from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
import json
from decimal import Decimal
from .models import Almacen, Inventario, Kardex
from core.models import Producto
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

@login_required(login_url='/login/')
def lista_almacenes(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    almacenes = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')
    return render(request, 'dashboard_almacenes.html', {'almacenes': almacenes})

@login_required(login_url='/login/')
def dashboard_kardex(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Filtros
    q = request.GET.get('q')
    producto_id = request.GET.get('producto')
    almacen_id = request.GET.get('almacen')
    tipo_movimiento = request.GET.get('tipo_movimiento')

    movimientos = Kardex.objects.filter(empresa=empresa_actual).select_related('producto', 'almacen').order_by('-fecha')

    if q:
        movimientos = movimientos.filter(
            Q(producto__nombre__icontains=q) | Q(lote__icontains=q) | Q(serie__icontains=q)
        )
    if producto_id:
        movimientos = movimientos.filter(producto_id=producto_id)
    if almacen_id:
        movimientos = movimientos.filter(almacen_id=almacen_id)
    if tipo_movimiento:
        movimientos = movimientos.filter(tipo_movimiento=tipo_movimiento)

    productos = Producto.objects.filter(empresa=empresa_actual).order_by('nombre')
    almacenes = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')

    contexto = {
        'movimientos': movimientos[:100],
        'productos': productos,
        'almacenes': almacenes,
        'filtros': {
            'q': q or '',
            'producto': int(producto_id) if producto_id else '',
            'almacen': int(almacen_id) if almacen_id else '',
            'tipo_movimiento': tipo_movimiento or ''
        }
    }
    return render(request, 'dashboard_kardex.html', contexto)

# --- APIS ALMACÉN ---

@login_required
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
                empresa=empresa_actual
            )
            return JsonResponse({'success': True, 'message': 'Almacén creado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
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
        'telefono': almacen.telefono
    })

@login_required
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
            almacen.save()
            return JsonResponse({'success': True, 'message': 'Almacén actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- APIs PARA TRASLADOS ---

@login_required
def api_productos_con_stock(request, almacen_id):
    """Retorna productos que tienen existencia física en el almacén de origen"""
    empresa_actual = get_empresa_actual(request)
    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    
    inventarios = Inventario.objects.filter(almacen=almacen, cantidad__gt=0).select_related('producto')
    
    data = []
    for inv in inventarios:
        data.append({
            'id': inv.producto.id,
            'nombre': inv.producto.nombre,
            'total': inv.cantidad,
            'reservado': inv.reservado,
            'disponible': inv.cantidad - inv.reservado,
            'maneja_lote': inv.producto.maneja_lote,
            'maneja_serie': inv.producto.maneja_serie
        })
    return JsonResponse(data, safe=False)

@login_required
def api_extras_producto(request, almacen_id, producto_id):
    """Retorna lotes o series disponibles para un producto en un almacén"""
    empresa_actual = get_empresa_actual(request)
    almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
    
    # Buscamos en DetalleRecepcionExtra que pertenezcan al almacén origen
    extras = DetalleRecepcionExtra.objects.filter(almacen=almacen, detalle_recepcion__producto_id=producto_id)
    
    data = []
    for e in extras:
        if e.tipo == 'lote' and e.cantidad_lote <= 0: continue
        data.append({
            'id': e.id,
            'tipo': e.tipo,
            'lote': e.lote,
            'serie': e.serie,
            'cantidad': e.cantidad_lote if e.tipo == 'lote' else 1
        })
    return JsonResponse(data, safe=False)

@login_required
@transaction.atomic
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
            inv_origen = Inventario.objects.select_for_update().get(almacen=origen, producto=producto)
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
                defaults={'cantidad': 0, 'reservado': 0, 'costo_promedio': inv_origen.costo_promedio, 'empresa': empresa_actual}
            )
            inv_destino.cantidad = F('cantidad') + cantidad
            if piezas_reservadas_movidas > 0:
                inv_destino.reservado = F('reservado') + piezas_reservadas_movidas
            inv_destino.save()

            # 4. ACTUALIZAR LOTE/SERIE (SI APLICA)
            lote_ref, serie_ref = None, None
            if extra_id:
                extra = DetalleRecepcionExtra.objects.get(id=extra_id, almacen=origen)
                if extra.tipo == 'serie':
                    extra.almacen = destino
                    extra.save()
                    serie_ref = extra.serie
                else:
                    # LOTE
                    if extra.cantidad_lote > cantidad:
                        extra.cantidad_lote = F('cantidad_lote') - cantidad
                        extra.save()
                        DetalleRecepcionExtra.objects.create(
                            detalle_recepcion=extra.detalle_recepcion, tipo='lote', lote=extra.lote,
                            cantidad_lote=cantidad, almacen=destino
                        )
                    else:
                        extra.almacen = destino
                        extra.save()
                    lote_ref = extra.lote

            # 5. REGISTRAR EN KARDEX (DOBLE ASIENTO)
            ref_folio = f"TRASLADO-{origen.id}>{destino.id}"
            # Refrescamos objetos para tener el valor numérico real para el Kardex
            inv_origen.refresh_from_db()
            inv_destino.refresh_from_db()

            Kardex.objects.create(
                empresa=empresa_actual, producto=producto, almacen=origen, tipo_movimiento='salida',
                cantidad=cantidad, stock_anterior=inv_origen.cantidad + cantidad, stock_nuevo=inv_origen.cantidad,
                referencia=ref_folio, lote=lote_ref, serie=serie_ref
            )
            Kardex.objects.create(
                empresa=empresa_actual, producto=producto, almacen=destino, tipo_movimiento='entrada',
                cantidad=cantidad, stock_anterior=inv_destino.cantidad - cantidad, stock_nuevo=inv_destino.cantidad,
                referencia=ref_folio, lote=lote_ref, serie=serie_ref
            )

        return JsonResponse({'success': True, 'message': 'Traslado realizado correctamente.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
