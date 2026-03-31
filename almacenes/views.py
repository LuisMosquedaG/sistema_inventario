from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Almacen
from panel.models import Empresa # <--- IMPORTANTE

# --- 1. FUNCIÓN AYUDANTE ESTÁNDAR ---
def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

# --- VISTA PRINCIPAL (LISTADO) ---
@login_required(login_url='/login/')
def lista_almacenes(request):
    empresa_actual = get_empresa_actual(request)
    
    # Seguridad: Si no hay empresa, bloquear.
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Filtrar almacenes por empresa detectada
    almacenes = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')

    contexto = {
        'almacenes': almacenes
    }
    return render(request, 'dashboard_almacenes.html', contexto)

# --- API: CREAR ALMACÉN ---
@login_required
def api_crear_almacen(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'No se detectó empresa. Ingresa por tu subdominio.'})

            data = request.POST
            
            nuevo_almacen = Almacen.objects.create(
                nombre=data.get('nombre'),
                responsable=data.get('responsable'),
                calle=data.get('calle'),
                numero_ext=data.get('numero_ext'),
                numero_int=data.get('numero_int'),
                colonia=data.get('colonia'),
                estado=data.get('estado'),
                cp=data.get('cp'),
                telefono=data.get('telefono'),
                empresa=empresa_actual # <--- ASIGNACIÓN EXPLÍCITA
            )
            return JsonResponse({'success': True, 'message': 'Almacén creado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})

# --- API: DETALLE ALMACÉN ---
@login_required
def api_detalle_almacen(request, id):
    try:
        empresa_actual = get_empresa_actual(request)
        
        # Verificamos propiedad del almacén
        almacen = get_object_or_404(Almacen, id=id, empresa=empresa_actual)
            
        data = {
            'id': almacen.id,
            'nombre': almacen.nombre,
            'responsable': almacen.responsable,
            'calle': almacen.calle,
            'numero_ext': almacen.numero_ext,
            'numero_int': almacen.numero_int,
            'colonia': almacen.colonia,
            'estado': almacen.estado,
            'cp': almacen.cp,
            'telefono': almacen.telefono,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': 'Almacén no encontrado'}, status=404)

# --- API: ACTUALIZAR ALMACÉN ---
@login_required
def api_actualizar_almacen(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            
            # Verificamos propiedad
            almacen = get_object_or_404(Almacen, id=id, empresa=empresa_actual)

            data = request.POST
            
            almacen.nombre = data.get('nombre')
            almacen.responsable = data.get('responsable')
            almacen.calle = data.get('calle')
            almacen.numero_ext = data.get('numero_ext')
            almacen.numero_int = data.get('numero_int')
            almacen.colonia = data.get('colonia')
            almacen.estado = data.get('estado')
            almacen.cp = data.get('cp')
            almacen.telefono = data.get('telefono')
            
            almacen.save()
            return JsonResponse({'success': True, 'message': 'Almacén actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})