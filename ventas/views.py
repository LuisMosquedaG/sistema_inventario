from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from .models import OrdenVenta, DetalleOrdenVenta
from pedidos.models import Pedido, DetallePedido
from panel.models import Empresa
from almacenes.models import Inventario
from clientes.models import Cliente
from core.models import Producto
from django.db.models import F
from notificaciones.utils import crear_notificacion
from preferencias.permissions import require_sales_permission, user_has_sales_permission

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

@login_required
@require_sales_permission('salidas', 'ver')
def dashboard_ventas(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    folio_salida = request.GET.get('folio_salida', '')
    folio_cotizacion = request.GET.get('folio_cotizacion', '')
    folio_pedido = request.GET.get('folio_pedido', '')
    fecha_salida = request.GET.get('fecha_salida', '')
    cliente_id = request.GET.get('cliente_id', '')
    estado = request.GET.get('estado', '')
    sucursal_id_filtro = request.GET.get('sucursal', '')

    ordenes = OrdenVenta.objects.filter(empresa=empresa_actual).select_related('pedido_origen', 'cliente', 'sucursal').order_by('-fecha_creacion')

    if q:
        ordenes = ordenes.filter(
            Q(id__icontains=q) |
            Q(pedido_origen__id__icontains=q) |
            Q(pedido_origen__cotizacion_origen_id__icontains=q) |
            Q(cliente__razon_social__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(cliente__apellidos__icontains=q) |
            Q(estado__icontains=q) |
            Q(detalles__producto__nombre__icontains=q)
        ).distinct()
    
    if folio_salida:
        clean_os = folio_salida.upper().replace('OS-', '').replace('OS', '').strip()
        ordenes = ordenes.filter(id__icontains=clean_os)
    if folio_cotizacion:
        clean_cot = folio_cotizacion.upper().replace('COT-', '').replace('COT', '').strip()
        ordenes = ordenes.filter(pedido_origen__cotizacion_origen_id__icontains=clean_cot)
    if folio_pedido:
        clean_ped = folio_pedido.upper().replace('PED-', '').replace('PED', '').strip()
        ordenes = ordenes.filter(pedido_origen__id__icontains=clean_ped)
        
    if cliente_id and cliente_id != 'all':
        ordenes = ordenes.filter(cliente_id=cliente_id)
    if fecha_salida:
        try:
            ordenes = ordenes.filter(fecha_creacion__date=fecha_salida)
        except:
            pass
    if estado:
        ordenes = ordenes.filter(estado=estado)
    if sucursal_id_filtro:
        ordenes = ordenes.filter(sucursal_id=sucursal_id_filtro)

    # Para el buscador visual
    cliente_nombre_display = ""
    if cliente_id and cliente_id != 'all':
        try:
            c_obj = Cliente.objects.get(id=cliente_id, empresa=empresa_actual)
            cliente_nombre_display = c_obj.razon_social if c_obj.razon_social else f"{c_obj.nombre} {c_obj.apellidos}"
        except:
            pass

    filtros = {
        'q': q,
        'folio_salida': folio_salida,
        'folio_cotizacion': folio_cotizacion,
        'folio_pedido': folio_pedido,
        'fecha_salida': fecha_salida,
        'cliente_id': cliente_id,
        'cliente_nombre': cliente_nombre_display,
        'estado': estado,
        'sucursal': sucursal_id_filtro
    }
    # --- FIN LÓGICA DE FILTRADO ---
    from preferencias.models import Sucursal
    sucursales_lista = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    cotizaciones_ids = set()
    for orden in ordenes:
        if orden.pedido_origen and orden.pedido_origen.cotizacion_origen_id:
            cotizaciones_ids.add(orden.pedido_origen.cotizacion_origen_id)
    
    fechas_map = {}
    if cotizaciones_ids:
        from cotizaciones.models import Cotizacion 
        datos_cot = Cotizacion.objects.filter(id__in=cotizaciones_ids).values('id', 'creado_en')
        for dato in datos_cot:
            fechas_map[dato['id']] = dato['creado_en']

    for orden in ordenes:
        orden.fecha_cotizacion_display = None
        if orden.pedido_origen and orden.pedido_origen.cotizacion_origen_id:
            orden.fecha_cotizacion_display = fechas_map.get(orden.pedido_origen.cotizacion_origen_id)

    # LISTA DE ALMACENES PARA EL MODAL
    almacenes = list(empresa_actual.almacen_set.all().values('id', 'nombre'))

    contexto = {
        'ordenes': ordenes, 
        'almacenes_json': almacenes, 
        'clientes': Cliente.objects.filter(empresa=empresa_actual), 
        'productos': Producto.objects.filter(empresa=empresa_actual),
        'sucursales': sucursales_lista,
        'filtros': filtros,
        'perm_ventas': {
            'ver': user_has_sales_permission(request, 'salidas', 'ver'),
            'crear': user_has_sales_permission(request, 'salidas', 'crear'),
            'editar': user_has_sales_permission(request, 'salidas', 'editar'),
            'eliminar': user_has_sales_permission(request, 'salidas', 'eliminar'),
            'aprobar': user_has_sales_permission(request, 'salidas', 'aprobar'),
            'imprimir': user_has_sales_permission(request, 'salidas', 'imprimir'),
        }
    }
    return render(request, 'dashboard_ventas.html', contexto)

@login_required
@transaction.atomic
@require_sales_permission('salidas', 'crear')
def crear_salida_directa(request):
    """Crea una Orden de Salida (Venta) directa sin pedido previo"""
    if request.method != 'POST':
        return redirect('dashboard_ventas')
    
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        messages.error(request, "Empresa no detectada")
        return redirect('dashboard_ventas')

    try:
        cliente_id = request.POST.get('cliente')
        cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
        
        # Asignar sucursal desde la sesión
        sucursal_obj = None
        sucursal_id = request.session.get('sucursal_id')
        if sucursal_id:
            from preferencias.models import Sucursal
            try:
                sucursal_obj = Sucursal.objects.get(id=sucursal_id, empresa=empresa_actual)
            except Sucursal.DoesNotExist:
                pass

        # 1. Crear la cabecera
        ov = OrdenVenta.objects.create(
            pedido_origen=None,
            cliente=cliente,
            vendedor=request.user,
            empresa=empresa_actual,
            sucursal=sucursal_obj,
            estado='borrador'
        )

        # 2. Crear los detalles
        productos_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        precios = request.POST.getlist('precio_unitario[]')

        if not productos_ids:
            raise ValueError("Debes agregar al menos un artículo a la salida.")

        for i in range(len(productos_ids)):
            prod_id = productos_ids[i]
            producto = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
            
            DetalleOrdenVenta.objects.create(
                orden_venta=ov,
                producto=producto,
                cantidad=int(cantidades[i]),
                precio_unitario=Decimal(precios[i])
            )

        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'creó salida directa {ov.folio_display}',
            propietario=request.user
        )

        messages.success(request, f'Orden de Salida OS-{ov.id:04d} creada correctamente.')
    except Exception as e:
        messages.error(request, f'Error al crear salida: {str(e)}')

    return redirect('dashboard_ventas')

@login_required
@transaction.atomic
@require_sales_permission('salidas', 'crear')
def crear_orden_venta(request, pedido_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        messages.error(request, "Empresa no detectada")
        return redirect('dashboard_pedidos')

    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)
    if pedido.estado not in ['confirmado', 'completo']:
        messages.error(request, 'Solo se pueden generar Órdenes de Venta desde pedidos confirmados.')
        return redirect('dashboard_pedidos')

    # Permitir creación solo si no hay una orden de venta ABIERTA para este pedido
    # (Borrador o Aprobado)
    orden_abierta = OrdenVenta.objects.filter(pedido_origen=pedido, estado__in=['borrador', 'aprobado']).exists()
    if orden_abierta:
        messages.warning(request, 'Este pedido ya tiene una Orden de Salida activa.')
        return redirect('dashboard_ventas')

    ov = OrdenVenta.objects.create(
        pedido_origen=pedido,
        cliente=pedido.cliente,
        vendedor=pedido.vendedor, # Se hereda el vendedor del pedido original
        empresa=empresa_actual,
        sucursal=pedido.sucursal, # Hereda la sucursal del pedido
        estado='borrador'
    )

    lineas_pedido = pedido.detalles.filter(parent_line__isnull=True)
    for linea in lineas_pedido:
        DetalleOrdenVenta.objects.create(
            orden_venta=ov,
            producto=linea.producto,
            cantidad=linea.cantidad_solicitada,
            precio_unitario=linea.precio_unitario
        )

    # NOTIFICACIÓN
    crear_notificacion(
        empresa=empresa_actual,
        mensaje=f"Se ha generado una Orden de Salida #{ov.id} desde el Pedido #{pedido.id}",
        actor=request.user,
        propietario=pedido.vendedor # El dueño es el vendedor original
    )

    messages.success(request, f'Orden de Salida #{ov.id} creada en estado Borrador.')
    return redirect('dashboard_ventas')

@login_required
@require_sales_permission('salidas', 'aprobar')
def cambiar_estado_ov(request, ov_id, nuevo_estado):
    empresa_actual = get_empresa_actual(request)
    ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)
    if nuevo_estado == 'aprobado' and ov.estado == 'borrador':
        ov.estado = 'aprobado'
        ov.save()

        # NOTIFICACIÓN
        crear_notificacion(
            empresa=empresa_actual,
            mensaje=f"La Orden de Salida #{ov.id} ha sido Aprobada.",
            actor=request.user,
            propietario=ov.vendedor
        )

        messages.success(request, 'Orden de Salida Aprobada. Lista para surtir.')
    return redirect('dashboard_ventas')

