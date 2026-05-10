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
from notificaciones.utils import crear_notificacion
from preferencias.permissions import require_sales_permission

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

from django.db.models import Q

@login_required(login_url='/login/')
@require_sales_permission('cotizaciones', 'ver')
def dashboard_cotizaciones(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    folio = request.GET.get('folio', '')
    cliente_id = request.GET.get('cliente_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')

    lista_cotizaciones = Cotizacion.objects.filter(empresa=empresa_actual).order_by('-creado_en')

    if q:
        # Intentar convertir q a número para buscar por ID exacto o parcial
        lista_cotizaciones = lista_cotizaciones.filter(
            Q(id__icontains=q) |
            Q(cliente__razon_social__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(cliente__apellidos__icontains=q) |
            Q(origen__icontains=q) |
            Q(estado__icontains=q)
        )
    if folio:
        lista_cotizaciones = lista_cotizaciones.filter(id__icontains=folio)
    if cliente_id and cliente_id != 'all':
        lista_cotizaciones = lista_cotizaciones.filter(cliente_id=cliente_id)
    if fecha:
        try:
            lista_cotizaciones = lista_cotizaciones.filter(fecha_inicio=fecha)
        except:
            pass
    if estado:
        lista_cotizaciones = lista_cotizaciones.filter(estado=estado)

    # Para mantener el nombre del cliente en el buscador visual
    cliente_nombre_display = ""
    if cliente_id and cliente_id != 'all':
        try:
            c_obj = Cliente.objects.get(id=cliente_id, empresa=empresa_actual)
            cliente_nombre_display = f"{c_obj.nombre} {c_obj.apellidos}"
            if c_obj.razon_social: cliente_nombre_display += f" - {c_obj.razon_social}"
        except:
            pass

    filtros = {
        'q': q,
        'folio': folio,
        'cliente_id': cliente_id,
        'cliente_nombre': cliente_nombre_display,
        'fecha': fecha,
        'estado': estado
    }
    # --- FIN LÓGICA DE FILTRADO ---

    todos_los_clientes = Cliente.objects.filter(empresa=empresa_actual)
    todos_los_productos = Producto.objects.filter(empresa=empresa_actual)

    from categorias.models import Categoria as CategoriaCatalogo, ListaPrecioCosto
    todas_categorias = CategoriaCatalogo.objects.filter(empresa=empresa_actual)
    todas_listas = ListaPrecioCosto.objects.filter(empresa=empresa_actual)
    
    contexto = {
        'cotizaciones': lista_cotizaciones,
        'clientes': todos_los_clientes,
        'productos': todos_los_productos,
        'categorias_catalogo': todas_categorias,
        'listas_precios': todas_listas,
        'filtros': filtros
    }
    return render(request, 'dashboard_cotizaciones.html', contexto)

@login_required(login_url='/login/')
@require_sales_permission('cotizaciones', 'imprimir')
def imprimir_cotizacion(request, pk):
    empresa_actual = get_empresa_actual(request)
    cotizacion = get_object_or_404(Cotizacion, id=pk, empresa=empresa_actual)

    # Limpiar nombre del vendedor (quitar @empresa si es necesario)
    vendedor_nombre = cotizacion.vendedor.get_full_name()
    if not vendedor_nombre:
        vendedor_nombre = cotizacion.vendedor.username.split('@')[0]

    context = {
        'cotizacion': cotizacion,
        'empresa': empresa_actual,
        'vendedor_nombre': vendedor_nombre,
    }
    return render(request, 'cotizaciones/imprimir_cotizacion.html', context)

@login_required(login_url='/login/')
@require_sales_permission('cotizaciones', 'crear')
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
                crear_notificacion(
                    empresa=empresa_actual,
                    actor=request.user,
                    mensaje=f'creó la cotización {nueva_cotizacion.folio_completo}',
                    propietario=request.user
                )
            else:
                messages.warning(request, 'Cotización creada pero sin productos.')

            return redirect('dashboard_cotizaciones')

        except Exception as e:
            messages.error(request, f'Error al guardar: {str(e)}')
            return redirect('dashboard_cotizaciones')
            
    return redirect('dashboard_cotizaciones')

@login_required(login_url='/login/')
@require_sales_permission('cotizaciones', 'ver', json_response=True)
def obtener_cotizacion_json(request, cotizacion_id):
    """Devuelve los datos de una cotización específica"""
    try:
        empresa_actual = get_empresa_actual(request)
        # --- SEGURIDAD ---
        cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)
        
        data = model_to_dict(cotizacion)
        data['folio_completo'] = cotizacion.folio_completo
        data['fecha_inicio'] = cotizacion.fecha_inicio.strftime('%Y-%m-%d') if cotizacion.fecha_inicio else ''
        data['fecha_fin'] = cotizacion.fecha_fin.strftime('%Y-%m-%d') if cotizacion.fecha_fin else ''
        data['cliente_nombre'] = f"{cotizacion.cliente.nombre} {cotizacion.cliente.apellidos}"
        if cotizacion.cliente.razon_social:
            data['cliente_nombre'] = cotizacion.cliente.razon_social
            
        data['contacto_id'] = cotizacion.contacto.id if cotizacion.contacto else None
        data['contacto_nombre'] = cotizacion.contacto.nombre_completo if cotizacion.contacto else 'Sin contacto'
        

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
@require_sales_permission('cotizaciones', 'editar')
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
@require_sales_permission('cotizaciones', 'aprobar', json_response=True)
def aprobar_cotizacion(request, cotizacion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)
            
            # --- VALIDACIÓN: No aprobar si hay productos en REVISIÓN ---
            productos_revision = cotizacion.detalles.filter(producto__estado='revision')
            if productos_revision.exists():
                nombres = ", ".join([d.producto.nombre for d in productos_revision])
                return JsonResponse({
                    'success': False, 
                    'error': f'No se puede aprobar la cotización porque contiene productos en revisión: {nombres}. Por favor, activa los productos en el inventario primero.'
                })

            if cotizacion.estado == 'borrador':
                cotizacion.estado = 'aprobada'
                cotizacion.save()
                crear_notificacion(
                    empresa=empresa_actual,
                    actor=request.user,
                    mensaje=f'aprobó la cotización {cotizacion.folio_completo}',
                    propietario=cotizacion.vendedor
                )
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'La cotización ya no está en borrador.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
@login_required(login_url='/login/')
@require_sales_permission('cotizaciones', 'crear')
def recotizar(request, cotizacion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            original = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)

            if original.estado != 'aprobada':
                messages.error(request, 'Solo se pueden recotizar cotizaciones aprobadas.')
                return redirect('dashboard_cotizaciones')

            # Al recotizar, la original se cancela y se genera una nueva versión en borrador.
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
            crear_notificacion(
                empresa=empresa_actual,
                actor=request.user,
                mensaje=f'recotizó {original.folio_completo} -> {nueva.folio_completo}',
                propietario=original.vendedor
            )
            return redirect('dashboard_cotizaciones')

        except Exception as e:
            messages.error(request, f'Error al recotizar: {str(e)}')
            return redirect('dashboard_cotizaciones')
            
    return redirect('dashboard_cotizaciones')

@login_required(login_url='/login/')
@require_sales_permission('cotizaciones', 'eliminar')
def cancelar_cotizacion(request, cotizacion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)
            
            # Validación: No se puede cancelar si ya tiene pedido
            if cotizacion.tiene_pedido:
                messages.error(request, 'No se puede cancelar la cotización porque ya tiene un pedido generado.')
                return redirect('dashboard_cotizaciones')

            if cotizacion.estado in ['borrador', 'aprobada']:
                cotizacion.estado = 'cancelada'
                cotizacion.resultado = 'perdida'
                cotizacion.save()
                messages.success(request, f'Cotización #{cotizacion.id} cancelada correctamente.')
                crear_notificacion(
                    empresa=empresa_actual,
                    actor=request.user,
                    mensaje=f'canceló la cotización {cotizacion.folio_completo}',
                    propietario=cotizacion.vendedor
                )
            else:
                messages.error(request, 'Solo se pueden cancelar cotizaciones en estado borrador o aprobada.')
                
        except Exception as e:
            messages.error(request, f'Error al cancelar: {str(e)}')
            
    return redirect('dashboard_cotizaciones')
