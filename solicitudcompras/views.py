from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.db import transaction
from collections import defaultdict
from panel.models import Empresa
from pedidos.models import Pedido, DetallePedido
from .models import SolicitudCompra, DetalleSolicitudCompra
from core.models import Producto, DetalleReceta
from categorias.models import ListaPrecioCosto
from produccion.models import OrdenProduccion
from proveedores.models import Proveedor
from almacenes.models import Almacen
from preferencias.models import Moneda
from notificaciones.utils import crear_notificacion

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
from proveedores.models import Proveedor

@login_required(login_url='/login/')
def dashboard_solicitudcompras(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    folio_solicitud = request.GET.get('folio_solicitud', '')
    folio_cotizacion = request.GET.get('folio_cotizacion', '')
    folio_pedido = request.GET.get('folio_pedido', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    fecha_solicitud = request.GET.get('fecha_solicitud', '')
    estado = request.GET.get('estado', '')

    solicitudes = SolicitudCompra.objects.filter(empresa=empresa_actual).select_related('pedido_origen', 'solicitante').order_by('-fecha_creacion')

    if q:
        solicitudes = solicitudes.filter(
            Q(id__icontains=q) |
            Q(pedido_origen__id__icontains=q) |
            Q(pedido_origen__cotizacion_origen_id__icontains=q) |
            Q(solicitante__username__icontains=q) |
            Q(estado__icontains=q) |
            Q(notas__icontains=q) |
            Q(detalles__producto__nombre__icontains=q)
        ).distinct()
    
    if folio_solicitud:
        clean_sol = folio_solicitud.upper().replace('SOL-', '').replace('SOL', '').strip()
        solicitudes = solicitudes.filter(id__icontains=clean_sol)
    if folio_cotizacion:
        clean_cot = folio_cotizacion.upper().replace('COT-', '').replace('COT', '').strip()
        solicitudes = solicitudes.filter(pedido_origen__cotizacion_origen_id__icontains=clean_cot)
    if folio_pedido:
        clean_ped = folio_pedido.upper().replace('PED-', '').replace('PED', '').strip()
        solicitudes = solicitudes.filter(pedido_origen__id__icontains=clean_ped)
    if proveedor_id and proveedor_id != 'all':
        solicitudes = solicitudes.filter(detalles__proveedor_id=proveedor_id).distinct()
    if fecha_solicitud:
        try:
            solicitudes = solicitudes.filter(fecha_creacion__date=fecha_solicitud)
        except:
            pass
    if estado:
        solicitudes = solicitudes.filter(estado=estado)

    # Para el buscador visual de proveedor
    proveedor_nombre_display = ""
    if proveedor_id and proveedor_id != 'all':
        try:
            p_obj = Proveedor.objects.get(id=proveedor_id, empresa=empresa_actual)
            proveedor_nombre_display = p_obj.razon_social
        except:
            pass

    filtros = {
        'q': q,
        'folio_solicitud': folio_solicitud,
        'folio_cotizacion': folio_cotizacion,
        'folio_pedido': folio_pedido,
        'proveedor_id': proveedor_id,
        'proveedor_nombre': proveedor_nombre_display,
        'fecha_solicitud': fecha_solicitud,
        'estado': estado
    }
    # --- FIN LÓGICA DE FILTRADO ---
    
    # --- NUEVO: Obtener catálogos para los selects del modal ---
    proveedores_activos = Proveedor.objects.filter(empresa=empresa_actual, estado='activo')
    todos_los_proveedores = Proveedor.objects.filter(empresa=empresa_actual)
    lista_almacenes = Almacen.objects.filter(empresa=empresa_actual).values('id', 'nombre')
    lista_monedas = Moneda.objects.filter(empresa=empresa_actual).values('id', 'siglas', 'simbolo')
    lista_productos = Producto.objects.filter(empresa=empresa_actual).values('id', 'nombre', 'precio_costo')
    listas_costos = ListaPrecioCosto.objects.filter(empresa=empresa_actual, tipo='costo')
    
    contexto = {
        'solicitudes': solicitudes,
        'proveedores': proveedores_activos,
        'todos_los_proveedores': todos_los_proveedores,
        'almacenes': list(lista_almacenes),
        'monedas': list(lista_monedas),
        'productos': list(lista_productos),
        'listas_costos': listas_costos,
        'filtros': filtros,
        'section': 'solicitudcompras'
    }
    return render(request, 'dashboard_solicitudcompras.html', contexto)

from preferencias.permissions import require_sales_permission

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'solicitar')
def crear_solicitud_desde_pedido(request, detalle_id):
    empresa_actual = get_empresa_actual(request)
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    
    # Seguridad: Verificar que el pedido pertenezca a la empresa
    pedido = get_object_or_404(Pedido, id=detalle.pedido.id, empresa=empresa_actual)
    producto = detalle.producto

    # Verificamos si YA existe una solicitud abierta para este pedido para agrupar
    solicitud_existente = SolicitudCompra.objects.filter(
        pedido_origen=pedido, 
        estado='borrador', 
        empresa=empresa_actual
    ).first()

    if solicitud_existente:
        target_solicitud = solicitud_existente
    else:
        target_solicitud = SolicitudCompra.objects.create(
            pedido_origen=pedido, 
            solicitante=request.user, 
            empresa=empresa_actual, 
            estado='borrador'
        )

    # --- INTELIGENCIA: ¿ES PRODUCCIÓN? ---
    if producto.tipo_abastecimiento == 'produccion':
        # 1. Crear la Orden de Producción vinculada al pedido (En Borrador)
        op = OrdenProduccion.objects.create(
            empresa=empresa_actual,
            producto=producto,
            cantidad=detalle.cantidad_solicitada,
            pedido_origen=pedido,
            solicitante=request.user,
            almacen=Almacen.objects.filter(empresa=empresa_actual).first(), # Almacen por defecto
            estado='borrador',
            notas=f"Generada desde Pedido #{pedido.id} (Partida Individual)"
        )

        # 2. Obtener Receta y copiar a DetalleOrdenProduccion
        receta = DetalleReceta.objects.filter(producto_padre=producto)
        
        if not receta.exists():
            messages.error(request, f'El producto "{producto.nombre}" es de producción pero NO TIENE RECETA. No se puede generar solicitud.')
            return redirect('dashboard_pedidos')

        # 3. Calcular necesidades y crear detalles
        items_a_solicitar = []
        for item in receta:
            # Copiar a la tabla de la orden específica
            from produccion.models import DetalleOrdenProduccion
            DetalleOrdenProduccion.objects.create(
                orden_produccion=op,
                producto=item.componente,
                cantidad=item.cantidad * detalle.cantidad_solicitada
            )

            componente = item.componente
            cantidad_necesaria = item.cantidad * detalle.cantidad_solicitada
            
            stock_componente = componente.stock_disponible
            
            if stock_componente < cantidad_necesaria:
                faltante = cantidad_necesaria - stock_componente
                items_a_solicitar.append({
                    'producto': componente,
                    'cantidad': faltante,
                    'costo': componente.precio_costo
                })

        if not items_a_solicitar:
            messages.info(request, f'Para producir {producto.nombre} ya tienes todos los componentes necesarios en stock. No se generó solicitud.')
            # Podríamos cambiar el estado a 'pendiente' si quisieras, pero lo dejamos así.
            return redirect('dashboard_pedidos')

        # 3. Crear Detalles en la Solicitud
        for item in items_a_solicitar:
            # Verificar si ya existe ese componente en la solicitud actual para no duplicar
            det_existente = DetalleSolicitudCompra.objects.filter(
                solicitud=target_solicitud,
                producto=item['producto']
            ).first()
            
            if det_existente:
                det_existente.cantidad_solicitada += item['cantidad']
                det_existente.save()
            else:
                DetalleSolicitudCompra.objects.create(
                    solicitud=target_solicitud,
                    producto=item['producto'],
                    cantidad_solicitada=item['cantidad'],
                    costo_unitario=item['costo'],
                    detalle_pedido_origen=detalle # Vinculamos al pedido original
                )
        
        detalle.estado_linea = 'en_proceso' # Marcamos que ya se inició el trámite
        detalle.save()
        
        messages.success(request, f'Solicitud de componentes para "{producto.nombre}" generada correctamente.')

    else:
        # --- CASO NORMAL: COMPRAR EL PRODUCTO DIRECTO ---
        DetalleSolicitudCompra.objects.create(
            solicitud=target_solicitud,
            producto=producto,
            cantidad_solicitada=detalle.cantidad_solicitada,
            costo_unitario=producto.precio_costo,
            detalle_pedido_origen=detalle
        )
        
        detalle.estado_linea = 'en_proceso'
        detalle.save()
        
        messages.success(request, f'Producto agregado a la Solicitud #{target_solicitud.id}.')

    return redirect('dashboard_solicitudcompras')

def obtener_solicitud_json(request, solicitud_id):
    """Devuelve los datos de una solicitud específica para el Modal"""
    try:
        empresa_actual = get_empresa_actual(request) 
        solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id, empresa=empresa_actual)
        
        # Convertimos el modelo principal a diccionario
        data = model_to_dict(solicitud)
        
        # --- Construir el objeto anidado del Pedido ---
        if solicitud.pedido_origen:
            data['pedido_origen'] = {
                'id': solicitud.pedido_origen.id,
                'cotizacion_origen_id': solicitud.pedido_origen.cotizacion_origen_id,
                'cliente': {
                    'nombre': solicitud.pedido_origen.cliente.nombre,
                    'apellidos': solicitud.pedido_origen.cliente.apellidos,
                    'razon_social': solicitud.pedido_origen.cliente.razon_social,
                    'nombre_completo': solicitud.pedido_origen.cliente.nombre_completo
                }
            }
        else:
            data['pedido_origen'] = None

        # --- CORRECCIÓN AQUÍ: Usar 'cantidad_solicitada' en lugar de 'cantidad' ---
        detalles_list = []
        for det in solicitud.detalles.all():
            detalles_list.append({
                'id': det.id,
                'producto_id': det.producto.id,
                'producto_nombre': det.producto.nombre,
                'cantidad': det.cantidad_solicitada,
                'proveedor_id': det.proveedor.id if det.proveedor else None,
                'proveedor_nombre': det.proveedor.razon_social if det.proveedor else 'No asignado',
                'sucursal_id': det.sucursal.id if det.sucursal else None,
                'sucursal_nombre': det.sucursal.nombre if det.sucursal else '',
                'costo_unitario': str(det.costo_unitario),
                'almacen_id': det.almacen.id if det.almacen else None,
                'almacen_nombre': det.almacen.nombre if det.almacen else 'No asignado',
                'moneda_id': det.moneda.id if det.moneda else None,
                'moneda_siglas': det.moneda.siglas if det.moneda else 'MXN',
                'lista_id': det.lista.id if det.lista else None,
                'detalle_pedido_origen_id': det.detalle_pedido_origen.id if det.detalle_pedido_origen else None
            })
        data['detalles'] = detalles_list
        data['solicitante_nombre'] = solicitud.solicitante.username.split('@')[0] if solicitud.solicitante else 'Sistema'
        data['fecha_creacion'] = solicitud.fecha_creacion.strftime('%d/%m/%Y %H:%M')
        data['estado_display'] = solicitud.get_estado_display()

        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required(login_url='/login/')
