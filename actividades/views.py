from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from .models import Actividad
from clientes.models import Cliente, ContactoCliente
from cotizaciones.models import Cotizacion
from django.contrib.auth.decorators import login_required
from panel.models import Empresa

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

# 1. VISTA PRINCIPAL (LISTA)
@login_required(login_url='/login/')
def lista_actividades(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Filtrar actividades y clientes por empresa
    actividades = Actividad.objects.filter(empresa=empresa_actual).select_related('cliente', 'contacto', 'cotizacion')
    clientes = Cliente.objects.filter(empresa=empresa_actual) # <--- CORRECCIÓN: Filtrar clientes
    
    return render(request, 'dashboard_actividades.html', {
        'actividades': actividades,
        'clientes': clientes
    })

@login_required(login_url='/login/')
def crear_actividad(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no detectada'})

    if request.method == 'POST':
        try:
            # Capturamos datos
            nombre = request.POST.get('nombre')
            fecha = request.POST.get('fecha')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fin = request.POST.get('hora_fin')
            tipo = request.POST.get('tipo')
            prioridad = request.POST.get('prioridad')
            cliente_id = request.POST.get('cliente')
            contacto_id = request.POST.get('contacto')
            cotizacion_id = request.POST.get('cotizacion')
            correo = request.POST.get('correo')
            direccion = request.POST.get('direccion')
            descripcion = request.POST.get('descripcion')
            estado = request.POST.get('estado', 'borrador') 

            if not cliente_id:
                return JsonResponse({'success': False, 'error': 'El cliente es obligatorio.'})

            # --- SEGURIDAD: Verificar que el Cliente pertenezca a la empresa ---
            cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)

            # --- SEGURIDAD: Verificar Contacto (si se envía) ---
            contacto = None
            if contacto_id:
                # Como Contacto depende de Cliente, si el Cliente es de la empresa, sus contactos lo son.
                # Pero verificamos que exista.
                contacto = get_object_or_404(ContactoCliente, id=contacto_id, cliente=cliente)

            # --- SEGURIDAD: Verificar Cotización (si se envía) ---
            # Asumimos que Cotización tiene empresa, si no, verificar por cliente.
            cotizacion = None
            if cotizacion_id:
                # Nota: Si tu modelo Cotizacion no tiene campo empresa directo, verifica por cliente
                try:
                    cotizacion = Cotizacion.objects.get(id=cotizacion_id, cliente=cliente)
                except Cotizacion.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'La cotización no pertenece a este cliente.'})

            Actividad.objects.create(
                nombre=nombre, 
                fecha=fecha, 
                hora_inicio=hora_inicio, 
                hora_fin=hora_fin,
                tipo=tipo, 
                prioridad=prioridad,
                cliente=cliente, # <--- Pasamos el objeto validado
                contacto=contacto, # <--- Pasamos el objeto validado
                cotizacion=cotizacion, # <--- Pasamos el objeto validado
                correo=correo, 
                direccion=direccion, 
                descripcion=descripcion,
                estado=estado,
                empresa=empresa_actual
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# 3. VISTA: EDITAR ACTIVIDAD
@login_required(login_url='/login/')
def editar_actividad(request, actividad_id):
    empresa_actual = get_empresa_actual(request)
    
    if request.method == 'POST':
        try:
            # --- SEGURIDAD: Verificar que la actividad pertenezca a la empresa ---
            actividad = get_object_or_404(Actividad, id=actividad_id, empresa=empresa_actual)
            
            if actividad.estado != 'borrador':
                return JsonResponse({'success': False, 'error': 'Solo se pueden editar actividades en borrador.'})

            # Actualizar campos simples
            actividad.nombre = request.POST.get('nombre')
            actividad.fecha = request.POST.get('fecha')
            actividad.hora_inicio = request.POST.get('hora_inicio')
            actividad.hora_fin = request.POST.get('hora_fin')
            actividad.tipo = request.POST.get('tipo')
            actividad.prioridad = request.POST.get('prioridad')
            actividad.descripcion = request.POST.get('descripcion')
            actividad.correo = request.POST.get('correo')
            actividad.direccion = request.POST.get('direccion')

            # ACTUALIZAR RELACIONES CON VALIDACIÓN
            cliente_id = request.POST.get('cliente')
            contacto_id = request.POST.get('contacto')
            cotizacion_id = request.POST.get('cotizacion')

            if cliente_id:
                # Validar nuevo cliente
                nuevo_cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
                actividad.cliente = nuevo_cliente
            
            if contacto_id:
                # Validar contacto (perteneciente al cliente seleccionado arriba)
                actividad.contacto = get_object_or_404(ContactoCliente, id=contacto_id, cliente=actividad.cliente)
            else:
                actividad.contacto = None

            if cotizacion_id:
                # Validar cotización (perteneciente al cliente)
                actividad.cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, cliente=actividad.cliente)
            else:
                actividad.cotizacion = None
            
            actividad.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# 4. VISTA: CAMBIAR ESTADO
