from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
import json
from decimal import Decimal
from django.utils import timezone
from django.db import IntegrityError
from .models import Almacen, Inventario, Kardex, SalidaPorUso, DetalleSalidaPorUso
from preferencias.models import Sucursal
from core.models import Producto
from pedidos.models import DetallePedido
from panel.models import Empresa
from recepciones.models import DetalleRecepcionExtra

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

# --- VISTAS DASHBOARD ---

from preferencias.permissions import require_inventory_permission

@login_required(login_url='/login/')
@require_inventory_permission('almacenes', 'ver')
def lista_almacenes(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    sucursal_id = request.GET.get('sucursal')
    almacenes = Almacen.objects.filter(empresa=empresa_actual).select_related('sucursal').order_by('nombre')
    
    if sucursal_id:
        almacenes = almacenes.filter(sucursal_id=sucursal_id)
        
    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    
    contexto = {
        'almacenes': almacenes,
        'sucursales': sucursales,
        'filtros': {
            'sucursal': sucursal_id or ''
        }
    }
    return render(request, 'dashboard_almacenes.html', contexto)

@login_required(login_url='/login/')
@require_inventory_permission('kardex', 'ver')
def dashboard_kardex(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Filtros
    q = request.GET.get('q')
    producto_id = request.GET.get('producto')
    almacen_id = request.GET.get('almacen')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    usuario_id = request.GET.get('usuario')
    sucursal_id = request.GET.get('sucursal')

    movimientos = Kardex.objects.filter(empresa=empresa_actual).select_related('producto', 'almacen', 'usuario', 'sucursal').order_by('-fecha')

    if q:
        movimientos = movimientos.filter(
            Q(producto__nombre__icontains=q) | Q(lote__icontains=q) | Q(serie__icontains=q)
        )
    if producto_id:
        movimientos = movimientos.filter(producto_id=producto_id)
    if sucursal_id:
        movimientos = movimientos.filter(sucursal_id=sucursal_id)
    if almacen_id:
        movimientos = movimientos.filter(almacen_id=almacen_id)
    if tipo_movimiento:
        movimientos = movimientos.filter(tipo_movimiento=tipo_movimiento)
    if usuario_id:
        movimientos = movimientos.filter(usuario_id=usuario_id)

    # Procesar nombres de usuario para quitar el @subdominio
    for m in movimientos:
        if m.usuario:
            # Si el usuario tiene @, lo cortamos, si no, lo dejamos igual
            m.display_user = m.usuario.username.split('@')[0] if '@' in m.usuario.username else m.usuario.username
        else:
            m.display_user = "Sistema"

    productos = Producto.objects.filter(empresa=empresa_actual).order_by('nombre')
    almacenes = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')
    if sucursal_id:
        almacenes = almacenes.filter(sucursal_id=sucursal_id)
        
    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    
    # Obtener usuarios: Todos los que han hecho movimientos en esta empresa + los actuales
    ids_usuarios_kardex = Kardex.objects.filter(empresa=empresa_actual).values_list('usuario_id', flat=True).distinct()
    usuarios_list = User.objects.filter(
        Q(id__in=ids_usuarios_kardex) |
        Q(username__iendswith=f"@{empresa_actual.subdominio}") |
        Q(roles_empresa__empresa=empresa_actual),
        is_active=True
    ).distinct().exclude(username__icontains='@crossoversuite').order_by('first_name', 'username')
    
    for u in usuarios_list:
        u.clean_name = u.username.split('@')[0] if '@' in u.username else u.username

    # --- PAGINACIÓN ---
    paginator = Paginator(movimientos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'page_obj': page_obj,
        'productos': productos,
        'almacenes': almacenes,
        'sucursales': sucursales,
        'usuarios': usuarios_list,
        'filtros': {
            'q': q or '',
            'producto': int(producto_id) if producto_id else '',
            'almacen': int(almacen_id) if almacen_id else '',
            'tipo_movimiento': tipo_movimiento or '',
            'usuario': int(usuario_id) if usuario_id else '',
            'sucursal': sucursal_id
        }
    }
    return render(request, 'dashboard_kardex.html', contexto)

# --- APIS ALMACÉN ---

@login_required
@require_inventory_permission('almacenes', 'crear', json_response=True)
def api_crear_almacen(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            Almacen.objects.create(
                nombre=request.POST.get('nombre'),
                responsable=request.POST.get('responsable'),
                calle=request.POST.get('calle'),
                numero_ext=request.POST.get('numero_ext'),
                numero_int=request.POST.get('numero_int'),
                colonia=request.POST.get('colonia'),
                estado=request.POST.get('estado'),
                cp=request.POST.get('cp'),
                telefono=request.POST.get('telefono'),
                empresa=empresa_actual,
                sucursal_id=request.POST.get('sucursal')
            )
            return JsonResponse({'success': True, 'message': 'Almacén creado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@require_inventory_permission('almacenes', 'ver', json_response=True)
def api_detalle_almacen(request, id):
    empresa_actual = get_empresa_actual(request)
    almacen = get_object_or_404(Almacen, id=id, empresa=empresa_actual)
    return JsonResponse({
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
        'sucursal': almacen.sucursal.id if almacen.sucursal else ''
    })

@login_required
@require_inventory_permission('almacenes', 'editar', json_response=True)
def api_actualizar_almacen(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            almacen = get_object_or_404(Almacen, id=id, empresa=empresa_actual)
            almacen.nombre = request.POST.get('nombre')
            almacen.responsable = request.POST.get('responsable')
            almacen.calle = request.POST.get('calle')
            almacen.numero_ext = request.POST.get('numero_ext')
            almacen.numero_int = request.POST.get('numero_int')
            almacen.colonia = request.POST.get('colonia')
            almacen.estado = request.POST.get('estado')
            almacen.cp = request.POST.get('cp')
            almacen.telefono = request.POST.get('telefono')
            almacen.sucursal_id = request.POST.get('sucursal')
            almacen.save()
            return JsonResponse({'success': True, 'message': 'Almacén actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- APIs PARA TRASLADOS ---

@login_required
@require_inventory_permission('inventario', 'traslado', json_response=True)
def api_productos_con_stock(request, almacen_id):
    """Retorna productos que tienen existencia física en el almacén de origen"""
    empresa_actual = get_empresa_actual(request)
    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    
    inventarios = Inventario.objects.filter(
        almacen=almacen,
        empresa=empresa_actual,
        producto__empresa=empresa_actual,
        cantidad__gt=0
    ).select_related('producto')
    
    data = []
    for inv in inventarios:
        data.append({
            'id': inv.producto.id,
            'nombre': inv.producto.nombre,
            'total': inv.cantidad,
            'reservado': inv.reservado,
            'disponible': inv.cantidad - inv.reservado,
            'maneja_lote': inv.producto.maneja_lote,
            'maneja_serie': inv.producto.maneja_serie,
            'maneja_caducidad': inv.producto.maneja_caducidad
        })
    return JsonResponse(data, safe=False)

@login_required
@require_inventory_permission('inventario', 'traslado', json_response=True)
def api_extras_producto(request, almacen_id, producto_id):
    """Retorna lotes o series disponibles para un producto en un almacén"""
    empresa_actual = get_empresa_actual(request)
    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    
    # Buscamos en DetalleRecepcionExtra que pertenezcan al almacén origen
    extras = DetalleRecepcionExtra.objects.filter(
        almacen=almacen
    ).filter(
        Q(detalle_recepcion__producto_id=producto_id) | Q(producto_id=producto_id)
    )
    
    data = []
    for e in extras:
        if e.tipo in ['lote', 'caducidad'] and (e.cantidad_lote or 0) <= 0:
            continue
        data.append({
            'id': e.id,
            'tipo': e.tipo,
            'lote': e.lote or (f"Cad: {e.fecha_caducidad.strftime('%d/%m/%Y')}" if e.fecha_caducidad else None),
            'serie': e.serie,
            'fecha_caducidad': e.fecha_caducidad.strftime('%d/%m/%Y') if e.fecha_caducidad else None,
            'cantidad': e.cantidad_lote if e.tipo in ['lote', 'caducidad'] else 1
        })
    return JsonResponse(data, safe=False)

@login_required
@transaction.atomic
@require_inventory_permission('inventario', 'traslado', json_response=True)
def api_ejecutar_traslado(request):
    """Procesa el movimiento de mercancía entre almacenes para múltiples items"""
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        empresa_actual = get_empresa_actual(request)
        data = json.loads(request.body)
        
        origen_id = data.get('almacen_origen')
        destino_id = data.get('almacen_destino')
        items = data.get('items', [])

        if not origen_id or not destino_id: raise ValueError("Faltan almacenes de origen o destino.")
        if origen_id == destino_id: raise ValueError("El almacén origen y destino no pueden ser el mismo.")
        if not items: raise ValueError("No hay artículos para trasladar.")

        origen = get_object_or_404(Almacen, id=origen_id, empresa=empresa_actual)
        destino = get_object_or_404(Almacen, id=destino_id, empresa=empresa_actual)

        for item in items:
            producto_id = item.get('producto_id')
            cantidad = int(item.get('cantidad', 0))
            extra_id = item.get('extra_id') # ID del registro DetalleRecepcionExtra

            if cantidad <= 0: continue

            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

            # 1. VALIDAR STOCK EN ORIGEN
            try:
                inv_origen = Inventario.objects.select_for_update().get(almacen=origen, producto=producto)
            except Inventario.DoesNotExist:
                raise ValueError(f"No hay stock suficiente de {producto.nombre} en el origen (Disponible: 0).")

            if inv_origen.cantidad < cantidad: 
                raise ValueError(f"No hay stock suficiente de {producto.nombre} en el origen.")

            disponible_origen = inv_origen.cantidad - inv_origen.reservado
            piezas_reservadas_movidas = 0
            if cantidad > disponible_origen:
                piezas_reservadas_movidas = cantidad - disponible_origen

            # 2. MOVIMIENTO DE SALIDA (ORIGEN)
            inv_origen.cantidad = F('cantidad') - cantidad
            if piezas_reservadas_movidas > 0:
                inv_origen.reservado = F('reservado') - piezas_reservadas_movidas
            inv_origen.save()

            # 3. MOVIMIENTO DE ENTRADA (DESTINO)
            inv_destino, created = Inventario.objects.select_for_update().get_or_create(
                almacen=destino, producto=producto,
                defaults={
                    'cantidad': 0, 
                    'reservado': 0, 
                    'costo_promedio': inv_origen.costo_promedio, 
                    'empresa': empresa_actual,
                    'sucursal': destino.sucursal # <--- ASIGNAR SUCURSAL DESTINO
                }
            )
            inv_destino.cantidad = F('cantidad') + cantidad
            if piezas_reservadas_movidas > 0:
                inv_destino.reservado = F('reservado') + piezas_reservadas_movidas
            
            # Aseguramos que la sucursal sea la del almacén destino incluso si ya existía
            inv_destino.sucursal = destino.sucursal
            inv_destino.save()

            # 4. ACTUALIZAR LOTE/SERIE (SI APLICA)
            lote_ref, serie_ref = None, None
            if extra_id:
                extra = DetalleRecepcionExtra.objects.select_for_update().get(id=extra_id, almacen=origen)
                if extra.tipo == 'serie':
                    extra.almacen = destino
                    extra.save()
                    serie_ref = extra.serie
                else:
                    # LOTE O CADUCIDAD
                    if extra.cantidad_lote < cantidad:
                        raise ValueError(f"Stock insuficiente en el lote {extra.lote or extra.fecha_caducidad}. Disponible: {extra.cantidad_lote}")
                    if extra.cantidad_lote > cantidad:
                        extra.cantidad_lote = F('cantidad_lote') - cantidad
                        extra.save()
                        DetalleRecepcionExtra.objects.create(
                            detalle_recepcion=extra.detalle_recepcion, 
                            producto=extra.producto or producto,
                            tipo=extra.tipo,
                            lote=extra.lote,
                            fecha_caducidad=extra.fecha_caducidad,
                            cantidad_lote=cantidad,
                            almacen=destino
                        )
                    else:
                        extra.almacen = destino
                        extra.save()
                    lote_ref = extra.lote or (extra.fecha_caducidad.strftime('%d/%m/%Y') if extra.fecha_caducidad else None)

            # 5. REGISTRAR EN KARDEX (DOBLE ASIENTO)
            ref_folio = "TRASLADO"
            # Refrescamos objetos para tener el valor numérico real para el Kardex
            inv_origen.refresh_from_db()
            inv_destino.refresh_from_db()

            Kardex.objects.create(
                empresa=empresa_actual, 
                sucursal=origen.sucursal, # <--- ASIGNAR SUCURSAL ORIGEN
                producto=producto, almacen=origen, tipo_movimiento='salida',
                cantidad=cantidad, stock_anterior=inv_origen.cantidad + cantidad, stock_nuevo=inv_origen.cantidad,
                referencia=ref_folio, lote=lote_ref, serie=serie_ref,
                usuario=request.user
            )
            Kardex.objects.create(
                empresa=empresa_actual, 
                sucursal=destino.sucursal, # <--- ASIGNAR SUCURSAL DESTINO
                producto=producto, almacen=destino, tipo_movimiento='entrada',
                cantidad=cantidad, stock_anterior=inv_destino.cantidad - cantidad, stock_nuevo=inv_destino.cantidad,
                referencia=ref_folio, lote=lote_ref, serie=serie_ref,
                usuario=request.user
            )

        return JsonResponse({'success': True, 'message': 'Traslado realizado correctamente.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_inventory_permission('inventario', 'ver', json_response=True)
def api_detalle_reservas(request, producto_id):
    """Retorna detalles de qué pedidos tienen reservado este producto"""
    empresa_actual = get_empresa_actual(request)
    producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

    # Buscamos partidas de pedido reservadas
    reservas = DetallePedido.objects.filter(
        producto=producto,
        pedido__empresa=empresa_actual,
        estado_linea='reservado'
    ).select_related('pedido', 'pedido__cliente').order_by('-pedido__fecha_creacion')

    data = []
    total_gral = 0
    for r in reservas:
        cantidad = r.cantidad_solicitada - r.cantidad_entregada
        if cantidad <= 0: continue
        
        data.append({
            'id': r.id,
            'cliente': str(r.pedido.cliente),
            'folio': f"PED-{r.pedido.id:04d}",
            'fecha': r.pedido.fecha_creacion.strftime('%d/%m/%Y'),
            'cantidad': cantidad
        })
        total_gral += cantidad

    return JsonResponse({
        'success': True,
        'producto': producto.nombre,
        'reservas': data,
        'total': total_gral
    })


# ==============================================================================
# TOMA DE INVENTARIO FÍSICO (CONTEO FÍSICO Y AJUSTE MASIVO)
# ==============================================================================
from django.utils import timezone
from .models import TomaInventario, DetalleTomaInventario

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'ver')
def dashboard_toma_inventario(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    q = request.GET.get('q', '').strip()
    almacen_id = request.GET.get('almacen', '').strip()
    estado = request.GET.get('estado', '').strip()

    tomas = TomaInventario.objects.filter(empresa=empresa_actual).select_related('almacen', 'creado_por')

    if q:
        tomas = tomas.filter(Q(nombre__icontains=q) | Q(almacen__nombre__icontains=q))
    if almacen_id:
        tomas = tomas.filter(almacen_id=almacen_id)
    if estado:
        tomas = tomas.filter(estado=estado)

    almacenes = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')

    # Métricas
    total_tomas = TomaInventario.objects.filter(empresa=empresa_actual).count()
    en_proceso_count = TomaInventario.objects.filter(empresa=empresa_actual, estado='en_proceso').count()
    finalizados_count = TomaInventario.objects.filter(empresa=empresa_actual, estado='finalizado').count()

    paginator = Paginator(tomas, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'tomas': page_obj,
        'almacenes': almacenes,
        'filtros': {
            'q': q,
            'almacen': almacen_id,
            'estado': estado,
        },
        'metricas': {
            'total': total_tomas,
            'en_proceso': en_proceso_count,
            'finalizados': finalizados_count,
        }
    }
    try:
        return render(request, 'dashboard_toma_inventario.html', contexto)
    except Exception:
        return render(request, 'almacenes/dashboard_toma_inventario.html', contexto)


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear', json_response=True)
def api_crear_toma_inventario(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'}, status=403)

    nombre = request.POST.get('nombre', '').strip()
    almacen_id = request.POST.get('almacen_id')
    fecha_inicio = request.POST.get('fecha_inicio')
    fecha_fin = request.POST.get('fecha_fin') or None
    notas = request.POST.get('notas', '').strip()

    if not nombre:
        return JsonResponse({'success': False, 'error': 'El nombre del inventario es obligatorio.'})
    if not almacen_id:
        return JsonResponse({'success': False, 'error': 'Debe seleccionar un almacén válido.'})
    if not fecha_inicio:
        fecha_inicio = timezone.now()

    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)

    try:
        with transaction.atomic():
            toma = TomaInventario.objects.create(
                empresa=empresa_actual,
                sucursal=almacen.sucursal,
                nombre=nombre,
                almacen=almacen,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado='en_proceso',
                notas=notas,
                creado_por=request.user
            )

            # Cargar todos los productos activos de la empresa para inicializar la toma
            productos = Producto.objects.filter(empresa=empresa_actual, estado='activo').select_related()
            inventarios_map = {
                inv.producto_id: inv 
                for inv in Inventario.objects.filter(almacen=almacen, producto__in=productos)
            }

            detalles_bulk = []
            for p in productos:
                inv = inventarios_map.get(p.id)
                existencia = Decimal(str(inv.cantidad)) if inv else Decimal('0.00')
                costo = (inv.costo_promedio if inv and inv.costo_promedio > 0 else None) or p.costo_promedio or p.ultimo_costo or p.precio_costo or Decimal('0.00')

                detalles_bulk.append(DetalleTomaInventario(
                    toma_inventario=toma,
                    producto=p,
                    existencia_sistema=existencia,
                    costo_unitario=costo,
                    cantidad_fisica=Decimal('0.00'),
                    contado=False
                ))

            DetalleTomaInventario.objects.bulk_create(detalles_bulk)

        return JsonResponse({
            'success': True,
            'id': toma.id,
            'message': f'Inventario "{toma.nombre}" creado exitosamente con {len(detalles_bulk)} partidas.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'ver', json_response=True)
def api_materiales_toma_inventario(request, toma_id):
    empresa_actual = get_empresa_actual(request)
    toma = get_object_or_404(TomaInventario, id=toma_id, empresa=empresa_actual)

    q = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('filtro_estado', 'todos').strip()

    detalles_qs = DetalleTomaInventario.objects.filter(toma_inventario=toma).select_related('producto', 'usuario_conteo').prefetch_related('producto__barcodes')

    # Filtros opcionales
    if q:
        detalles_qs = detalles_qs.filter(
            Q(producto__nombre__icontains=q) |
            Q(producto__clave__icontains=q) |
            Q(producto__barcodes__codigo__icontains=q)
        ).distinct()

    if filtro_estado == 'contados':
        detalles_qs = detalles_qs.filter(contado=True)
    elif filtro_estado == 'pendientes':
        detalles_qs = detalles_qs.filter(contado=False)
    elif filtro_estado == 'diferencias':
        detalles_qs = detalles_qs.exclude(cantidad_fisica=F('existencia_sistema'))

    # Estadísticas globales de la toma
    todos_detalles = DetalleTomaInventario.objects.filter(toma_inventario=toma)
    total_partidas = todos_detalles.count()
    contadas = todos_detalles.filter(contado=True).count()
    pendientes = total_partidas - contadas

    partidas_data = []
    total_sistema_importe = Decimal('0.00')
    total_fisico_importe = Decimal('0.00')
    con_diferencia_count = 0

    for d in detalles_qs:
        sub_sist = d.subtotal_sistema
        sub_fis = d.subtotal_fisico
        dif = d.diferencia
        dif_imp = d.diferencia_importe

        total_sistema_importe += sub_sist
        if d.contado:
            total_fisico_importe += sub_fis
        if dif != 0 and d.contado:
            con_diferencia_count += 1

        barcodes = [b.codigo for b in d.producto.barcodes.all()]
        clave_efectiva = d.producto.clave or (barcodes[0] if barcodes else '--')

        partidas_data.append({
            'id': d.id,
            'producto_id': d.producto.id,
            'clave': clave_efectiva,
            'codigos_barras': barcodes,
            'nombre': d.producto.nombre,
            'unidad': d.producto.unidad_medida or 'H87',
            'categoria': d.producto.categoria or '--',
            'existencia_sistema': float(d.existencia_sistema),
            'costo_unitario': float(d.costo_unitario),
            'cantidad_fisica': float(d.cantidad_fisica),
            'diferencia': float(dif),
            'diferencia_importe': float(dif_imp),
            'subtotal_sistema': float(sub_sist),
            'subtotal_fisico': float(sub_fis),
            'contado': d.contado,
            'numero_conteos': d.numero_conteos if d.numero_conteos > 0 else (1 if d.contado else 0),
            'fecha_conteo': d.fecha_conteo.strftime('%d/%m/%Y %H:%M') if d.fecha_conteo else '',
            'usuario_conteo': d.usuario_conteo.username if d.usuario_conteo else '',
            'notas': d.notas or ''
        })

    return JsonResponse({
        'success': True,
        'toma': {
            'id': toma.id,
            'nombre': toma.nombre,
            'almacen': toma.almacen.nombre,
            'fecha_inicio': toma.fecha_inicio.strftime('%d/%m/%Y %H:%M') if toma.fecha_inicio else '',
            'fecha_fin': toma.fecha_fin.strftime('%d/%m/%Y %H:%M') if toma.fecha_fin else '',
            'estado': toma.estado,
            'estado_display': toma.get_estado_display(),
            'porcentaje_avance': toma.porcentaje_avance,
        },
        'stats': {
            'total_partidas': total_partidas,
            'contadas': contadas,
            'pendientes': pendientes,
            'con_diferencia': con_diferencia_count,
            'total_sistema_importe': float(total_sistema_importe),
            'total_fisico_importe': float(total_fisico_importe),
            'total_diferencia_importe': float(total_fisico_importe - total_sistema_importe)
        },
        'partidas': partidas_data
    })


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'ver', json_response=True)
def api_buscar_articulo_toma(request, toma_id):
    empresa_actual = get_empresa_actual(request)
    toma = get_object_or_404(TomaInventario, id=toma_id, empresa=empresa_actual)
    q = request.GET.get('q', '').strip()

    if not q:
        return JsonResponse({'success': True, 'resultados': [], 'exacto': None})

    # 1. Búsqueda exacta por código de barras o clave
    detalle_exacto = DetalleTomaInventario.objects.filter(
        Q(toma_inventario=toma) &
        (Q(producto__clave__iexact=q) | Q(producto__barcodes__codigo__iexact=q))
    ).select_related('producto').prefetch_related('producto__barcodes').first()

    def serializar_detalle(d):
        barcodes = [b.codigo for b in d.producto.barcodes.all()]
        clave_efectiva = d.producto.clave or (barcodes[0] if barcodes else '--')
        return {
            'id': d.id,
            'producto_id': d.producto.id,
            'clave': clave_efectiva,
            'codigos_barras': barcodes,
            'nombre': d.producto.nombre,
            'unidad': d.producto.unidad_medida or 'H87',
            'existencia_sistema': float(d.existencia_sistema),
            'costo_unitario': float(d.costo_unitario),
            'cantidad_fisica': float(d.cantidad_fisica),
            'contado': d.contado,
            'numero_conteos': d.numero_conteos if d.numero_conteos > 0 else (1 if d.contado else 0),
            'fecha_conteo': d.fecha_conteo.strftime('%d/%m/%Y %H:%M') if d.fecha_conteo else '',
            'notas': d.notas or ''
        }

    if detalle_exacto:
        return JsonResponse({
            'success': True,
            'exacto': serializar_detalle(detalle_exacto),
            'resultados': [serializar_detalle(detalle_exacto)]
        })

    # 2. Búsqueda parcial por clave, nombre o código
    coincidencias = DetalleTomaInventario.objects.filter(
        Q(toma_inventario=toma) &
        (
            Q(producto__clave__icontains=q) |
            Q(producto__nombre__icontains=q) |
            Q(producto__barcodes__codigo__icontains=q)
        )
    ).select_related('producto').prefetch_related('producto__barcodes').distinct()[:10]

    return JsonResponse({
        'success': True,
        'exacto': None,
        'resultados': [serializar_detalle(d) for d in coincidencias]
    })


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'editar', json_response=True)
def api_guardar_conteo_toma(request, toma_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    empresa_actual = get_empresa_actual(request)
    toma = get_object_or_404(TomaInventario, id=toma_id, empresa=empresa_actual)

    if toma.estado != 'en_proceso':
        return JsonResponse({'success': False, 'error': 'No se puede capturar conteos en un inventario que no está "En proceso".'})

    detalle_id = request.POST.get('detalle_id')
    cantidad_contada_raw = request.POST.get('cantidad_contada', '0').strip()
    modo = request.POST.get('modo', 'reemplazar') # 'reemplazar' o 'sumar'
    notas = request.POST.get('notas', '').strip()

    detalle = get_object_or_404(DetalleTomaInventario, id=detalle_id, toma_inventario=toma)

    try:
        cantidad_num = Decimal(cantidad_contada_raw)
        if cantidad_num < 0:
            return JsonResponse({'success': False, 'error': 'La cantidad física no puede ser negativa.'})

        if modo == 'sumar':
            detalle.cantidad_fisica = detalle.cantidad_fisica + cantidad_num
        else:
            detalle.cantidad_fisica = cantidad_num

        if detalle.numero_conteos == 0 and detalle.contado:
            detalle.numero_conteos = 1
        detalle.numero_conteos += 1
        detalle.contado = True
        detalle.fecha_conteo = timezone.now()
        detalle.usuario_conteo = request.user
        if notas:
            detalle.notas = notas
        detalle.save()

        return JsonResponse({
            'success': True,
            'message': f'Conteo guardado para {detalle.producto.nombre}: {detalle.cantidad_fisica}',
            'detalle': {
                'id': detalle.id,
                'producto_id': detalle.producto.id,
                'clave': detalle.producto.clave or '--',
                'nombre': detalle.producto.nombre,
                'existencia_sistema': float(detalle.existencia_sistema),
                'cantidad_fisica': float(detalle.cantidad_fisica),
                'diferencia': float(detalle.diferencia),
                'diferencia_importe': float(detalle.diferencia_importe),
                'contado': True,
                'numero_conteos': detalle.numero_conteos,
                'fecha_conteo': detalle.fecha_conteo.strftime('%d/%m/%Y %H:%M'),
                'usuario_conteo': request.user.username
            },
            'avance': {
                'contadas': toma.partidas_contadas,
                'total': toma.total_partidas,
                'porcentaje': toma.porcentaje_avance
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'editar', json_response=True)
def api_cambiar_estado_toma(request, toma_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    empresa_actual = get_empresa_actual(request)
    toma = get_object_or_404(TomaInventario, id=toma_id, empresa=empresa_actual)
    nuevo_estado = request.POST.get('estado')

    if nuevo_estado not in ['en_proceso', 'finalizado', 'cancelado']:
        return JsonResponse({'success': False, 'error': 'Estado no válido.'})

    toma.estado = nuevo_estado
    toma.save()

    return JsonResponse({
        'success': True,
        'nuevo_estado': toma.estado,
        'nuevo_estado_display': toma.get_estado_display(),
        'message': f'Estado de inventario actualizado a "{toma.get_estado_display()}".'
    })


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'eliminar', json_response=True)
def api_eliminar_toma_inventario(request, toma_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    empresa_actual = get_empresa_actual(request)
    toma = get_object_or_404(TomaInventario, id=toma_id, empresa=empresa_actual)
    nombre = toma.nombre
    toma.delete()

    return JsonResponse({
        'success': True,
        'message': f'El inventario "{nombre}" ha sido eliminado exitosamente.'
    })


@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'editar', json_response=True)
@transaction.atomic
def api_cerrar_toma_inventario(request, toma_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    empresa_actual = get_empresa_actual(request)
    toma = get_object_or_404(TomaInventario, id=toma_id, empresa=empresa_actual)

    if toma.estado == 'cerrado':
        return JsonResponse({'success': False, 'error': 'El inventario ya se encuentra cerrado.'})

    accion = request.POST.get('accion_cierre', 'actualizar').strip() # 'actualizar' o 'no_actualizar'

    ajustes_realizados = 0
    if accion == 'actualizar':
        detalles_contados = toma.detalles.filter(contado=True).select_related('producto')
        for det in detalles_contados:
            inv, _ = Inventario.objects.get_or_create(
                empresa=toma.empresa,
                almacen=toma.almacen,
                producto=det.producto,
                defaults={
                    'cantidad': 0,
                    'reservado': 0,
                    'costo_promedio': det.costo_unitario,
                    'sucursal': toma.almacen.sucursal
                }
            )
            stock_anterior = inv.cantidad
            stock_nuevo = int(round(det.cantidad_fisica))
            dif = stock_nuevo - stock_anterior

            if dif != 0:
                inv.cantidad = stock_nuevo
                inv.save()

                Kardex.objects.create(
                    empresa=toma.empresa,
                    sucursal=toma.almacen.sucursal,
                    producto=det.producto,
                    almacen=toma.almacen,
                    tipo_movimiento='ajuste',
                    cantidad=abs(dif),
                    stock_anterior=stock_anterior,
                    stock_nuevo=stock_nuevo,
                    referencia=f"Toma Inv: {toma.nombre}",
                    usuario=request.user
                )
                ajustes_realizados += 1

    toma.estado = 'cerrado'
    toma.fecha_fin = timezone.now()
    toma.save()

    msg = f'Inventario "{toma.nombre}" cerrado exitosamente.'
    if accion == 'actualizar':
        msg += f' Se ajustaron las existencias de {ajustes_realizados} artículo(s) en {toma.almacen.nombre}.'
    else:
        msg += ' No se modificaron las existencias del sistema (Modo auditoría).'

    return JsonResponse({
        'success': True,
        'message': msg,
        'estado': toma.estado,
        'estado_display': toma.get_estado_display(),
        'fecha_fin': toma.fecha_fin.strftime('%d/%m/%Y %H:%M')
    })


# ==============================================================
# --- MÓDULO: SALIDA POR USO DE INVENTARIO ---
# ==============================================================

@login_required(login_url='/login/')
@require_inventory_permission('salida_por_uso', 'ver')
def dashboard_salida_por_uso(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error.html', {'mensaje': 'Empresa no encontrada'})

    # Filtros
    q = request.GET.get('q', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()
    almacen_id = request.GET.get('almacen', '').strip()
    estado = request.GET.get('estado', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()

    salidas_qs = SalidaPorUso.objects.filter(empresa=empresa_actual).select_related(
        'sucursal', 'almacen', 'usuario_creador', 'usuario_recibe', 'usuario_aprueba', 'usuario_cancela'
    ).prefetch_related('detalles__producto').order_by('-fecha_creacion')

    if q:
        salidas_qs = salidas_qs.filter(
            Q(folio__icontains=q) |
            Q(almacen__nombre__icontains=q) |
            Q(sucursal__nombre__icontains=q) |
            Q(usuario_creador__first_name__icontains=q) |
            Q(usuario_creador__username__icontains=q) |
            Q(usuario_recibe__first_name__icontains=q) |
            Q(usuario_recibe__username__icontains=q) |
            Q(notas__icontains=q)
        )

    if sucursal_id:
        salidas_qs = salidas_qs.filter(sucursal_id=sucursal_id)

    if almacen_id:
        salidas_qs = salidas_qs.filter(almacen_id=almacen_id)

    if estado:
        salidas_qs = salidas_qs.filter(estado=estado)

    if fecha_inicio:
        salidas_qs = salidas_qs.filter(fecha_salida__gte=fecha_inicio)

    if fecha_fin:
        salidas_qs = salidas_qs.filter(fecha_salida__lte=fecha_fin)

    # Catálogos para filtros y modal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    almacenes = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')

    # Sucursal actual del usuario (por sesión o primera disponible)
    sesion_sucursal_id = request.session.get('sucursal_id')
    sucursal_actual = None
    if sesion_sucursal_id:
        sucursal_actual = sucursales.filter(id=sesion_sucursal_id).first()
    if not sucursal_actual and sucursales.exists():
        sucursal_actual = sucursales.first()

    # Almacenes para la sucursal actual
    if sucursal_actual:
        almacenes_sucursal_actual = almacenes.filter(sucursal=sucursal_actual)
        if not almacenes_sucursal_actual.exists():
            almacenes_sucursal_actual = almacenes
    else:
        almacenes_sucursal_actual = almacenes

    # Lista de usuarios de la empresa para campo "Recibe" (estrictamente del tenant/cliente)
    usuarios_list = User.objects.filter(
        Q(username__iendswith=f"@{empresa_actual.subdominio}") |
        Q(roles_empresa__empresa=empresa_actual),
        is_active=True
    ).distinct().exclude(username__icontains='@crossoversuite').order_by('first_name', 'username')

    for u in usuarios_list:
        nombre_completo = f"{u.first_name} {u.last_name}".strip()
        clean_user = u.username.split('@')[0] if '@' in u.username else u.username
        u.display_name = nombre_completo if nombre_completo else clean_user

    # Usuario creador display
    creador_display = f"{request.user.first_name} {request.user.last_name}".strip()
    if not creador_display:
        creador_display = request.user.username.split('@')[0] if '@' in request.user.username else request.user.username

    # Siguiente folio sugerido
    siguiente_folio = SalidaPorUso.generar_siguiente_folio(empresa_actual)

    # Paginación
    paginator = Paginator(salidas_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'page_obj': page_obj,
        'salidas': page_obj,
        'sucursales': sucursales,
        'almacenes': almacenes,
        'sucursal_actual': sucursal_actual,
        'almacenes_sucursal_actual': almacenes_sucursal_actual,
        'usuarios': usuarios_list,
        'creador_display': creador_display,
        'siguiente_folio': siguiente_folio,
        'fecha_hoy': timezone.localdate().strftime('%Y-%m-%d'),
        'fecha_hoy_display': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
        'filtros': {
            'q': q,
            'sucursal': sucursal_id,
            'almacen': almacen_id,
            'estado': estado,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
        }
    }
    return render(request, 'almacenes/dashboard_salida_por_uso.html', contexto)


@login_required
def api_almacenes_sucursal(request, sucursal_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    almacenes = Almacen.objects.filter(empresa=empresa_actual)
    if sucursal_id and int(sucursal_id) > 0:
        almacenes = almacenes.filter(sucursal_id=sucursal_id)

    data = [{'id': a.id, 'nombre': a.nombre} for a in almacenes.order_by('nombre')]
    return JsonResponse({'success': True, 'almacenes': data})


@login_required
@require_inventory_permission('salida_por_uso', 'ver', json_response=True)
def api_articulos_salida_almacen(request, almacen_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    inventarios = Inventario.objects.filter(
        almacen=almacen,
        empresa=empresa_actual,
        producto__empresa=empresa_actual,
        cantidad__gt=0
    ).select_related('producto').order_by('producto__nombre')

    data = []
    for inv in inventarios:
        p = inv.producto
        disp = inv.cantidad - inv.reservado
        data.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo': getattr(p, 'codigo_barras', '') or getattr(p, 'codigo', '') or '',
            'stock_fisico': float(inv.cantidad),
            'reservado': float(inv.reservado),
            'disponible': float(max(0, disp)),
            'unidad_medida': getattr(p, 'unidad_medida_display', None) or p.unidad_medida or 'Pieza',
            'costo_unitario': float(inv.costo_promedio or getattr(p, 'precio_costo', 0) or 0),
            'maneja_lote': getattr(p, 'maneja_lote', False),
            'maneja_serie': getattr(p, 'maneja_serie', False),
            'maneja_caducidad': getattr(p, 'maneja_caducidad', False),
        })
    return JsonResponse({'success': True, 'productos': data})


@login_required
@require_inventory_permission('salida_por_uso', 'ver', json_response=True)
def api_extras_salida_almacen(request, almacen_id, producto_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
    extras = DetalleRecepcionExtra.objects.filter(
        almacen=almacen,
        almacen__empresa=empresa_actual
    ).filter(
        Q(detalle_recepcion__producto=producto, detalle_recepcion__recepcion__empresa=empresa_actual) |
        Q(producto=producto, producto__empresa=empresa_actual)
    ).order_by('id')

    data = []
    for e in extras:
        if e.tipo in ['lote', 'caducidad'] and (e.cantidad_lote or 0) <= 0:
            continue
        data.append({
            'id': e.id,
            'tipo': e.tipo,
            'lote': e.lote or '',
            'serie': e.serie or '',
            'fecha_caducidad': e.fecha_caducidad.strftime('%d/%m/%Y') if e.fecha_caducidad else '',
            'disponible': float(e.cantidad_lote) if e.tipo in ['lote', 'caducidad'] else 1
        })
    return JsonResponse({'success': True, 'extras': data})


@login_required
@require_inventory_permission('salida_por_uso', 'crear', json_response=True)
def api_crear_salida_por_uso(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = json.loads(request.POST.get('data', '{}'))
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'JSON inválido: {str(e)}'}, status=400)

    sucursal_id = data.get('sucursal_id')
    almacen_id = data.get('almacen_id')
    fecha_salida = data.get('fecha_salida')
    usuario_recibe_id = data.get('usuario_recibe_id')
    notas = data.get('notas', '').strip()
    articulos = data.get('articulos', [])

    if not almacen_id:
        return JsonResponse({'success': False, 'error': 'Debe seleccionar un almacén.'}, status=400)
    if not usuario_recibe_id:
        return JsonResponse({'success': False, 'error': 'Debe seleccionar el usuario que recibe.'}, status=400)
    if not fecha_salida:
        fecha_salida = timezone.localdate()
    if not articulos:
        return JsonResponse({'success': False, 'error': 'Debe agregar al menos un artículo a la salida.'}, status=400)

    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    sucursal = None
    if sucursal_id:
        sucursal = Sucursal.objects.filter(id=sucursal_id, empresa=empresa_actual).first()
    if not sucursal and almacen.sucursal:
        sucursal = almacen.sucursal

    usuario_recibe = get_object_or_404(User, id=usuario_recibe_id)
    # Validar estrictamente que el usuario pertenezca a la empresa del cliente
    is_client_user = (
        usuario_recibe.username.lower().endswith(f"@{empresa_actual.subdominio.lower()}") or
        usuario_recibe.roles_empresa.filter(empresa=empresa_actual).exists()
    ) and ('@crossoversuite' not in usuario_recibe.username.lower())
    if not is_client_user:
        return JsonResponse({'success': False, 'error': 'El usuario seleccionado no pertenece a esta empresa.'}, status=400)

    try:
        with transaction.atomic():
            folio = SalidaPorUso.generar_siguiente_folio(empresa_actual)
            salida = SalidaPorUso.objects.create(
                empresa=empresa_actual,
                folio=folio,
                sucursal=sucursal,
                almacen=almacen,
                fecha_salida=fecha_salida,
                usuario_creador=request.user,
                usuario_recibe=usuario_recibe,
                estado='borrador',
                notas=notas
            )

            for art in articulos:
                prod_id = art.get('producto_id')
                cant = Decimal(str(art.get('cantidad', 1)))
                if cant <= 0:
                    continue
                prod = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
                costo = Decimal(str(art.get('costo_unitario', 0)))
                subt = cant * costo
                um = art.get('unidad_medida') or getattr(prod, 'unidad_medida_display', None) or prod.unidad_medida or 'Pieza'
                extras = art.get('extras', [])

                DetalleSalidaPorUso.objects.create(
                    salida=salida,
                    producto=prod,
                    unidad_medida=um,
                    cantidad=cant,
                    costo_unitario=costo,
                    subtotal=subt,
                    extras_data=extras
                )

        return JsonResponse({
            'success': True,
            'id': salida.id,
            'folio': salida.folio,
            'message': f'Salida por uso {salida.folio} creada exitosamente en estado Borrador.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al crear la salida: {str(e)}'}, status=500)


@login_required
@require_inventory_permission('salida_por_uso', 'editar', json_response=True)
def api_actualizar_salida_por_uso(request, salida_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    salida = get_object_or_404(SalidaPorUso, id=salida_id, empresa=empresa_actual)

    if salida.estado != 'borrador':
        return JsonResponse({'success': False, 'error': f'La salida se encuentra en estado {salida.get_estado_display()}. Solo se pueden editar salidas en estado Borrador.'}, status=400)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = json.loads(request.POST.get('data', '{}'))
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'JSON inválido: {str(e)}'}, status=400)

    sucursal_id = data.get('sucursal_id')
    almacen_id = data.get('almacen_id')
    fecha_salida = data.get('fecha_salida')
    usuario_recibe_id = data.get('usuario_recibe_id')
    notas = data.get('notas', '').strip()
    articulos = data.get('articulos', [])

    if not almacen_id:
        return JsonResponse({'success': False, 'error': 'Debe seleccionar un almacén.'}, status=400)
    if not usuario_recibe_id:
        return JsonResponse({'success': False, 'error': 'Debe seleccionar el usuario que recibe.'}, status=400)
    if not fecha_salida:
        fecha_salida = timezone.localdate()
    if not articulos:
        return JsonResponse({'success': False, 'error': 'Debe agregar al menos un artículo a la salida.'}, status=400)

    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    sucursal = None
    if sucursal_id:
        sucursal = Sucursal.objects.filter(id=sucursal_id, empresa=empresa_actual).first()
    if not sucursal and almacen.sucursal:
        sucursal = almacen.sucursal

    usuario_recibe = get_object_or_404(User, id=usuario_recibe_id)
    is_client_user = (
        usuario_recibe.username.lower().endswith(f"@{empresa_actual.subdominio.lower()}") or
        usuario_recibe.roles_empresa.filter(empresa=empresa_actual).exists()
    ) and ('@crossoversuite' not in usuario_recibe.username.lower())
    if not is_client_user:
        return JsonResponse({'success': False, 'error': 'El usuario seleccionado no pertenece a esta empresa.'}, status=400)

    try:
        with transaction.atomic():
            salida.sucursal = sucursal
            salida.almacen = almacen
            salida.fecha_salida = fecha_salida
            salida.usuario_recibe = usuario_recibe
            salida.notas = notas
            salida.save()

            salida.detalles.all().delete()

            for art in articulos:
                prod_id = art.get('producto_id')
                cant = Decimal(str(art.get('cantidad', 1)))
                if cant <= 0:
                    continue
                prod = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
                costo = Decimal(str(art.get('costo_unitario', 0)))
                subt = cant * costo
                um = art.get('unidad_medida') or getattr(prod, 'unidad_medida_display', None) or prod.unidad_medida or 'Pieza'
                extras = art.get('extras', [])

                DetalleSalidaPorUso.objects.create(
                    salida=salida,
                    producto=prod,
                    unidad_medida=um,
                    cantidad=cant,
                    costo_unitario=costo,
                    subtotal=subt,
                    extras_data=extras
                )

        return JsonResponse({
            'success': True,
            'id': salida.id,
            'folio': salida.folio,
            'message': f'Salida por uso {salida.folio} actualizada exitosamente.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al actualizar la salida: {str(e)}'}, status=500)


@login_required
@require_inventory_permission('salida_por_uso', 'aprobar', json_response=True)
def api_aprobar_salida_por_uso(request, salida_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    salida = get_object_or_404(SalidaPorUso, id=salida_id, empresa=empresa_actual)

    if salida.estado != 'borrador':
        return JsonResponse({'success': False, 'error': f'La salida ya se encuentra en estado {salida.get_estado_display()}. Solo se pueden aprobar salidas en borrador.'}, status=400)

    detalles = list(salida.detalles.select_related('producto').all())
    if not detalles:
        return JsonResponse({'success': False, 'error': 'La salida no tiene artículos para descontar.'}, status=400)

    try:
        with transaction.atomic():
            for det in detalles:
                Inventario.registrar_salida(
                    almacen=salida.almacen,
                    producto=det.producto,
                    cantidad_salida=det.cantidad,
                    referencia=f"Salida por uso {salida.folio}",
                    quitar_reserva=0,
                    extras_data=det.extras_data if det.extras_data else None,
                    usuario=request.user
                )

            salida.estado = 'aprobada'
            salida.fecha_aprobacion = timezone.now()
            salida.usuario_aprueba = request.user
            salida.save()

        return JsonResponse({
            'success': True,
            'estado': 'aprobada',
            'estado_display': 'Aprobada',
            'message': f'Salida por uso {salida.folio} aprobada con éxito. Inventario descontado y registrado en Kardex.'
        })
    except IntegrityError as ie:
        return JsonResponse({'success': False, 'error': str(ie)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al aprobar salida: {str(e)}'}, status=500)


@login_required
@require_inventory_permission('salida_por_uso', 'cancelar', json_response=True)
def api_cancelar_salida_por_uso(request, salida_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    salida = get_object_or_404(SalidaPorUso, id=salida_id, empresa=empresa_actual)

    # Si está en borrador: se elimina el registro
    if salida.estado == 'borrador':
        folio = salida.folio
        salida.delete()
        return JsonResponse({
            'success': True,
            'action': 'deleted',
            'message': f'La salida {folio} en estado Borrador ha sido cancelada y eliminada.'
        })

    # Si ya está cancelada: error
    if salida.estado == 'cancelada':
        return JsonResponse({'success': False, 'error': 'Esta salida ya se encuentra cancelada.'}, status=400)

    # Si está aprobada: se cancela y se regresan los materiales
    if salida.estado == 'aprobada':
        try:
            motivo = request.POST.get('motivo', '').strip()
            if not motivo and request.content_type == 'application/json':
                try:
                    b_data = json.loads(request.body)
                    motivo = b_data.get('motivo', '').strip()
                except Exception:
                    pass

            with transaction.atomic():
                for det in salida.detalles.select_related('producto').all():
                    # 1. Regresar cantidad física a Inventario
                    inv, _ = Inventario.objects.select_for_update().get_or_create(
                        producto=det.producto,
                        almacen=salida.almacen,
                        defaults={
                            'empresa': empresa_actual,
                            'sucursal': salida.almacen.sucursal,
                            'cantidad': 0,
                            'costo_promedio': det.costo_unitario
                        }
                    )
                    stock_anterior = inv.cantidad
                    inv.cantidad = F('cantidad') + det.cantidad
                    inv.save()
                    inv.refresh_from_db()

                    # 2. Revertir trazabilidad (lotes / series / caducidades)
                    lotes_restaurados = []
                    series_restauradas = []
                    if det.extras_data:
                        for extra_item in det.extras_data:
                            eid = extra_item.get('id')
                            eqty = Decimal(str(extra_item.get('qty', 1)))
                            try:
                                extra_obj = DetalleRecepcionExtra.objects.select_for_update().get(id=eid)
                                if extra_obj.tipo == 'serie':
                                    extra_obj.almacen = salida.almacen
                                    extra_obj.save()
                                    if extra_obj.serie:
                                        series_restauradas.append(extra_obj.serie)
                                else:
                                    extra_obj.cantidad_lote = F('cantidad_lote') + eqty
                                    extra_obj.save()
                                    nombre_lote = extra_obj.lote or (extra_obj.fecha_caducidad.strftime('%d/%m/%Y') if extra_obj.fecha_caducidad else str(extra_obj.id))
                                    lotes_restaurados.append(nombre_lote)
                            except DetalleRecepcionExtra.DoesNotExist:
                                pass

                    # 3. Registrar entrada de reversión en Kardex
                    Kardex.objects.create(
                        empresa=empresa_actual,
                        sucursal=salida.almacen.sucursal,
                        producto=det.producto,
                        almacen=salida.almacen,
                        tipo_movimiento='entrada',
                        cantidad=det.cantidad,
                        stock_anterior=stock_anterior,
                        stock_nuevo=inv.cantidad,
                        referencia=f"Cancelación salida por uso {salida.folio}",
                        lote=", ".join(dict.fromkeys(lotes_restaurados)) if lotes_restaurados else None,
                        serie=", ".join(dict.fromkeys(series_restauradas)) if series_restauradas else None,
                        usuario=request.user
                    )

                salida.estado = 'cancelada'
                salida.fecha_cancelacion = timezone.now()
                salida.usuario_cancela = request.user
                if motivo:
                    salida.motivo_cancelacion = motivo
                salida.save()

            return JsonResponse({
                'success': True,
                'action': 'cancelled',
                'estado': 'cancelada',
                'estado_display': 'Cancelada',
                'message': f'Salida {salida.folio} cancelada exitosamente. Se regresaron los materiales al almacén {salida.almacen.nombre} y se asentó en Kardex.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error al cancelar salida: {str(e)}'}, status=500)

    return JsonResponse({'success': False, 'error': f'Estado desconocido: {salida.estado}'}, status=400)


@login_required
@require_inventory_permission('salida_por_uso', 'ver', json_response=True)
def api_detalle_salida_por_uso(request, salida_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    salida = get_object_or_404(
        SalidaPorUso.objects.select_related(
            'sucursal', 'almacen', 'usuario_creador', 'usuario_recibe', 'usuario_aprueba', 'usuario_cancela'
        ).prefetch_related('detalles__producto'),
        id=salida_id,
        empresa=empresa_actual
    )

    detalles_data = []
    for d in salida.detalles.all():
        extras_display = []
        if d.extras_data:
            for ex in d.extras_data:
                tipo = ex.get('tipo', '')
                if tipo == 'serie':
                    extras_display.append(f"Serie: {ex.get('serie', '')}")
                elif tipo == 'lote':
                    extras_display.append(f"Lote: {ex.get('lote', '')} (Cant: {ex.get('qty', '')})")
                elif tipo == 'caducidad':
                    extras_display.append(f"Cad: {ex.get('fecha_caducidad', '')} (Cant: {ex.get('qty', '')})")

        detalles_data.append({
            'id': d.id,
            'producto_id': d.producto_id,
            'producto_nombre': d.producto.nombre,
            'producto_codigo': getattr(d.producto, 'codigo_barras', '') or getattr(d.producto, 'codigo', '') or '',
            'unidad_medida': d.unidad_medida,
            'cantidad': float(d.cantidad),
            'costo_unitario': float(d.costo_unitario),
            'subtotal': float(d.subtotal),
            'extras': d.extras_data,
            'extras_str': ", ".join(extras_display) if extras_display else "--"
        })

    def get_user_name(u):
        if not u:
            return "--"
        nombre = f"{u.first_name} {u.last_name}".strip()
        return nombre if nombre else (u.username.split('@')[0] if '@' in u.username else u.username)

    data = {
        'id': salida.id,
        'folio': salida.folio,
        'sucursal_id': salida.sucursal_id,
        'sucursal': salida.sucursal.nombre if salida.sucursal else 'Sin Sucursal',
        'almacen_id': salida.almacen_id,
        'almacen': salida.almacen.nombre,
        'fecha_salida': salida.fecha_salida.strftime('%d/%m/%Y') if salida.fecha_salida else '--',
        'fecha_salida_iso': salida.fecha_salida.strftime('%Y-%m-%d') if salida.fecha_salida else '',
        'fecha_creacion': salida.fecha_creacion.strftime('%d/%m/%Y %H:%M') if salida.fecha_creacion else '--',
        'usuario_creador': get_user_name(salida.usuario_creador),
        'usuario_recibe_id': salida.usuario_recibe_id,
        'usuario_recibe': get_user_name(salida.usuario_recibe),
        'estado': salida.estado,
        'estado_display': salida.get_estado_display(),
        'notas': salida.notas or '',
        'fecha_aprobacion': salida.fecha_aprobacion.strftime('%d/%m/%Y %H:%M') if salida.fecha_aprobacion else None,
        'usuario_aprueba': get_user_name(salida.usuario_aprueba) if salida.usuario_aprueba else None,
        'fecha_cancelacion': salida.fecha_cancelacion.strftime('%d/%m/%Y %H:%M') if salida.fecha_cancelacion else None,
        'usuario_cancela': get_user_name(salida.usuario_cancela) if salida.usuario_cancela else None,
        'motivo_cancelacion': salida.motivo_cancelacion or None,
        'total_piezas': float(salida.total_piezas),
        'total_articulos': salida.total_articulos,
        'total_costo': float(salida.total_costo),
        'detalles': detalles_data
    }
    return JsonResponse({'success': True, 'salida': data})