def actualizar_solicitud(request, solicitud_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id, empresa=empresa_actual)

            # SEGURIDAD: Solo editar si está en borrador
            if solicitud.estado != 'borrador':
                return JsonResponse({'success': False, 'error': 'Solo se pueden editar solicitudes en Borrador.'})

            solicitud.notas = request.POST.get('notas', '')
            solicitud.save()

            # Borrar y recrear detalles (simplificación para este ejemplo)
            solicitud.detalles.all().delete()

            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            proveedores_ids = request.POST.getlist('proveedor_id[]')
            sucursales_ids = request.POST.getlist('sucursal_id[]') # <--- NUEVO
            costos = request.POST.getlist('costo_unitario[]')
            almacenes_ids = request.POST.getlist('almacen_id[]')
            monedas_ids = request.POST.getlist('moneda_id[]') 
            listas_ids = request.POST.getlist('lista_id[]')
            pedidos_det_ids = request.POST.getlist('pedido_det_id[]') 

            # Zip de todas las listas
            for p_id, cant, prov_id, suc_id, cost, alm_id, mon_id, p_det_id, l_id in zip(productos_ids, cantidades, proveedores_ids, sucursales_ids, costos, almacenes_ids, monedas_ids, pedidos_det_ids, listas_ids):
                if p_id and p_id != '':
                    DetalleSolicitudCompra.objects.create(
                        solicitud=solicitud,
                        producto_id=p_id,
                        cantidad_solicitada=cant,
                        proveedor_id=prov_id if prov_id else None,
                        sucursal_id=suc_id if (suc_id and suc_id != '') else None,
                        costo_unitario=cost,
                        almacen_id=alm_id if alm_id else None,
                        moneda_id=mon_id if mon_id else None,
                        lista_id=l_id if l_id else None,
                        detalle_pedido_origen_id=p_det_id if p_det_id else None 
                    )
            
            messages.success(request, f'Solicitud #{solicitud.id} actualizada.')
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
@transaction.atomic
def crear_solicitud_manual(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no detectada'})

            notas = request.POST.get('notas', '')
            solicitud = SolicitudCompra.objects.create(
                solicitante=request.user,
                empresa=empresa_actual,
                estado='borrador',
                notas=notas
            )

            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            proveedores_ids = request.POST.getlist('proveedor_id[]')
            sucursales_ids = request.POST.getlist('sucursal_id[]')
            costos = request.POST.getlist('costo_unitario[]')
            almacenes_ids = request.POST.getlist('almacen_id[]')
            monedas_ids = request.POST.getlist('moneda_id[]')
            listas_ids = request.POST.getlist('lista_id[]')

            count = 0
            for p_id, cant, prov_id, suc_id, cost, alm_id, mon_id, l_id in zip(productos_ids, cantidades, proveedores_ids, sucursales_ids, costos, almacenes_ids, monedas_ids, listas_ids):
                if p_id and p_id != '':
                    DetalleSolicitudCompra.objects.create(
                        solicitud=solicitud,
                        producto_id=p_id,
                        cantidad_solicitada=cant,
                        proveedor_id=prov_id if prov_id else None,
                        sucursal_id=suc_id if (suc_id and suc_id != '') else None,
                        costo_unitario=cost,
                        almacen_id=alm_id if alm_id else None,
                        moneda_id=mon_id if mon_id else None,
                        lista_id=l_id if l_id else None
                    )
                    count += 1
            
            if count == 0:
                raise ValueError("Debes agregar al menos un producto a la solicitud.")

            messages.success(request, f'Solicitud #{solicitud.id} creada correctamente.')
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
@transaction.atomic 
def autorizar_solicitud(request, solicitud_id):
    empresa_actual = get_empresa_actual(request)
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id, empresa=empresa_actual)

    if solicitud.estado != 'borrador':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Solo se pueden autorizar solicitudes en estado Borrador.'})
        messages.warning(request, 'Solo se pueden autorizar solicitudes en estado Borrador.')
        return redirect('dashboard_solicitudcompras')

    # 1. Validar que todas las partidas tengan proveedor, almacén y moneda
    for det in solicitud.detalles.all():
        if not det.proveedor or not det.almacen or not det.moneda:
            error_msg = f'Faltan datos (Proveedor, Almacén o Moneda) en el producto {det.producto.nombre}.'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('dashboard_solicitudcompras')

    # 2. Agrupar ítems por (Proveedor, Sucursal, Moneda, Almacén)
    items_agrupados = defaultdict(list)
    for det in solicitud.detalles.all():
        llave = (det.proveedor, det.sucursal, det.moneda, det.almacen)
        items_agrupados[llave].append(det)

    # 3. Si es una previsualización (AJAX)
    if request.GET.get('preview') == '1':
        desglose = []
        # Agrupamos por proveedor para el mensaje de alerta
        conteo_por_proveedor = defaultdict(int)
        for (prov, suc, mon, alm) in items_agrupados.keys():
            conteo_por_proveedor[prov.razon_social] += 1

        for prov_nombre, total_oc in conteo_por_proveedor.items():
            desglose.append({
                'proveedor': prov_nombre,
                'total_oc': total_oc
            })

        return JsonResponse({
            'success': True,
            'total_ordenes': len(items_agrupados),
            'desglose': desglose
        })

    # 4. Procesar creación física (POST)
    if request.method == 'POST':
        from compras.models import OrdenCompra, DetalleCompra

        ordenes_creadas_count = 0
        for (proveedor, sucursal, moneda, almacen), lista_detalles in items_agrupados.items():
            nueva_oc = OrdenCompra.objects.create(
                proveedor=proveedor,
                sucursal=sucursal,
                usuario=request.user,
                empresa=empresa_actual,
                estado='borrador',
                almacen_destino=almacen,
                moneda=moneda,
                tipo_cambio=moneda.factor if moneda else 1.0000,
                notas=f"Generada desde Solicitud #{solicitud.id}.",
                solicitud_origen=solicitud 
            )

            for det_solicitud in lista_detalles:
                DetalleCompra.objects.create(
                    orden_compra=nueva_oc,
                    producto=det_solicitud.producto,
                    cantidad=det_solicitud.cantidad_solicitada,
                    precio_costo=det_solicitud.costo_unitario,
                    detalle_pedido_origen=det_solicitud.detalle_pedido_origen
                )

                if det_solicitud.detalle_pedido_origen:
                    det_solicitud.detalle_pedido_origen.estado_linea = 'comprado'
                    det_solicitud.detalle_pedido_origen.save()

            ordenes_creadas_count += 1

        solicitud.estado = 'atendida'
        solicitud.save()

        # NOTIFICACIÓN
        crear_notificacion(
            empresa=empresa_actual,
            mensaje=f"La Solicitud #{solicitud.id} ha sido autorizada y se generaron {ordenes_creadas_count} órdenes de compra.",
            actor=request.user,
            propietario=solicitud.solicitante
        )

        msg = f'Solicitud autorizada. Se generaron {ordenes_creadas_count} órdenes de compra.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': msg})

        messages.success(request, msg)
        return redirect('dashboard_solicitudcompras')

    return redirect('dashboard_solicitudcompras')

@login_required
def imprimir_solicitud(request, pk):
    """Genera la vista para impresión de solicitud de compra (PDF)"""
    empresa_actual = get_empresa_actual(request)
    solicitud = get_object_or_404(SolicitudCompra, id=pk, empresa=empresa_actual)

    # Limpiar nombre del solicitante
    solicitante_nombre = solicitud.solicitante.get_full_name()
    if not solicitante_nombre:
        solicitante_nombre = solicitud.solicitante.username.split('@')[0]

    context = {
        'solicitud': solicitud,
        'empresa': empresa_actual,
        'solicitante_nombre': solicitante_nombre,
    }
    return render(request, 'solicitudcompras/imprimir_solicitud.html', context)