@login_required
@require_sales_permission('salidas', 'ver', json_response=True)
def api_preparar_surtido(request, ov_id):
    empresa_actual = get_empresa_actual(request)
    ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)

    if ov.estado not in ['borrador', 'aprobado', 'surtido']:
        return JsonResponse({'success': False, 'error': 'Estado inválido para ver detalles.'})

    almacen_id_req = request.GET.get('almacen_id')
    almacen_final_id = almacen_id_req or (ov.almacen.id if ov.almacen else None)

    cliente = ov.cliente
    pedido_origen = ov.pedido_origen
    
    razon_social = cliente.razon_social if cliente.razon_social else ""
    nombre_completo = f"{cliente.nombre} {cliente.apellidos}" if not razon_social else ""
    correo_cliente = getattr(cliente, 'email', '')
    telefono_cliente = getattr(cliente, 'telefono', '')
    
    dir_parts = []
    if cliente.calle: dir_parts.append(cliente.calle)
    if cliente.numero_ext: dir_parts.append(f"#{cliente.numero_ext}")
    if cliente.numero_int: dir_parts.append(f"Int {cliente.numero_int}")
    if cliente.colonia: dir_parts.append(cliente.colonia)
    if cliente.cp: dir_parts.append(f"CP {cliente.cp}")
    if cliente.estado_dir: dir_parts.append(cliente.estado_dir)
    direccion_completa = ", ".join(dir_parts)

    contacto_nombre, contacto_correo, contacto_telefono = "", "", ""
    if pedido_origen and pedido_origen.cotizacion_origen_id:
        try:
            from cotizaciones.models import Cotizacion
            cot = Cotizacion.objects.get(id=pedido_origen.cotizacion_origen_id, empresa=empresa_actual)
            if cot.contacto:
                contacto_nombre = cot.contacto.nombre_completo
                contacto_correo = cot.contacto.correo_1 or cot.contacto.correo_2 or ""
                contacto_telefono = cot.contacto.telefono_1 or cot.contacto.telefono_2 or ""
        except: pass

    envio_parts = []
    if getattr(cliente, 'envio_calle', ''): envio_parts.append(cliente.envio_calle)
    if getattr(cliente, 'envio_numero_ext', ''): envio_parts.append(f"#{cliente.envio_numero_ext}")
    if getattr(cliente, 'envio_numero_int', ''): envio_parts.append(f"Int {cliente.envio_numero_int}")
    if getattr(cliente, 'envio_colonia', ''): envio_parts.append(cliente.envio_colonia)
    if getattr(cliente, 'envio_cp', ''): envio_parts.append(f"CP {cliente.envio_cp}")
    if getattr(cliente, 'envio_estado', ''): envio_parts.append(cliente.envio_estado)
    direccion_cliente_envio = ", ".join(envio_parts)

    final_quien_recibe = ov.quien_recibe or getattr(cliente, 'envio_quien_recibe', '') or cliente.nombre
    final_telefono = ov.telefono_recibe or getattr(cliente, 'envio_telefono', '') or contacto_telefono or telefono_cliente
    final_correo = ov.contacto_envio or getattr(cliente, 'envio_correo', '') or contacto_correo or correo_cliente
    final_notas = ov.notas_envio or getattr(cliente, 'envio_notas', '')

    from recepciones.models import DetalleRecepcionExtra
    detalles_data = []
    total_calculado = 0
    for det in ov.detalles.all():
        subtotal = float(det.subtotal)
        total_calculado += subtotal
        extras_disponibles = []
        if (det.producto.maneja_lote or det.producto.maneja_serie) and almacen_final_id:
            extras_qs = DetalleRecepcionExtra.objects.filter(almacen_id=almacen_final_id, detalle_recepcion__producto=det.producto)
            for extra in extras_qs:
                if extra.tipo == 'lote' and extra.cantidad_lote <= 0: continue
                extras_disponibles.append({'id': extra.id, 'tipo': extra.tipo, 'lote': extra.lote, 'serie': extra.serie, 'cantidad': extra.cantidad_lote if extra.tipo == 'lote' else 1})

        detalles_data.append({
            'id': det.id, 'producto_id': det.producto.id, 'producto_nombre': det.producto.nombre,
            'cantidad': det.cantidad, 'precio': float(det.precio_unitario), 'subtotal': subtotal,
            'maneja_lote': det.producto.maneja_lote, 'maneja_serie': det.producto.maneja_serie, 'extras': extras_disponibles
        })

    return JsonResponse({
        'success': True, 'id': ov.id, 'almacen_id': almacen_final_id,
        'folio_display': ov.folio_display,
        'cliente_razon': razon_social, 'cliente_nombre': nombre_completo, 'cliente_correo': correo_cliente, 'cliente_telefono': telefono_cliente, 'cliente_direccion': direccion_completa,
        'contacto_nombre': contacto_nombre, 'contacto_correo': contacto_correo, 'contacto_telefono': contacto_telefono,
        'direccion_envio': ov.direccion_envio or direccion_cliente_envio,
        'quien_recibe': final_quien_recibe, 'telefono_recibe': final_telefono, 'email': final_correo, 'guia': ov.guia or '', 'notas_envio': final_notas,
        'detalles': detalles_data, 'total': total_calculado
    })

