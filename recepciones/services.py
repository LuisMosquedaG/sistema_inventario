from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from collections import defaultdict
import json
from .models import Recepcion, DetalleRecepcion, DetalleRecepcionExtra
from compras.models import OrdenCompra, DetalleCompra
from almacenes.models import Inventario, Almacen
from core.models import Producto

@transaction.atomic
def procesar_recepcion_servicio(data_post, empresa_actual):
    """
    Servicio que procesa una recepción completa.
    Maneja validaciones, inventario, lotes/series y actualización de OC.
    """
    
    # 1. OBTENER DATOS DE CABECERA
    oc_id = data_post.get('orden_compra')
    almacen_id = data_post.get('almacen')
    fecha = data_post.get('fecha')
    factura = data_post.get('factura')
    
    pedimento = data_post.get('pedimento')
    aduana = data_post.get('aduana')
    fecha_pedimento = data_post.get('fecha_pedimento')
    importe_aduana = data_post.get('importe_aduana')

    # 2. VALIDAR EXISTENCIA DE OC Y ALMACÉN
    try:
        orden_compra = OrdenCompra.objects.get(id=oc_id)
        if orden_compra.empresa != empresa_actual:
            raise ValueError("Seguridad: La Orden de Compra seleccionada no pertenece a tu empresa.")

        almacen = Almacen.objects.get(id=almacen_id)
        if almacen.empresa != empresa_actual:
            raise ValueError("Seguridad: El Almacén seleccionado no pertenece a tu empresa.")
            
    except (OrdenCompra.DoesNotExist, Almacen.DoesNotExist):
        raise ValueError("La Orden de Compra o el Almacén no existen.")

    # 3. CREAR CABECERA DE RECEPCIÓN
    recepcion = Recepcion.objects.create(
        orden_compra=orden_compra,
        almacen=almacen,
        empresa=empresa_actual, 
        fecha=fecha,
        factura=factura,
        pedimento=pedimento if pedimento else None,
        aduana=aduana if aduana else None,
        fecha_pedimento=fecha_pedimento if fecha_pedimento else None,
        importe_aduana=importe_aduana if importe_aduana else '0.00',
        moneda=orden_compra.moneda,
        tipo_cambio=orden_compra.tipo_cambio,
        estado='completada'
    )

    # 4. RECOLECTAR Y PREPARAR ITEMS (LÓGICA SEGURA)
    detalle_ids = data_post.getlist('detalle_compra_id[]')
    cantidades_recibidas = data_post.getlist('cantidad_recibida[]')
    costos = data_post.getlist('costo_unitario[]')

    items_a_procesar = [] 
    input_acumulado_por_producto = defaultdict(int)

    # RECORREMOS USANDO ZIP PARA EVITAR EL ERROR DE ÍNDICE
    for i in range(len(detalle_ids)):
        det_id_raw = detalle_ids[i]
        cant_raw = cantidades_recibidas[i] if i < len(cantidades_recibidas) else 0
        costo_raw = costos[i] if i < len(costos) else 0.0

        if not det_id_raw: continue
        
        try:
            det_id = int(det_id_raw)
            detalle_original = DetalleCompra.objects.get(id=det_id, orden_compra=orden_compra)
            cant_rec = int(cant_raw) if cant_raw else 0
            costo = Decimal(costo_raw) if costo_raw else Decimal('0.00')

            if cant_rec > 0:
                input_acumulado_por_producto[detalle_original.producto.id] += cant_rec
                items_a_procesar.append({'detalle': detalle_original, 'cantidad': cant_rec, 'costo': costo})
        except (ValueError, DetalleCompra.DoesNotExist):
            continue

    if not items_a_procesar:
        recepcion.delete()
        raise ValueError('No se recibieron datos válidos de artículos. Verifique las cantidades.')

    # 5. VALIDACIÓN GLOBAL (LÍMITES DE OC)
    total_pedido_por_producto = defaultdict(int)
    for det in orden_compra.detalles.all():
        total_pedido_por_producto[det.producto.id] += det.cantidad

    productos_ids = list(input_acumulado_por_producto.keys())
    historial_recepciones = DetalleRecepcion.objects.filter(
        recepcion__orden_compra=orden_compra,
        producto_id__in=productos_ids
    ).exclude(recepcion__estado='cancelada').values('producto_id').annotate(total=Sum('cantidad_recibida'))
    
    mapa_historial = {item['producto_id']: item['total'] for item in historial_recepciones}

    for prod_id, cant_input in input_acumulado_por_producto.items():
        limite = total_pedido_por_producto.get(prod_id, 0)
        ya_recibido = mapa_historial.get(prod_id, 0)
        if (ya_recibido + cant_input) > limite:
            recepcion.delete()
            raise ValueError(f'Error: El producto ID {prod_id} excede el total pedido en la OC.')

    # 6. PROCESAR Y GUARDAR ITEMS
    for item in items_a_procesar:
        detalle_original = item['detalle']
        cant_rec = item['cantidad']
        costo = item['costo']

        detalle_recepcion_creado = DetalleRecepcion.objects.create(
            recepcion=recepcion,
            detalle_compra=detalle_original,
            producto=detalle_original.producto,
            cantidad_recibida=cant_rec,
            costo_unitario=costo
        )
        
        producto = detalle_original.producto

        if producto.tipo != 'servicio':
            tipo_cambio_aplicar = Decimal(orden_compra.tipo_cambio or '1.0000')
            costo_en_pesos = costo * tipo_cambio_aplicar

            # CARGAR LOTES Y SERIES PARA EL KARDEX
            extra_data_json = data_post.get(f'extra_data_{detalle_original.id}')
            lote_kardex = None
            serie_kardex = None
            
            if extra_data_json:
                try:
                    extras_list = json.loads(extra_data_json)
                    for extra in extras_list:
                        DetalleRecepcionExtra.objects.create(
                            detalle_recepcion=detalle_recepcion_creado,
                            tipo=extra['tipo'],
                            lote=extra.get('lote'),
                            cantidad_lote=extra.get('cantidad_lote', 0),
                            serie=extra.get('serie'),
                            almacen=almacen  # <--- ASIGNAR ALMACÉN INICIAL
                        )
                        # Capturar el primero para el Kardex
                        if extra['tipo'] == 'lote' and not lote_kardex:
                            lote_kardex = extra.get('lote')
                        if extra['tipo'] == 'serie' and not serie_kardex:
                            serie_kardex = extra.get('serie')
                except json.JSONDecodeError: pass

            Inventario.registrar_ingreso(
                almacen=almacen,
                producto=producto,
                cantidad_ingreso=cant_rec,
                costo_unitario=costo_en_pesos,
                referencia=f"REC-{recepcion.id:04d}",
                lote=lote_kardex,
                serie=serie_kardex
            )

    # 7. ACTUALIZAR ESTADO DE LA OC
    orden_completa = True
    for prod_id, limite in total_pedido_por_producto.items():
        total_final = DetalleRecepcion.objects.filter(
            recepcion__orden_compra=orden_compra,
            producto_id=prod_id
        ).exclude(recepcion__estado='cancelada').aggregate(total=Sum('cantidad_recibida'))['total'] or 0
        if total_final < limite:
            orden_completa = False
            break
    
    orden_compra.estado = 'recibida' if orden_completa else 'parcial'
    orden_compra.save()

    return recepcion
