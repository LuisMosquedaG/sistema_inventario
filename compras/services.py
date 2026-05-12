from django.db import transaction
from decimal import Decimal
from .models import OrdenCompra, DetalleCompra
from core.models import Producto

@transaction.atomic
def crear_orden_compra_servicio(usuario, data_post, empresa_actual, session_sucursal_id=None):
    """
    Servicio que maneja la lógica de creación de Orden de Compra.
    Separa la lógica de negocio de la vista.
    """
    
    # 1. Validaciones y Extracción de Datos de Cabecera
    proveedor = data_post.get('proveedor')
    sucursal_id = data_post.get('sucursal') # Esta es la sucursal del PROVEEDOR
    almacen_id = data_post.get('almacen')
    moneda_id = data_post.get('moneda')
    tipo_cambio = data_post.get('tipo_cambio', '1.0000')
    fecha = data_post.get('fecha')
    notas = data_post.get('notas')

    if not proveedor:
        raise ValueError("El proveedor es obligatorio.")

    # Asignar sucursal desde la sesión
    sucursal_empresa_obj = None
    if session_sucursal_id:
        from preferencias.models import Sucursal
        try:
            sucursal_empresa_obj = Sucursal.objects.get(id=session_sucursal_id, empresa=empresa_actual)
        except Sucursal.DoesNotExist:
            pass

    # 2. Crear la Cabecera (OrdenCompra)
    orden = OrdenCompra.objects.create(
        proveedor_id=proveedor,
        sucursal_id=sucursal_id if sucursal_id else None, 
        almacen_destino_id=almacen_id if almacen_id else None,
        moneda_id=moneda_id if moneda_id else None,
        tipo_cambio=tipo_cambio,
        fecha=fecha,
        notas=notas,
        estado='borrador',
        usuario=usuario,
        empresa=empresa_actual,
        sucursal_empresa=sucursal_empresa_obj
    )

    # 3. Procesar la lista de ítems
    productos_ids = data_post.getlist('producto_id[]')
    cantidades = data_post.getlist('cantidad[]')
    precios = data_post.getlist('precio_unitario[]')

    items_creados = 0

    for i in range(len(productos_ids)):
        prod_id = productos_ids[i]
        cant_str = cantidades[i] if i < len(cantidades) else 0
        precio_str = precios[i] if i < len(precios) else 0.0

        # Validaciones individuales del ítem
        if not prod_id or prod_id == "":
            continue

        try:
            cant = int(cant_str)
            precio = float(precio_str)
        except ValueError:
            continue # Ignorar líneas con datos inválidos

        if cant > 0:
            DetalleCompra.objects.create(
                orden_compra=orden,
                producto_id=prod_id,
                cantidad=cant,
                precio_costo=precio
            )
            items_creados += 1
    
    if items_creados == 0:
        orden.delete() # Si no hay items, borramos la orden vacía
        raise ValueError("Debes agregar al menos un producto válido.")

    return orden