@login_required
@require_sales_permission('salidas', 'imprimir')
def imprimir_salida(request, pk):
    """Genera la vista para impresión de orden de salida (PDF)"""
    empresa_actual = get_empresa_actual(request)
    orden = get_object_or_404(OrdenVenta, id=pk, empresa=empresa_actual)

    # Limpiar nombre del vendedor
    vendedor_nombre = orden.vendedor.get_full_name()
    if not vendedor_nombre:
        vendedor_nombre = orden.vendedor.username.split('@')[0]

    context = {
        'orden': orden,
        'empresa': empresa_actual,
        'vendedor_nombre': vendedor_nombre,
    }
    return render(request, 'ventas/imprimir_salida.html', context)

@login_required
@transaction.atomic
@require_sales_permission('salidas', 'surtir_orden', json_response=True)
def ejecutar_surtido(request, ov_id):
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Método no permitido'})
    try:
        empresa_actual = get_empresa_actual(request)
        ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)
        
        if ov.estado == 'surtido':
            return JsonResponse({'success': False, 'error': 'Esta orden ya ha sido surtida.'})

        almacen_id = request.POST.get('almacen_id')
        if not almacen_id: raise ValueError("Debes seleccionar un almacén de salida.")
        
        from almacenes.models import Almacen, Inventario, Kardex
        from recepciones.models import DetalleRecepcionExtra
        
        almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
        ov.almacen = almacen
        ov.direccion_envio, ov.quien_recibe = request.POST.get('direccion'), request.POST.get('quien_recibe')
        ov.telefono_recibe, ov.guia, ov.notas_envio = request.POST.get('telefono_recibe'), request.POST.get('guia'), request.POST.get('notas')
        ov.fecha_surtido = timezone.now()
        
        # 1. Preparar Orden Hija (Backorder) si es necesario
        orden_hija = None
        detalles_actuales = list(ov.detalles.all())
        
        for det in detalles_actuales:
            producto = det.producto
            cant_solicitada = det.cantidad
            cant_a_entregar = int(request.POST.get(f'cantidad_entregar_{det.id}', cant_solicitada))
            
            if cant_a_entregar < 0: raise ValueError(f"Cantidad inválida para {producto.nombre}")
            if cant_a_entregar > cant_solicitada: raise ValueError(f"No puedes entregar más de lo solicitado ({cant_solicitada}) para {producto.nombre}")

            # Lógica de Partición: Si queda pendiente
            if cant_a_entregar < cant_solicitada:
                if not orden_hija:
                    # Crear la cabecera de la hija una sola vez
                    # Determinamos la secuencia: madre.hijas.count() + 1
                    parent = ov.parent_orden if ov.parent_orden else ov
                    nueva_secuencia = parent.hijas.count() + 1
                    
                    orden_hija = OrdenVenta.objects.create(
                        pedido_origen=ov.pedido_origen,
                        cliente=ov.cliente,
                        vendedor=ov.vendedor,
                        empresa=ov.empresa,
                        estado='aprobado', # Lista para surtir el resto
                        parent_orden=parent,
                        secuencia=nueva_secuencia,
                        direccion_envio=ov.direccion_envio,
                        contacto_envio=ov.contacto_envio,
                        notas_envio=ov.notas_envio,
                        quien_recibe=ov.quien_recibe,
                        telefono_recibe=ov.telefono_recibe
                    )
                
                # Crear detalle en la hija con el pendiente
                DetalleOrdenVenta.objects.create(
                    orden_venta=orden_hija,
                    producto=producto,
                    cantidad=cant_solicitada - cant_a_entregar,
                    precio_unitario=det.precio_unitario
                )
                
                # Ajustar la orden actual con lo que realmente se entrega
                det.cantidad = cant_a_entregar
                det.save()

            # 2. Procesar Salida de Almacén (Solo si se entrega algo)
            if cant_a_entregar > 0 and producto.tipo != 'servicio':
                extra_ids = request.POST.getlist(f'extra_id_{det.id}[]')
                
                # Bloqueo de stock
                inv = Inventario.objects.select_for_update().get(almacen=almacen, producto=producto)
                if inv.cantidad < cant_a_entregar:
                    raise ValueError(f"Stock insuficiente para {producto.nombre} en {almacen.nombre}. Disponible: {inv.cantidad}, Requerido: {cant_a_entregar}")
                
                # Restar stock y reserva
                quitar_reserva = min(cant_a_entregar, inv.reservado)
                inv.cantidad = F('cantidad') - cant_a_entregar
                inv.reservado = F('reservado') - quitar_reserva
                inv.save()
                
                # Procesar Lotes/Series si aplica
                lote_ref, serie_ref = None, None
                if extra_ids:
                    piezas_por_asignar = cant_a_entregar
                    for eid in extra_ids:
                        if piezas_por_asignar <= 0: break
                        extra = DetalleRecepcionExtra.objects.get(id=eid, almacen=almacen)
                        if extra.tipo == 'serie':
                            extra.almacen = None # Sale de almacén
                            extra.save()
                            serie_ref = extra.serie # Nota: Solo guarda el último para el Kardex general
                            piezas_por_asignar -= 1
                        else:
                            # Lote
                            cantidad_lote_disponible = extra.cantidad_lote
                            a_quitar_de_lote = min(piezas_por_asignar, cantidad_lote_disponible)
                            
                            extra.cantidad_lote = F('cantidad_lote') - a_quitar_de_lote
                            extra.save()
                            lote_ref = extra.lote
                            piezas_por_asignar -= a_quitar_de_lote
                
                # Registrar en Kardex
                Kardex.objects.create(
                    empresa=empresa_actual, producto=producto, almacen=almacen,
                    tipo_movimiento='salida', cantidad=cant_a_entregar,
                    stock_anterior=inv.cantidad + cant_a_entregar, # Refrescamos mentalmente
                    stock_nuevo=inv.cantidad,
                    referencia=f"{ov.folio_display}", 
                    lote=lote_ref, serie=serie_ref,
                    usuario=request.user
                )
            
            # Si se entregó 0 y no se ha creado hija, hay que forzar creación de hija para no perder la partida
            elif cant_a_entregar == 0 and not orden_hija:
                # (Mismo bloque de creación de hija que arriba)
                parent = ov.parent_orden if ov.parent_orden else ov
                nueva_secuencia = parent.hijas.count() + 1
                orden_hija = OrdenVenta.objects.create(
                    pedido_origen=ov.pedido_origen, cliente=ov.cliente, vendedor=ov.vendedor,
                    empresa=ov.empresa, estado='aprobado', parent_orden=parent, secuencia=nueva_secuencia,
                    direccion_envio=ov.direccion_envio, contacto_envio=ov.contacto_envio
                )
                DetalleOrdenVenta.objects.create(
                    orden_venta=orden_hija, producto=producto, cantidad=cant_solicitada, precio_unitario=det.precio_unitario
                )
                det.delete() # Se movió completa a la hija

        ov.estado = 'surtido'
        ov.estado_entrega = 'listo'
        ov.save()

        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'surtió la orden {ov.folio_display}',
            propietario=ov.vendedor
        )

        # Solo actualizar pedido si NO hay más órdenes pendientes para este pedido
        if ov.pedido_origen:
            ordenes_pendientes = OrdenVenta.objects.filter(pedido_origen=ov.pedido_origen).exclude(estado__in=['surtido', 'cancelado']).count()
            if ordenes_pendientes == 0:
                pedido = ov.pedido_origen
                pedido.estado = 'completo'
                pedido.save()

        msg = f'Orden {ov.folio_display} surtida correctamente.'
        if orden_hija:
            msg += f' Se creó la orden pendiente {orden_hija.folio_display}.'
            
        return JsonResponse({'success': True, 'message': msg})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_sales_permission('salidas', 'actualizar_entrega')
def actualizar_estado_entrega(request, ov_id):
    if request.method != 'POST':
        return redirect('dashboard_ventas')
    
    empresa_actual = get_empresa_actual(request)
    ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)
    nuevo_estado = request.POST.get('nuevo_estado')
    
    if nuevo_estado in ['transito', 'entregado']:
        ov.estado_entrega = nuevo_estado
        ov.save()
        
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'marcó como {ov.get_estado_entrega_display()} la orden {ov.folio_display}',
            propietario=ov.vendedor
        )
        
        messages.success(request, f"Estado de entrega actualizado a {ov.get_estado_entrega_display()}.")
    
    return redirect('dashboard_ventas')