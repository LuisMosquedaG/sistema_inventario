from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notificacion
from panel.models import Empresa
from django.utils import timezone
from datetime import timedelta

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

@login_required
def api_notificaciones_recientes(request):
    """
    Endpoint para el polling de notificaciones en tiempo real (Toasts).
    Marca las notificaciones como 'visto_en_toast' para no repetirlas.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Sin empresa'})

    # Definición de Admin/Sadmin según requerimiento
    es_admin = request.user.is_superuser or \
               request.user.is_staff or \
               request.user.username.startswith('sadmin@') or \
               request.user.username == 'madmin@crossoversuite'

    if es_admin:
        # Admins/Sadmins ven todo de su empresa (excepto lo propio para no auto-notificarse)
        qs = Notificacion.objects.filter(empresa=empresa, visto_en_toast=False).exclude(actor=request.user)
    else:
        # Usuarios tipo "usuario" ven solo notificaciones de registros donde son dueños (propietario_recurso)
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
        })
        n.visto_en_toast = True
        n.save()

    return JsonResponse({'success': True, 'notificaciones': data})

@login_required
def lista_notificaciones(request):
    """
    Vista para consultar el historial de notificaciones (Última semana).
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return render(request, 'error_sin_empresa.html')

    hace_una_semana = timezone.now() - timedelta(days=7)
    
    # Definición de Admin/Sadmin según requerimiento
    es_admin = request.user.is_superuser or \
               request.user.is_staff or \
               request.user.username.startswith('sadmin@') or \
               request.user.username == 'madmin@crossoversuite'

    if es_admin:
        # Admins/Sadmins ven todo el historial de la empresa
        qs = Notificacion.objects.filter(empresa=empresa, fecha__gte=hace_una_semana)
    else:
        # Usuarios normales solo ven historial de sus propios registros
        qs = Notificacion.objects.filter(
            propietario_recurso=request.user,
            empresa=empresa, 
            fecha__gte=hace_una_semana
        )

    # Limpiar nombres de usuario para la plantilla
    for n in qs:
        n.actor_corto = n.actor.username.split('@')[0]

    return render(request, 'notificaciones/historial.html', {
        'notificaciones': qs,
        'section': 'notificaciones'
    })
