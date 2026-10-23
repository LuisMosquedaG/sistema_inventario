from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from decimal import Decimal
import json
import openpyxl
from datetime import datetime
from .models import Recepcion, DetalleRecepcion, DetalleRecepcionExtra, DevolucionRecepcion, DetalleDevolucionRecepcion
from .services import procesar_recepcion_servicio, recalcular_estado_orden_compra
from compras.models import OrdenCompra, DetalleCompra
from core.models import Producto, Transaccion
from almacenes.models import Almacen, Inventario
from panel.models import Empresa
from notificaciones.utils import crear_notificacion
from preferencias.permissions import require_purchase_permission, get_granular_purchase_permissions

@login_required(login_url='/login/')
@require_purchase_permission('recepciones', 'crear')
def descargar_plantilla_recepciones(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla Recepciones"
    
    # Encabezados: Referencia ayuda a agrupar productos en una misma recepción
    headers = [
        'Referencia (Ej: REC-001)', 'Orden Compra (ID)', 'Almacen (Nombre o ID)',
        'Fecha (YYYY-MM-DD)', 'Factura', 'Producto (Nombre o ID)', 'Cantidad Recibida'
    ]
    
    ws.append(headers)
    
    for col_idx, header in enumerate(headers, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = len(header) + 5

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Plantilla_Recepciones.xlsx"'
    wb.save(response)
    return response

@login_required(login_url='/login/')
@require_purchase_permission('recepciones', 'crear', json_response=True)
def importar_recepciones_ajax(request):
    if request.method == 'POST' and request.FILES.get('archivo_recepciones'):
        empresa_actual = get_empresa_actual(request)
        excel_file = request.FILES['archivo_recepciones']
        
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            
            if len(rows) < 2:
                return JsonResponse({'success': False, 'error': 'El archivo está vacío.'})
            
            data_rows = rows[1:]
            
            # Agrupar por Referencia
            recepciones_data = {}
            for idx, row in enumerate(data_rows, start=2):
                if not any(row): continue
                ref = str(row[0] or f"TEMP-{idx}").strip()
                if ref not in recepciones_data:
                    recepciones_data[ref] = {
                        'oc_input': str(row[1] or '').strip(),
                        'alm_input': str(row[2] or '').strip(),
                        'fecha_raw': row[3],
                        'factura': str(row[4] or '').strip(),
                        'items': []
                    }
                recepciones_data[ref]['items'].append({
                    'prod_input': str(row[5] or '').strip(),
                    'cantidad': row[6] or 0
                })

            creadas = 0
            errores = []
            
            with transaction.atomic():
                # Obtener sucursal de la sesión
                sucursal_obj = None
                sucursal_id = request.session.get('sucursal_id')
                if sucursal_id:
                    from preferencias.models import Sucursal
                    try:
                        sucursal_obj = Sucursal.objects.get(id=sucursal_id, empresa=empresa_actual)
                    except Sucursal.DoesNotExist:
                        pass

                for ref, data in recepciones_data.items():
                    try:
                        # Buscar Orden de Compra
                        orden = None
                        if data['oc_input'].isdigit():
                            orden = OrdenCompra.objects.filter(id=int(data['oc_input']), empresa=empresa_actual).first()
                        if not orden:
                            errores.append(f"Ref {ref}: No se encontró la OC '{data['oc_input']}'.")
                            continue

                        # Buscar Almacén
                        almacen = None
                        if data['alm_input'].isdigit():
                            almacen = Almacen.objects.filter(id=int(data['alm_input']), empresa=empresa_actual).first()
                        if not almacen:
                            almacen = Almacen.objects.filter(nombre__icontains=data['alm_input'], empresa=empresa_actual).first()
                        
                        if not almacen:
                            errores.append(f"Ref {ref}: No se encontró el almacén '{data['alm_input']}'.")
                            continue

                        # Procesar Fecha
                        fecha_rec = timezone.now().date()
                        if data['fecha_raw']:
                            if isinstance(data['fecha_raw'], datetime):
                                fecha_rec = data['fecha_raw'].date()
                            elif isinstance(data['fecha_raw'], str):
                                try: fecha_rec = datetime.strptime(data['fecha_raw'], '%Y-%m-%d').date()
                                except: pass

                        # Crear Recepción
                        recepcion = Recepcion.objects.create(
                            empresa=empresa_actual,
                            orden_compra=orden,
                            almacen=almacen,
                            sucursal=orden.sucursal_empresa or sucursal_obj,
                            moneda=orden.moneda,
                            tipo_cambio=orden.tipo_cambio,
                            fecha=fecha_rec,
                            factura=data['factura'],
                            estado='completada'
                        )

                        # Crear Detalles y registrar en Inventario / Kardex
                        detalles_creados = 0
                        for item in data['items']:
                            from core.models import Producto
                            producto = None
                            if item['prod_input'].isdigit():
                                producto = Producto.objects.filter(id=int(item['prod_input']), empresa=empresa_actual).first()
                            if not producto:
                                producto = Producto.objects.filter(nombre__icontains=item['prod_input'], empresa=empresa_actual).first()
                            
                            cant_rec = int(item['cantidad'] or 0)
                            if producto and cant_rec > 0:
                                # Buscar el detalle de compra correspondiente para vincular
                                det_compra = DetalleCompra.objects.filter(orden_compra=orden, producto=producto).first()
                                costo_unit = Decimal(str(det_compra.precio_costo if det_compra else (producto.precio_costo or 0)))
                                
                                DetalleRecepcion.objects.create(
                                    recepcion=recepcion,
                                    producto=producto,
                                    detalle_compra=det_compra,
                                    cantidad_recibida=cant_rec,
                                    costo_unitario=costo_unit
                                )
                                detalles_creados += 1

                                if producto.tipo != 'servicio':
                                    tc_aplicar = Decimal(str(orden.tipo_cambio or '1.0000'))
                                    costo_pesos = costo_unit * tc_aplicar
                                    Transaccion.objects.create(
                                        producto=producto,
                                        almacen=almacen,
                                        tipo='compra',
                                        cantidad=cant_rec,
                                        total=costo_pesos * Decimal(str(cant_rec)),
                                        empresa=empresa_actual,
                                        usuario=request.user,
                                        referencia=f"REC-{recepcion.id:04d}",
                                        estado='recibida'
                                    )
                                else:
                                    tc_aplicar = Decimal(str(orden.tipo_cambio or '1.0000'))
                                    costo_pesos = costo_unit * tc_aplicar
                                    producto.ultimo_costo = costo_pesos
                                    producto.precio_costo = costo_pesos
                                    producto.costo_promedio = costo_pesos
                                    producto.save(update_fields=['ultimo_costo', 'precio_costo', 'costo_promedio'])

                        if detalles_creados == 0:
                            recepcion.delete()
                            errores.append(f"Ref {ref}: No se encontraron artículos válidos con cantidad mayor a 0.")
                            continue

                        # Actualizar estado de la Orden de Compra
                        recalcular_estado_orden_compra(orden)
                        
                        creadas += 1
                    except Exception as e:
                        errores.append(f"Ref {ref}: {str(e)}")
            
            if creadas == 0 and errores:
                return JsonResponse({'success': False, 'error': f"Error: {errores[0]}"})

            msg = f'Importación exitosa. {creadas} recepciones creadas.'
            if errores: msg += f' ({len(errores)} errores)'
            return JsonResponse({'success': True, 'message': msg})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Solicitud inválida.'})

@login_required(login_url='/login/')
@require_purchase_permission('recepciones', 'ver')
def exportar_recepciones_excel(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return HttpResponse("No autorizado", status=403)

    # --- Filtrado ---
    from django.db.models import Q
    q = request.GET.get('q', '')
    folio_recepcion = request.GET.get('folio_recepcion', '')
    folio_oc = request.GET.get('folio_oc', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    almacen_id = request.GET.get('almacen_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')
    sucursal_id_filtro = request.GET.get('sucursal', '')

    recepciones = Recepcion.objects.filter(empresa=empresa_actual).select_related('orden_compra', 'almacen', 'orden_compra__proveedor', 'sucursal').order_by('-fecha', '-id')

    if q:
        recepciones = recepciones.filter(
            Q(id__icontains=q) | Q(orden_compra__id__icontains=q) |
            Q(orden_compra__proveedor__razon_social__icontains=q) | Q(factura__icontains=q)
        )
    if folio_recepcion:
        recepciones = recepciones.filter(id__icontains=folio_recepcion.replace('REC-', ''))
    if folio_oc:
        recepciones = recepciones.filter(orden_compra__id__icontains=folio_oc.replace('OC-', ''))
    if proveedor_id and proveedor_id != 'all':
        recepciones = recepciones.filter(orden_compra__proveedor_id=proveedor_id)
    if almacen_id:
        recepciones = recepciones.filter(almacen_id=almacen_id)
    if fecha:
        try: recepciones = recepciones.filter(fecha=fecha)
        except: pass
    if estado:
        recepciones = recepciones.filter(estado=estado)
    if sucursal_id_filtro:
        recepciones = recepciones.filter(sucursal_id=sucursal_id_filtro)

    # --- Generar Excel ---
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte de Recepciones"

    headers = [
        'ID', 'Folio', 'OC Origen', 'Proveedor', 'Almacén', 'Fecha', 'Factura', 'Estado', 'Total'
    ]
    ws.append(headers)

    for r in recepciones:
        ws.append([
            r.id, f"REC-{r.id:04d}", f"OC-{r.orden_compra.id:04d}",
            r.orden_compra.proveedor.razon_social, r.almacen.nombre,
            r.fecha.strftime('%Y-%m-%d'), r.factura, r.get_estado_display(), r.total
        ])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        ws.column_dimensions[column].width = max_length + 2

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Recepciones_{empresa_actual.nombre}.xlsx"'
    wb.save(response)
    return response

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
from proveedores.models import Proveedor

@login_required
@require_purchase_permission('recepciones', 'ver')
def dashboard_recepciones(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    folio_recepcion = request.GET.get('folio_recepcion', '')
    folio_oc = request.GET.get('folio_oc', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    almacen_id = request.GET.get('almacen_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')
    sucursal_id_filtro = request.GET.get('sucursal', '')

    recepciones_list = Recepcion.objects.filter(empresa=empresa_actual).select_related('orden_compra', 'almacen', 'orden_compra__proveedor', 'sucursal').order_by('-fecha', '-id')

    if q:
        recepciones_list = recepciones_list.filter(
            Q(id__icontains=q) |
            Q(orden_compra__id__icontains=q) |
            Q(orden_compra__proveedor__razon_social__icontains=q) |
            Q(factura__icontains=q) |
            Q(pedimento__icontains=q) |
            Q(aduana__icontains=q)
        )
    if folio_recepcion:
        clean_rec = folio_recepcion.upper().replace('REC-', '').replace('REC', '').strip()
        recepciones_list = recepciones_list.filter(id__icontains=clean_rec)
    if folio_oc:
        clean_oc = folio_oc.upper().replace('OC-', '').replace('OC', '').strip()
        recepciones_list = recepciones_list.filter(orden_compra__id__icontains=clean_oc)
    if proveedor_id and proveedor_id != 'all':
        recepciones_list = recepciones_list.filter(orden_compra__proveedor_id=proveedor_id)
    if almacen_id:
        recepciones_list = recepciones_list.filter(almacen_id=almacen_id)
    if fecha:
        try:
            recepciones_list = recepciones_list.filter(fecha=fecha)
        except:
            pass
    if estado:
        recepciones_list = recepciones_list.filter(estado=estado)
    if sucursal_id_filtro:
        recepciones_list = recepciones_list.filter(sucursal_id=sucursal_id_filtro)

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
        'folio_recepcion': folio_recepcion,
        'folio_oc': folio_oc,
        'proveedor_id': proveedor_id,
        'proveedor_nombre': proveedor_nombre_display,
        'almacen_id': almacen_id,
        'fecha': fecha,
        'estado': estado,
        'sucursal': sucursal_id_filtro
    }
    # --- FIN LÓGICA DE FILTRADO ---
    from preferencias.models import Sucursal
    sucursales_lista = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    paginator = Paginator(recepciones_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    ordenes_aprobadas = OrdenCompra.objects.filter(
        empresa=empresa_actual,
        estado__in=['aprobada', 'parcial', 'borrador']
    )

    almacenes = Almacen.objects.filter(empresa=empresa_actual)
    todos_los_proveedores = Proveedor.objects.filter(empresa=empresa_actual)
    oc_preseleccionada = request.GET.get('oc_id')

    context = {
        'page_obj': page_obj,
        'ordenes_compra_aprobadas': ordenes_aprobadas,
        'almacenes': almacenes,
        'todos_los_proveedores': todos_los_proveedores,
        'oc_preseleccionada': oc_preseleccionada,
        'sucursales': sucursales_lista,
        'section': 'recepciones',
        'filtros': filtros
    }
    return render(request, 'dashboard_recepciones.html', context)


@login_required
@require_purchase_permission('recepciones', 'ver', json_response=True)
def obtener_items_orden_compra(request, oc_id):
    empresa_actual = get_empresa_actual(request)

    try:
        # Buscamos la orden de forma segura
        orden = OrdenCompra.objects.filter(id=oc_id, empresa=empresa_actual).first()

        if not orden:
            return JsonResponse({'error': 'La Orden de Compra no existe o no pertenece a tu empresa.'}, status=404)

        detalles = DetalleCompra.objects.filter(orden_compra=orden).order_by('id')

        # Preparamos el paquete de datos con moneda y tipo de cambio
        data = {
            'id': orden.id,
            'moneda': orden.moneda.siglas if (orden.moneda and orden.moneda.siglas) else 'MXN',
            'tipo_cambio': str(orden.tipo_cambio) if orden.tipo_cambio else '1.0000',
            'items': []
        }

        for det in detalles:
            # Sumamos lo recibido anteriormente menos devoluciones para saber cuánto falta
            total_recibido_bruto = DetalleRecepcion.objects.filter(
                detalle_compra=det
            ).exclude(recepcion__estado='cancelada').aggregate(total=Sum('cantidad_recibida'))['total'] or 0

            total_devuelto = DetalleDevolucionRecepcion.objects.filter(
                detalle_recepcion__detalle_compra=det,
                devolucion__estado='completada'
            ).exclude(detalle_recepcion__recepcion__estado='cancelada').aggregate(total=Sum('cantidad_devuelta'))['total'] or 0

            total_recibido = max(0, total_recibido_bruto - total_devuelto)

            data['items'].append({
                'id': det.id,
                'nombre': det.producto.nombre,
                'cant_ordenada': det.cantidad,
                'cant_recibida_anterior': total_recibido,
                'costo': float(det.precio_costo),
                'iva_porcentaje': float(det.producto.iva or 0),
                'maneja_lote': det.producto.maneja_lote,
                'maneja_serie': det.producto.maneja_serie,
                'maneja_caducidad': det.producto.maneja_caducidad,
            })

        return JsonResponse(data)

    except Exception as e:
        print(f"Error en obtener_items_orden_compra: {str(e)}")
        return JsonResponse({'error': 'Error interno al cargar artículos.'}, status=500)

@login_required
@require_purchase_permission('recepciones', 'crear', json_response=True)
@transaction.atomic
def crear_recepcion(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no detectada.'})

            recepcion = procesar_recepcion_servicio(
                data_post=request.POST,
                empresa_actual=empresa_actual,
                usuario=request.user
            )

            crear_notificacion(
                empresa=empresa_actual,
                actor=request.user,
                mensaje=f'procesó recepción REC-{recepcion.id:04d} para OC-{recepcion.orden_compra.id:04d}',
                propietario=recepcion.orden_compra.usuario
            )

            return JsonResponse({'success': True, 'message': 'Recepción procesada exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def cambiar_estado_recepcion(request, recepcion_id):
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado == 'cancelada':
            return cancelar_recepcion(request, recepcion_id)
        perms = get_granular_purchase_permissions(request).get('recepciones', {})
        if not perms.get('crear'):
            return JsonResponse({'success': False, 'error': 'No tienes permisos para actualizar recepciones.'}, status=403)
        empresa_actual = get_empresa_actual(request)
        recepcion = get_object_or_404(Recepcion, id=recepcion_id, empresa=empresa_actual)

        if nuevo_estado == 'completada':
            recepcion.estado = nuevo_estado
            recepcion.save()
            return JsonResponse({'success': True, 'message': 'Estado actualizado'})
    return JsonResponse({'success': False, 'error': 'Error'})

@login_required
@require_purchase_permission('recepciones', 'ver', json_response=True)
def api_detalle_recepcion(request, recepcion_id):
    try:
        empresa_actual = get_empresa_actual(request)
        rec = get_object_or_404(Recepcion, id=recepcion_id, empresa=empresa_actual)
        oc = rec.orden_compra

        data = {
            'titulo': 'Detalle Recepción',
            'id': rec.id,
            'folio': f"REC-{rec.id:04d}",
            'fecha': rec.fecha.strftime('%d/%m/%Y') if rec.fecha else '-',
            'fecha_comprobante': rec.fecha_comprobante.strftime('%d/%m/%Y') if rec.fecha_comprobante else '-',
            'estado': rec.estado.upper(),
            'proveedor': str(oc.proveedor) if oc else "Directo / Sin OC",
            'sucursal': oc.sucursal.nombre if (oc and oc.sucursal) else 'Matriz / Principal',
            'almacen': str(rec.almacen),
            'factura': rec.factura or '-',
            'total': float(rec.total),
            'pedimento': rec.pedimento or '-',
            'aduana': rec.aduana or '-',
            'fecha_pedimento': rec.fecha_pedimento.strftime('%d/%m/%Y') if rec.fecha_pedimento else '-',
            'oc_id': oc.id if oc else None,
            'oc_folio': f"OC-{oc.id:04d}" if oc else '-',
            'oc_fecha': oc.fecha.strftime('%d/%m/%Y') if (oc and oc.fecha) else '-',
            'detalles': [
                {
                    'id': d.id,
                    'producto': d.producto.nombre,
                    'cant': d.cantidad_recibida,
                    'cant_devuelta': d.cantidad_devuelta,
                    'cant_disponible': d.cantidad_disponible_devolver,
                    'precio': float(d.costo_unitario),
                    'iva_porcentaje': float(d.producto.iva or 0),
                    'subtotal': float(d.subtotal),
                    'iva_monto': float(d.iva_monto),
                    'total': float(d.total),
                    'maneja_lote': bool(d.producto.maneja_lote),
                    'maneja_serie': bool(d.producto.maneja_serie),
                    'maneja_caducidad': bool(d.producto.maneja_caducidad),
                    'extras': [
                        {
                            'id': e.id,
                            'tipo': e.tipo,
                            'lote': e.lote or '',
                            'serie': e.serie or '',
                            'fecha_caducidad': e.fecha_caducidad.strftime('%d/%m/%Y') if e.fecha_caducidad else '',
                            'en_almacen': bool(e.almacen_id == rec.almacen_id),
                            'disponible': (1 if e.tipo == 'serie' else int(e.cantidad_lote or 0)) if e.almacen_id == rec.almacen_id else 0,
                        }
                        for e in d.extras.all().order_by('id')
                    ]
                } for d in rec.detalles.select_related('producto').prefetch_related('extras').all()
            ],
            'subtotal_total': float(rec.calcular_subtotal),
            'iva_total': float(rec.calcular_iva),
            'gran_total': float(rec.calcular_total)
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

@login_required
@require_purchase_permission('recepciones', 'cancelar', json_response=True)
@transaction.atomic
def cancelar_recepcion(request, recepcion_id):
    try:
        empresa_actual = get_empresa_actual(request)
        recepcion = get_object_or_404(Recepcion, id=recepcion_id, empresa=empresa_actual)

        if recepcion.estado == 'cancelada':
            return JsonResponse({'success': False, 'error': 'La recepción ya está cancelada.'})

        orden_compra = recepcion.orden_compra
        almacen = recepcion.almacen

        for det in recepcion.detalles.all():
            producto = det.producto
            cant_restante_revertir = det.cantidad_disponible_devolver
            if producto.tipo != 'servicio' and cant_restante_revertir > 0:
                # Preparar datos de extras para revertir (lotes/series)
                extras_data = []
                restante_extra = cant_restante_revertir
                for extra in det.extras.all():
                    if restante_extra <= 0:
                        break
                    qty_tomar = 1 if extra.tipo == 'serie' else min(restante_extra, extra.cantidad_lote)
                    if qty_tomar > 0:
                        extras_data.append({
                            'id': extra.id,
                            'qty': qty_tomar
                        })
                        restante_extra -= qty_tomar

                # Usamos el modelo Transacción para un log centralizado
                # Al ser una cancelación de ingreso, es una salida (cantidad negativa)
                Transaccion.objects.create(
                    producto=producto,
                    almacen=almacen,
                    tipo='ajuste',
                    cantidad=-cant_restante_revertir,
                    empresa=recepcion.empresa,
                    usuario=request.user,
                    referencia=f"CANCELACIÓN: REC-{recepcion.id:04d}",
                    extras_data=extras_data,
                    estado='recibida'
                )

        recepcion.estado = 'cancelada'
        recepcion.save()

        # Recalcular costos de productos afectados (último costo y promedio)
        for det in recepcion.detalles.all():
            prod = det.producto
            prod.recalcular_costo_promedio_global(save=True)
            ult_det = DetalleRecepcion.objects.filter(
                producto=prod,
                recepcion__empresa=empresa_actual,
                recepcion__estado='completada'
            ).order_by('-recepcion__fecha', '-id').first()
            if ult_det:
                costo_ult = (ult_det.costo_unitario or Decimal('0.00')) * Decimal(str(ult_det.recepcion.tipo_cambio or '1.0000'))
                prod.ultimo_costo = costo_ult
                prod.precio_costo = costo_ult
                prod.save(update_fields=['ultimo_costo', 'precio_costo'])

        # Recalcular estado de la OC considerando recepciones y devoluciones activas
        nuevo_estado_oc = recalcular_estado_orden_compra(orden_compra)

        return JsonResponse({'success': True, 'message': f'Recepción cancelada. La OC regresó a estado: {nuevo_estado_oc.upper()}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_purchase_permission('recepciones', 'imprimir')
def imprimir_recepcion(request, pk):
    """Genera la vista para impresión de recepción de mercancía (PDF)"""
    empresa_actual = get_empresa_actual(request)
    recepcion = get_object_or_404(Recepcion, id=pk, empresa=empresa_actual)
    
    context = {
        'recepcion': recepcion,
        'empresa': empresa_actual,
    }
    return render(request, 'recepciones/imprimir_recepcion.html', context)


@login_required
@require_purchase_permission('devoluciones', 'crear', json_response=True)
@transaction.atomic
def crear_devolucion_recepcion(request, recepcion_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    try:
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'success': False, 'error': 'Empresa no detectada.'}, status=403)

        recepcion = get_object_or_404(Recepcion.objects.select_for_update(), id=recepcion_id, empresa=empresa_actual)
        if recepcion.estado != 'completada':
            return JsonResponse({'success': False, 'error': 'Solo se pueden realizar devoluciones de recepciones completadas.'})

        payload = json.loads(request.body.decode('utf-8'))
        motivo = (payload.get('motivo') or '').strip()
        items = payload.get('items') or []

        items_validos = []
        for item in items:
            try:
                det_id = int(item.get('detalle_id'))
                cant_dev = int(item.get('cantidad') or 0)
            except (TypeError, ValueError):
                continue

            if cant_dev <= 0:
                continue

            det_rec = get_object_or_404(DetalleRecepcion.objects.select_for_update(), id=det_id, recepcion=recepcion)
            disponible_devolver = det_rec.cantidad_disponible_devolver
            if cant_dev > disponible_devolver:
                return JsonResponse({
                    'success': False,
                    'error': f'La cantidad a devolver de "{det_rec.producto.nombre}" ({cant_dev}) excede lo disponible para devolver ({disponible_devolver}).'
                })

            if det_rec.producto.tipo != 'servicio':
                inv = Inventario.objects.filter(producto=det_rec.producto, almacen=recepcion.almacen).first()
                stock_actual = inv.cantidad if inv else 0
                if stock_actual < cant_dev:
                    return JsonResponse({
                        'success': False,
                        'error': f'Stock insuficiente en almacén "{recepcion.almacen.nombre}" para devolver "{det_rec.producto.nombre}". Disponible en almacén: {stock_actual}.'
                    })

            # Validar lote / caducidad / serie específicos ingresados en esta recepción
            extras_req = item.get('extras') or []
            extras_validados = []
            etiquetas_trazabilidad = []
            prod = det_rec.producto
            tiene_extras_recepcion = det_rec.extras.exists()

            if prod.tipo != 'servicio' and tiene_extras_recepcion:
                if extras_req:
                    suma_extras = 0
                    for ex_in in extras_req:
                        try:
                            ex_id = int(ex_in.get('id'))
                            ex_qty = int(ex_in.get('qty') or 0)
                        except (TypeError, ValueError):
                            continue
                        if ex_qty <= 0:
                            continue
                        extra_obj = DetalleRecepcionExtra.objects.select_for_update().filter(
                            id=ex_id,
                            detalle_recepcion=det_rec,
                            almacen=recepcion.almacen
                        ).first()
                        if not extra_obj:
                            return JsonResponse({
                                'success': False,
                                'error': f'El lote/serie seleccionado para "{prod.nombre}" ya no se encuentra disponible en el almacén "{recepcion.almacen.nombre}".'
                            })
                        if extra_obj.tipo == 'serie':
                            ex_qty = 1
                            etiquetas_trazabilidad.append(f"Serie: {extra_obj.serie}")
                        else:
                            if ex_qty > (extra_obj.cantidad_lote or 0):
                                return JsonResponse({
                                    'success': False,
                                    'error': f'La cantidad a devolver ({ex_qty}) supera lo disponible ({extra_obj.cantidad_lote}) en el lote/caducidad de "{prod.nombre}".'
                                })
                            partes_lbl = []
                            if extra_obj.lote:
                                partes_lbl.append(f"Lote: {extra_obj.lote}")
                            if extra_obj.fecha_caducidad:
                                partes_lbl.append(f"Cad: {extra_obj.fecha_caducidad.strftime('%d/%m/%Y')}")
                            lbl = " / ".join(partes_lbl) if partes_lbl else f"ID {extra_obj.id}"
                            etiquetas_trazabilidad.append(f"{lbl} ({ex_qty})")

                        extras_validados.append({'id': extra_obj.id, 'qty': ex_qty})
                        suma_extras += ex_qty

                    if suma_extras != cant_dev:
                        return JsonResponse({
                            'success': False,
                            'error': f'La suma de lotes/series seleccionados ({suma_extras}) no coincide con la cantidad a devolver ({cant_dev}) para "{prod.nombre}".'
                        })
                else:
                    restante_extra = cant_dev
                    for extra_obj in det_rec.extras.select_for_update().filter(almacen=recepcion.almacen).order_by('id'):
                        if restante_extra <= 0:
                            break
                        qty_tomar = 1 if extra_obj.tipo == 'serie' else min(restante_extra, extra_obj.cantidad_lote or 0)
                        if qty_tomar > 0:
                            extras_validados.append({'id': extra_obj.id, 'qty': qty_tomar})
                            if extra_obj.tipo == 'serie':
                                etiquetas_trazabilidad.append(f"Serie: {extra_obj.serie}")
                            else:
                                partes_lbl = []
                                if extra_obj.lote:
                                    partes_lbl.append(f"Lote: {extra_obj.lote}")
                                if extra_obj.fecha_caducidad:
                                    partes_lbl.append(f"Cad: {extra_obj.fecha_caducidad.strftime('%d/%m/%Y')}")
                                lbl = " / ".join(partes_lbl) if partes_lbl else f"ID {extra_obj.id}"
                                etiquetas_trazabilidad.append(f"{lbl} ({qty_tomar})")
                            restante_extra -= qty_tomar

                    if restante_extra > 0:
                        return JsonResponse({
                            'success': False,
                            'error': f'No hay suficientes lotes/series disponibles de esta recepción en el almacén para devolver {cant_dev} de "{prod.nombre}".'
                        })

            items_validos.append((det_rec, cant_dev, extras_validados, ", ".join(etiquetas_trazabilidad)))

        if not items_validos:
            return JsonResponse({'success': False, 'error': 'Debes indicar al menos una partida con cantidad mayor a 0 para devolver.'})

        devolucion = DevolucionRecepcion.objects.create(
            recepcion=recepcion,
            orden_compra=recepcion.orden_compra,
            almacen=recepcion.almacen,
            empresa=empresa_actual,
            sucursal=recepcion.sucursal or (recepcion.orden_compra.sucursal_empresa if recepcion.orden_compra else None),
            usuario=request.user,
            fecha=timezone.now().date(),
            motivo=motivo,
            estado='completada'
        )

        tc = Decimal(str(recepcion.tipo_cambio or '1.0000'))

        for det_rec, cant_dev, extras_data, trazabilidad_str in items_validos:
            DetalleDevolucionRecepcion.objects.create(
                devolucion=devolucion,
                detalle_recepcion=det_rec,
                producto=det_rec.producto,
                cantidad_devuelta=cant_dev,
                costo_unitario=det_rec.costo_unitario,
                detalle_trazabilidad=trazabilidad_str or None
            )

            producto = det_rec.producto
            if producto.tipo != 'servicio':
                costo_pesos = (det_rec.costo_unitario or Decimal('0.00')) * tc
                ref_kardex = f"DEV-{devolucion.id:04d} (REC-{recepcion.id:04d})"
                if motivo:
                    ref_kardex = f"{ref_kardex} - {motivo[:40]}"

                Transaccion.objects.create(
                    producto=producto,
                    almacen=recepcion.almacen,
                    tipo='ajuste',
                    cantidad=-cant_dev,
                    total=costo_pesos * Decimal(str(cant_dev)),
                    empresa=empresa_actual,
                    usuario=request.user,
                    referencia=ref_kardex,
                    extras_data=extras_data,
                    estado='recibida'
                )
                try:
                    producto.recalcular_costo_promedio_global(save=True)
                except Exception:
                    pass

        nuevo_estado_oc = recalcular_estado_orden_compra(recepcion.orden_compra)

        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'registró devolución DEV-{devolucion.id:04d} de recepción REC-{recepcion.id:04d} (OC-{recepcion.orden_compra.id:04d})',
            propietario=recepcion.orden_compra.usuario
        )

        return JsonResponse({
            'success': True,
            'folio': f"DEV-{devolucion.id:04d}",
            'estado_oc': nuevo_estado_oc.upper(),
            'message': f'Devolución DEV-{devolucion.id:04d} registrada correctamente. Existencias descontadas y Orden OC-{recepcion.orden_compra.id:04d} liberada ({nuevo_estado_oc.upper()}).'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_purchase_permission('devoluciones', 'ver')
def dashboard_devoluciones(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    q = request.GET.get('q', '')
    folio_devolucion = request.GET.get('folio_devolucion', '')
    folio_recepcion = request.GET.get('folio_recepcion', '')
    folio_oc = request.GET.get('folio_oc', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    almacen_id = request.GET.get('almacen_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')
    sucursal_id_filtro = request.GET.get('sucursal', '')

    devoluciones_list = DevolucionRecepcion.objects.filter(
        empresa=empresa_actual
    ).select_related(
        'recepcion', 'orden_compra', 'orden_compra__proveedor', 'almacen', 'sucursal', 'usuario'
    ).order_by('-fecha', '-id')

    if q:
        devoluciones_list = devoluciones_list.filter(
            Q(id__icontains=q) |
            Q(recepcion__id__icontains=q) |
            Q(orden_compra__id__icontains=q) |
            Q(orden_compra__proveedor__razon_social__icontains=q) |
            Q(motivo__icontains=q)
        )
    if folio_devolucion:
        clean_dev = folio_devolucion.upper().replace('DEV-', '').replace('DEV', '').strip()
        devoluciones_list = devoluciones_list.filter(id__icontains=clean_dev)
    if folio_recepcion:
        clean_rec = folio_recepcion.upper().replace('REC-', '').replace('REC', '').strip()
        devoluciones_list = devoluciones_list.filter(recepcion__id__icontains=clean_rec)
    if folio_oc:
        clean_oc = folio_oc.upper().replace('OC-', '').replace('OC', '').strip()
        devoluciones_list = devoluciones_list.filter(orden_compra__id__icontains=clean_oc)
    if proveedor_id and proveedor_id != 'all':
        devoluciones_list = devoluciones_list.filter(orden_compra__proveedor_id=proveedor_id)
    if almacen_id:
        devoluciones_list = devoluciones_list.filter(almacen_id=almacen_id)
    if fecha:
        try:
            devoluciones_list = devoluciones_list.filter(fecha=fecha)
        except Exception:
            pass
    if estado:
        devoluciones_list = devoluciones_list.filter(estado=estado)
    if sucursal_id_filtro:
        devoluciones_list = devoluciones_list.filter(sucursal_id=sucursal_id_filtro)

    proveedor_nombre_display = ""
    if proveedor_id and proveedor_id != 'all':
        try:
            p_obj = Proveedor.objects.get(id=proveedor_id, empresa=empresa_actual)
            proveedor_nombre_display = p_obj.razon_social
        except Exception:
            pass

    filtros = {
        'q': q,
        'folio_devolucion': folio_devolucion,
        'folio_recepcion': folio_recepcion,
        'folio_oc': folio_oc,
        'proveedor_id': proveedor_id,
        'proveedor_nombre': proveedor_nombre_display,
        'almacen_id': almacen_id,
        'fecha': fecha,
        'estado': estado,
        'sucursal': sucursal_id_filtro
    }

    from preferencias.models import Sucursal
    sucursales_lista = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    paginator = Paginator(devoluciones_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    almacenes = Almacen.objects.filter(empresa=empresa_actual)
    todos_los_proveedores = Proveedor.objects.filter(empresa=empresa_actual)

    context = {
        'page_obj': page_obj,
        'almacenes': almacenes,
        'todos_los_proveedores': todos_los_proveedores,
        'sucursales': sucursales_lista,
        'section': 'devoluciones',
        'filtros': filtros
    }
    return render(request, 'dashboard_devoluciones.html', context)


@login_required
@require_purchase_permission('devoluciones', 'ver', json_response=True)
def api_detalle_devolucion(request, devolucion_id):
    try:
        empresa_actual = get_empresa_actual(request)
        dev = get_object_or_404(
            DevolucionRecepcion.objects.select_related('recepcion', 'orden_compra', 'orden_compra__proveedor', 'almacen', 'sucursal', 'usuario'),
            id=devolucion_id,
            empresa=empresa_actual
        )
        rec = dev.recepcion
        oc = dev.orden_compra

        data = {
            'id': dev.id,
            'folio': f"DEV-{dev.id:04d}",
            'recepcion_folio': f"REC-{rec.id:04d}" if rec else '-',
            'oc_folio': f"OC-{oc.id:04d}" if oc else '-',
            'fecha': dev.fecha.strftime('%d/%m/%Y') if dev.fecha else '-',
            'estado': dev.estado.upper(),
            'proveedor': str(oc.proveedor) if oc else '-',
            'sucursal': dev.sucursal.nombre if dev.sucursal else (oc.sucursal.nombre if (oc and oc.sucursal) else 'Matriz / Principal'),
            'almacen': str(dev.almacen),
            'usuario': dev.usuario.username if dev.usuario else '-',
            'motivo': dev.motivo or 'Sin observaciones registradas.',
            'detalles': [
                {
                    'producto': d.producto.nombre,
                    'trazabilidad': d.detalle_trazabilidad or '',
                    'cant_recibida': d.detalle_recepcion.cantidad_recibida if d.detalle_recepcion else '-',
                    'cant_devuelta': d.cantidad_devuelta,
                    'precio': float(d.costo_unitario),
                    'subtotal': float(d.subtotal),
                    'iva_monto': float(d.iva_monto),
                    'total': float(d.total)
                } for d in dev.detalles.select_related('producto', 'detalle_recepcion').all()
            ],
            'subtotal_total': float(dev.calcular_subtotal),
            'iva_total': float(dev.calcular_iva),
            'gran_total': float(dev.calcular_total)
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required(login_url='/login/')
@require_purchase_permission('devoluciones', 'ver')
def exportar_devoluciones_excel(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return HttpResponse("No autorizado", status=403)

    q = request.GET.get('q', '')
    folio_devolucion = request.GET.get('folio_devolucion', '')
    folio_recepcion = request.GET.get('folio_recepcion', '')
    folio_oc = request.GET.get('folio_oc', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    almacen_id = request.GET.get('almacen_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')
    sucursal_id_filtro = request.GET.get('sucursal', '')

    devoluciones = DevolucionRecepcion.objects.filter(
        empresa=empresa_actual
    ).select_related('recepcion', 'orden_compra', 'orden_compra__proveedor', 'almacen', 'sucursal', 'usuario').order_by('-fecha', '-id')

    if q:
        devoluciones = devoluciones.filter(
            Q(id__icontains=q) | Q(recepcion__id__icontains=q) |
            Q(orden_compra__id__icontains=q) | Q(orden_compra__proveedor__razon_social__icontains=q) |
            Q(motivo__icontains=q)
        )
    if folio_devolucion:
        devoluciones = devoluciones.filter(id__icontains=folio_devolucion.upper().replace('DEV-', '').replace('DEV', '').strip())
    if folio_recepcion:
        devoluciones = devoluciones.filter(recepcion__id__icontains=folio_recepcion.upper().replace('REC-', '').replace('REC', '').strip())
    if folio_oc:
        devoluciones = devoluciones.filter(orden_compra__id__icontains=folio_oc.upper().replace('OC-', '').replace('OC', '').strip())
    if proveedor_id and proveedor_id != 'all':
        devoluciones = devoluciones.filter(orden_compra__proveedor_id=proveedor_id)
    if almacen_id:
        devoluciones = devoluciones.filter(almacen_id=almacen_id)
    if fecha:
        try:
            devoluciones = devoluciones.filter(fecha=fecha)
        except Exception:
            pass
    if estado:
        devoluciones = devoluciones.filter(estado=estado)
    if sucursal_id_filtro:
        devoluciones = devoluciones.filter(sucursal_id=sucursal_id_filtro)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte de Devoluciones"

    headers = [
        'ID', 'Folio Devolución', 'Recepción Origen', 'OC Origen', 'Proveedor', 'Almacén', 'Fecha', 'Motivo', 'Estado', 'Total'
    ]
    ws.append(headers)

    for d in devoluciones:
        ws.append([
            d.id,
            f"DEV-{d.id:04d}",
            f"REC-{d.recepcion.id:04d}",
            f"OC-{d.orden_compra.id:04d}",
            d.orden_compra.proveedor.razon_social if d.orden_compra and d.orden_compra.proveedor else '-',
            d.almacen.nombre if d.almacen else '-',
            d.fecha.strftime('%Y-%m-%d') if d.fecha else '-',
            d.motivo or '-',
            d.get_estado_display(),
            d.total
        ])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        ws.column_dimensions[column].width = max_length + 2

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Devoluciones_{empresa_actual.nombre}.xlsx"'
    wb.save(response)
    return response

