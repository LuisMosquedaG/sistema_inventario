from django.shortcuts import render, redirect, get_object_or_404
from .models import Cotizacion, DetalleCotizacion
from django.contrib import messages
from clientes.models import Cliente, ContactoCliente
from core.models import Producto
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
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

@login_required(login_url='/login/')
def dashboard_cotizaciones(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Filtramos Cotizaciones y Clientes por empresa
    lista_cotizaciones = Cotizacion.objects.filter(empresa=empresa_actual).order_by('-creado_en')
    todos_los_clientes = Cliente.objects.filter(empresa=empresa_actual)
    
    # --- CORRECCIÓN: Filtramos Productos por empresa ---
    # (Revisamos core/models.py y SÍ tiene el campo empresa)
    todos_los_productos = Producto.objects.filter(empresa=empresa_actual)
    
    contexto = {
        'cotizaciones': lista_cotizaciones,
        'clientes': todos_los_clientes,
        'productos': todos_los_productos
    }
    return render(request, 'dashboard_cotizaciones.html', contexto)


@login_required(login_url='/login/')
def crear_cotizacion(request):
    empresa_actual = get_empresa_actual(request)
    
    if request.method == 'POST':
        try:
            # --- 1. DATOS CABECERA ---
            cliente_id = request.POST.get('cliente')
            contacto_id = request.POST.get('contacto')
            fecha_ini = request.POST.get('fecha_inicio')
            fecha_fin = request.POST.get('fecha_fin')
            origen = request.POST.get('origen')
            direccion = request.POST.get('direccion_entrega')
            
            if not fecha_ini or not fecha_fin:
                messages.error(request, 'Las fechas de vigencia son obligatorias.')
                return redirect('dashboard_cotizaciones')

            if not cliente_id:
                messages.error(request, 'Debes seleccionar un cliente.')
                return redirect('dashboard_cotizaciones')

            # --- SEGURIDAD: Validar Cliente ---
            cliente_obj = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)

            contacto_obj = None
            if contacto_id:
                # El contacto debe pertenecer al cliente seleccionado
                contacto_obj = get_object_or_404(ContactoCliente, id=contacto_id, cliente=cliente_obj)

            # --- 2. CREAR CABECERA ---
            nueva_cotizacion = Cotizacion.objects.create(
                cliente=cliente_obj,
                contacto=contacto_obj,
                vendedor=request.user,
                fecha_inicio=fecha_ini,
                fecha_fin=fecha_fin,
                origen=origen,
                direccion_entrega=direccion,
                estado='borrador',
                empresa=empresa_actual
            )

            # --- 3. GUARDAR DETALLES ---
            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            precios = request.POST.getlist('precio_unitario[]')

            count = 0
            for prod_id, cant, prec in zip(productos_ids, cantidades, precios):
                if prod_id and prod_id != '':
                    # --- SEGURIDAD: Validar Producto ---
                    producto_obj = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
                    
                    DetalleCotizacion.objects.create(
                        cotizacion=nueva_cotizacion,
                        producto=producto_obj,
                        cantidad=cant,
                        precio_unitario=prec
                    )
                    count += 1
            
            if count > 0:
                messages.success(request, f'Cotización #{nueva_cotizacion.id} guardada con {count} productos.')
            else:
                messages.warning(request, 'Cotización creada pero sin productos.')

            return redirect('dashboard_cotizaciones')

        except Exception as e:
            messages.error(request, f'Error al guardar: {str(e)}')
            return redirect('dashboard_cotizaciones')
            
    return redirect('dashboard_cotizaciones')

