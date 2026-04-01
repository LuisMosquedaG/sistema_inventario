# --- Nuevas APIS para Traslados ---
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
    
    extras = DetalleRecepcionExtra.objects.filter(almacen_id=almacen_id, detalle_recepcion__producto_id=producto_id)
    
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
    """Procesa el movimiento de mercancía entre almacenes"""
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        empresa_actual = get_empresa_actual(request)
        data = json.loads(request.body)
        
        origen_id, destino_id = data.get('almacen_origen'), data.get('almacen_destino')
        producto_id, cantidad = data.get('producto_id'), int(data.get('cantidad', 0))
        extra_id = data.get('extra_id') # ID del lote/serie seleccionado

        if origen_id == destino_id: raise ValueError("El almacén origen y destino no pueden ser el mismo.")
        if cantidad <= 0: raise ValueError("La cantidad debe ser mayor a cero.")

        origen, destino = get_object_or_404(Almacen, id=origen_id, empresa=empresa_actual), get_object_or_404(Almacen, id=destino_id, empresa=empresa_actual)
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

        # 1. VALIDAR STOCK EN ORIGEN
        inv_origen = Inventario.objects.select_for_update().get(almacen=origen, producto=producto)
        if inv_origen.cantidad < cantidad: raise ValueError("No hay stock suficiente en el origen.")

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
