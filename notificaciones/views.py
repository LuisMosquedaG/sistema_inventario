from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from .models import Notificacion
from panel.models import Empresa
from django.utils import timezone
from datetime import timedelta

def get_empresa_actual(request):
    username = request.user.username
    
    # CASO ESPECIAL: madmin@crossoversuite mapea a la empresa 'demo'
    if username == 'madmin@crossoversuite':
        return Empresa.objects.filter(subdominio='demo').first()
        
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

@csrf_exempt
def enviar_mensaje_ventas_ajax(request):
    """
    Recibe mensajes del formulario de la Landing Page y los convierte en notificaciones 
    para madmin y todos los sadmins del sistema (uno por empresa).
    """
    if request.method == 'POST':
        nombre = request.POST.get('Nombre')
        email = request.POST.get('Email')
        mensaje = request.POST.get('Mensaje')
        
        empresa_demo = Empresa.objects.filter(subdominio='demo').first()
        system = User.objects.filter(username='system@crossoversuite').first()
        
        # Identificar destinatarios únicos por empresa
        destinatarios = list(User.objects.filter(username__startswith='sadmin@'))
        madmin = User.objects.filter(username='madmin@crossoversuite').first()
        if madmin:
            destinatarios.insert(0, madmin) # Madmin primero para ser el "dueño" si hay conflicto

        empresas_final = {} # {subdominio: user_propietario}
        for user in destinatarios:
            sub = 'demo' if user.username == 'madmin@crossoversuite' else user.username.split('@')[1]
            if sub not in empresas_final:
                empresas_final[sub] = user
            
        if not empresas_final:
            return JsonResponse({'success': False, 'error': 'No se encontraron destinatarios.'})
            
        for sub, user_prop in empresas_final.items():
            u_empresa = Empresa.objects.filter(subdominio=sub).first() or empresa_demo
            if not u_empresa: continue

            Notificacion.objects.create(
                empresa=u_empresa,
                actor=system if system else (madmin if madmin else user_prop),
                propietario_recurso=user_prop,
                mensaje=f"MENSAJE DE VENTAS: {nombre} ({email}) dice: {mensaje}",
                link='#'
            )
        
        return JsonResponse({'success': True, 'message': 'Tu solicitud ha sido enviada correctamente.'})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_notificaciones_recientes(request):
    """
    Endpoint para el polling de notificaciones en tiempo real.
    Restringe los mensajes de ventas estrictamente a madmin y sadmin@.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Sin empresa'})

    username = request.user.username
    # Definición estricta de SuperAdmin para mensajes de ventas
    es_maestro = (username == 'madmin@crossoversuite' or username.startswith('sadmin@'))
    
    # Definición de Admin general para ver notificaciones de la empresa
    es_admin = es_maestro or request.user.is_superuser or request.user.is_staff or username.startswith('admin@')

    if es_admin:
        qs = Notificacion.objects.filter(empresa=empresa, visto_en_toast=False).exclude(actor=request.user)
        
        # PRIVACIDAD: Si no es maestro (madmin o sadmin@), no ve mensajes de ventas
        if not es_maestro:
            qs = qs.exclude(mensaje__icontains='MENSAJE DE VENTAS')
            qs = qs.exclude(propietario_recurso__username='madmin@crossoversuite')
    else:
        # Usuarios normales ven solo lo que se les asigne directamente
        qs = Notificacion.objects.filter(
            propietario_recurso=request.user,
            empresa=empresa, 
            visto_en_toast=False
        ).exclude(actor=request.user)

    data = []
    for n in qs:
        actor_corto = n.actor.username.split('@')[0]
        data.append({
            'id': n.id,
            'mensaje': n.mensaje,
            'actor': actor_corto,
            'link': n.link or '#',
            'fecha': n.fecha.strftime('%H:%M'),
            'es_ventas': 'MENSAJE DE VENTAS' in n.mensaje,
        })
        n.visto_en_toast = True
        n.save()

    return JsonResponse({'success': True, 'notificaciones': data})

@login_required
def lista_notificaciones(request):
    """
    Historial de notificaciones con restricción estricta de mensajes de ventas.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return render(request, 'error_sin_empresa.html')

    hace_una_semana = timezone.now() - timedelta(days=7)
    
    username = request.user.username
    es_maestro = (username == 'madmin@crossoversuite' or username.startswith('sadmin@'))
    es_admin = es_maestro or request.user.is_superuser or request.user.is_staff or username.startswith('admin@')

    if es_admin:
        qs = Notificacion.objects.filter(empresa=empresa, fecha__gte=hace_una_semana)

        # PRIVACIDAD: Si no es maestro, filtrar mensajes especiales
        if not es_maestro:
            qs = qs.exclude(mensaje__icontains='MENSAJE DE VENTAS')
            qs = qs.exclude(propietario_recurso__username='madmin@crossoversuite')
    else:
        qs = Notificacion.objects.filter(
            propietario_recurso=request.user,
            empresa=empresa, 
            fecha__gte=hace_una_semana
        )

    for n in qs:
        n.actor_corto = n.actor.username.split('@')[0]

    return render(request, 'notificaciones/historial.html', {
        'notificaciones': qs,
        'section': 'notificaciones'
    })