@login_required(login_url='/login/')
def obtener_cotizacion_json(request, cotizacion_id):
    """Devuelve los datos de una cotización específica"""
    try:
        empresa_actual = get_empresa_actual(request)
        # --- SEGURIDAD ---
        cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)
        
        data = model_to_dict(cotizacion)
        data['fecha_inicio'] = cotizacion.fecha_inicio.strftime('%Y-%m-%d') if cotizacion.fecha_inicio else ''
        data['fecha_fin'] = cotizacion.fecha_fin.strftime('%Y-%m-%d') if cotizacion.fecha_fin else ''
        data['cliente_nombre'] = f"{cotizacion.cliente.nombre} {cotizacion.cliente.apellidos}"
        data['contacto_id'] = cotizacion.contacto.id if cotizacion.contacto else None
        

        detalles_list = []
        for det in cotizacion.detalles.all():
            detalles_list.append({
                'producto_id': det.producto.id,
                'producto_nombre': det.producto.nombre,
                'cantidad': det.cantidad,
                'precio': str(det.precio_unitario),
                'total': str(det.subtotal)
            })
        
        data['detalles'] = detalles_list

        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': 'Cotización no encontrada'}, status=404)

@login_required(login_url='/login/')
def actualizar_cotizacion(request, cotizacion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            # --- SEGURIDAD ---
            cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)

            # Actualizar Cabecera
            cliente_id = request.POST.get('cliente')
            fecha_ini = request.POST.get('fecha_inicio')
            fecha_fin = request.POST.get('fecha_fin')
            origen = request.POST.get('origen')
            direccion = request.POST.get('direccion_entrega')

            if not cliente_id or not fecha_ini or not fecha_fin:
                messages.error(request, 'Faltan datos obligatorios.')
                return redirect('dashboard_cotizaciones')

            contacto_id = request.POST.get('contacto')
            contacto_obj = None
            if contacto_id:
                contacto_obj = get_object_or_404(ContactoCliente, id=contacto_id)

            # --- SEGURIDAD: Validar nuevo cliente ---
            cotizacion.cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
            
            cotizacion.contacto = contacto_obj
            cotizacion.fecha_inicio = fecha_ini
            cotizacion.fecha_fin = fecha_fin
            cotizacion.origen = origen
            cotizacion.direccion_entrega = direccion
            cotizacion.save()

            # Actualizar Detalles
            cotizacion.detalles.all().delete()

            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            precios = request.POST.getlist('precio_unitario[]')

            for prod_id, cant, prec in zip(productos_ids, cantidades, precios):
                if prod_id and prod_id != '':
                    # --- SEGURIDAD: Validar Producto al actualizar ---
                    producto_obj = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
                    DetalleCotizacion.objects.create(
                        cotizacion=cotizacion,
                        producto=producto_obj,
                        cantidad=cant,
                        precio_unitario=prec
                    )

            messages.success(request, f'Cotización #{cotizacion.id} actualizada correctamente.')
            return redirect('dashboard_cotizaciones')

        except Exception as e:
            messages.error(request, f'Error al actualizar: {str(e)}')
            return redirect('dashboard_cotizaciones')
            
    return redirect('dashboard_cotizaciones')

@login_required(login_url='/login/')
def aprobar_cotizacion(request, cotizacion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)
            
            if cotizacion.estado == 'borrador':
                cotizacion.estado = 'aprobada'
                cotizacion.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'La cotización ya no está en borrador.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
@login_required(login_url='/login/')
def recotizar(request, cotizacion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            original = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)

            if original.estado != 'aprobada':
                messages.error(request, 'Solo se pueden recotizar cotizaciones aprobadas.')
                return redirect('dashboard_cotizaciones')

            original.estado = 'cancelada'
            original.save()

            # Clonar
            nueva = Cotizacion.objects.create(
                cliente=original.cliente,
                vendedor=request.user,
                fecha_inicio=original.fecha_inicio,
                fecha_fin=original.fecha_fin,
                origen=original.origen,
                direccion_entrega=original.direccion_entrega,
                estado='borrador',
                parent_quote=original,
                empresa=original.empresa # Hereda la empresa correctamente
            )

            for detalle in original.detalles.all():
                DetalleCotizacion.objects.create(
                    cotizacion=nueva,
                    producto=detalle.producto,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario
                )

            messages.success(request, f'Cotización recotizada exitosamente. Nuevo folio: {nueva.folio_completo}')
            return redirect('dashboard_cotizaciones')

        except Exception as e:
            messages.error(request, f'Error al recotizar: {str(e)}')
            return redirect('dashboard_cotizaciones')
            
    return redirect('dashboard_cotizaciones')