@login_required(login_url='/login/')
@csrf_exempt
def cambiar_estado_actividad(request, actividad_id):
    empresa_actual = get_empresa_actual(request)
    
    if request.method == 'POST':
        try:
            # --- SEGURIDAD ---
            actividad = get_object_or_404(Actividad, id=actividad_id, empresa=empresa_actual)
            
            nuevo_estado = request.POST.get('nuevo_estado')
            
            if actividad.estado == 'borrador' and nuevo_estado == 'pendiente':
                actividad.estado = 'pendiente'
                actividad.save()
                return JsonResponse({'success': True, 'mensaje': 'Actividad aprobada y enviada a pendiente.'})
            
            elif actividad.estado == 'pendiente' and nuevo_estado == 'completada':
                actividad.estado = 'completada'
                actividad.save()
                return JsonResponse({'success': True, 'mensaje': 'Actividad completada exitosamente.'})
            
            else:
                return JsonResponse({'success': False, 'error': 'Transición de estado no permitida.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# 5. VISTA: REPROGRAMAR
@login_required(login_url='/login/')
def reprogramar_actividad(request, actividad_id):
    empresa_actual = get_empresa_actual(request)
    
    if request.method == 'POST':
        try:
            # --- SEGURIDAD ---
            actividad = get_object_or_404(Actividad, id=actividad_id, empresa=empresa_actual)
            
            if actividad.estado != 'pendiente':
                return JsonResponse({'success': False, 'error': 'Solo se pueden reprogramar actividades pendientes.'})

            actividad.fecha = request.POST.get('fecha')
            actividad.hora_inicio = request.POST.get('hora_inicio')
            actividad.hora_fin = request.POST.get('hora_fin')
            actividad.descripcion = request.POST.get('descripcion')
            
            actividad.save()
            return JsonResponse({'success': True, 'mensaje': 'Actividad reprogramada.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# 6. VISTA: CANCELAR
@login_required(login_url='/login/')
def cancelar_actividad(request, actividad_id):
    empresa_actual = get_empresa_actual(request)
    
    if request.method == 'POST':
        try:
            # --- SEGURIDAD ---
            actividad = get_object_or_404(Actividad, id=actividad_id, empresa=empresa_actual)
            
            motivo = request.POST.get('motivo')
            
            if not motivo:
                return JsonResponse({'success': False, 'error': 'El motivo de cancelación es obligatorio.'})

            actividad.estado = 'cancelada'
            actividad.motivo_cancelacion = motivo
            actividad.save()
            
            return JsonResponse({'success': True, 'mensaje': 'Actividad cancelada.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# 7. VISTA: API DATOS ACTIVIDAD
@login_required(login_url='/login/')
def api_datos_actividad(request, actividad_id):
    empresa_actual = get_empresa_actual(request)
    try:
        # --- SEGURIDAD ---
        actividad = get_object_or_404(Actividad, id=actividad_id, empresa=empresa_actual)
        
        data = model_to_dict(actividad)
        if data.get('fecha'): data['fecha'] = actividad.fecha.strftime('%Y-%m-%d')
        data['cliente'] = actividad.cliente.id if actividad.cliente else None
        data['contacto'] = actividad.contacto.id if actividad.contacto else None
        data['cotizacion'] = actividad.cotizacion.id if actividad.cotizacion else None
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)
    
# 3. API: Obtener Datos del Cliente
@login_required(login_url='/login/')
@csrf_exempt
def api_cliente_datos(request, cliente_id):
    empresa_actual = get_empresa_actual(request)
    
    if request.method == 'GET':
        try:
            # --- SEGURIDAD: Solo ver clientes de mi empresa ---
            cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
            
            # 1. CONSTRUIR LISTA DE CONTACTOS
            contactos_data = []
            for c in ContactoCliente.objects.filter(cliente=cliente):
                contactos_data.append({
                    'id': c.id,
                    'nombre_completo': c.nombre_completo,
                    'correo_1': c.correo_1,
                    'telefono_1': c.telefono_1
                })
            
            # 2. CONSTRUIR LISTA DE COTIZACIONES
            cotizaciones_data = []
            for cot in Cotizacion.objects.filter(cliente=cliente):
                cotizaciones_data.append({
                    'id': cot.id,
                    'folio_completo': cot.folio_completo
                })

            return JsonResponse({
                'cliente': {
                    'email': cliente.email,
                    'calle': cliente.calle,
                    'numero_ext': cliente.numero_ext,
                    'numero_int': cliente.numero_int,
                    'colonia': cliente.colonia,
                    'estado': cliente.estado,
                    'cp': cliente.cp,
                },
                'contactos': contactos_data,
                'cotizaciones': cotizaciones_data
            })
            
        except Exception as e:
            print(f"Error en API: {e}")
            return JsonResponse({'error': str(e)}, status=500)