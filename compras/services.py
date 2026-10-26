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
    sucursal_empresa_id = data_post.get('sucursal_empresa') # Sucursal de la EMPRESA
    almacen_id = data_post.get('almacen')
    moneda_id = data_post.get('moneda')
    tipo_cambio = data_post.get('tipo_cambio', '1.0000')
    descuento = data_post.get('descuento', '0.00')
    fecha_str = data_post.get('fecha')
    notas = data_post.get('notas')

    if not proveedor:
        raise ValueError("El proveedor es obligatorio.")

    from proveedores.models import Proveedor, SucursalProveedor
    from almacenes.models import Almacen
    from preferencias.models import Moneda

    prov_obj = Proveedor.objects.filter(id=proveedor, empresa=empresa_actual).first()
    if not prov_obj:
        raise ValueError("El proveedor seleccionado no es válido o no pertenece a tu empresa.")

    suc_prov_obj = None
    if sucursal_id:
        suc_prov_obj = SucursalProveedor.objects.filter(id=sucursal_id, proveedor=prov_obj).first()

    alm_obj = None
    if almacen_id:
        alm_obj = Almacen.objects.filter(id=almacen_id, empresa=empresa_actual).first()
        if not alm_obj:
            raise ValueError("El almacén destino no pertenece a tu empresa.")

    moneda_obj = None
    if moneda_id:
        moneda_obj = Moneda.objects.filter(id=moneda_id, empresa=empresa_actual).first()
        if not moneda_obj:
            raise ValueError("La moneda seleccionada no pertenece a tu empresa.")

    # Asignar sucursal desde POST o desde la sesión
    sucursal_empresa_obj = None
    final_sucursal_empresa_id = sucursal_empresa_id or session_sucursal_id
    
    if final_sucursal_empresa_id:
        from preferencias.models import Sucursal
        try:
            sucursal_empresa_obj = Sucursal.objects.get(id=final_sucursal_empresa_id, empresa=empresa_actual)
        except Sucursal.DoesNotExist:
            pass

    aplica_iva = data_post.get('aplica_iva') == 'on'

    # Parsear fecha si se proporciona
    fecha = None
    if fecha_str:
        from datetime import datetime
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # 2. Crear la Cabecera (OrdenCompra)
    create_kwargs = {
        'proveedor': prov_obj,
        'sucursal': suc_prov_obj, 
        'almacen_destino': alm_obj,
        'moneda': moneda_obj,
        'tipo_cambio': tipo_cambio,
        'descuento': descuento,
        'notas': notas,
        'estado': 'borrador',
        'usuario': usuario,
        'empresa': empresa_actual,
        'sucursal_empresa': sucursal_empresa_obj,
        'aplica_iva': aplica_iva
    }
    if fecha:
        create_kwargs['fecha'] = fecha

    orden = OrdenCompra.objects.create(**create_kwargs)

    # 3. Procesar la lista de ítems
    productos_ids = data_post.getlist('producto_id[]')
    cantidades = data_post.getlist('cantidad[]')
    precios = data_post.getlist('precio_unitario[]')
    unidades_compra = data_post.getlist('unidad_compra[]')
    factores_conv = data_post.getlist('factor_conversion[]')
    cantidades_inv = data_post.getlist('cantidad_inventario[]')

    items_creados = 0

    for i in range(len(productos_ids)):
        prod_id = productos_ids[i]
        cant_str = cantidades[i] if i < len(cantidades) else 0
        precio_str = precios[i] if i < len(precios) else 0.0
        u_compra = unidades_compra[i] if i < len(unidades_compra) else ''

        # Validaciones individuales del ítem
        if not prod_id or prod_id == "":
            continue

        try:
            cant = int(cant_str)
            precio = float(precio_str)
        except ValueError:
            continue # Ignorar líneas con datos inválidos

        try:
            f_conv = Decimal(str(factores_conv[i])) if i < len(factores_conv) and factores_conv[i] else Decimal('1.0000')
        except Exception:
            f_conv = Decimal('1.0000')

        try:
            c_inv = Decimal(str(cantidades_inv[i])) if i < len(cantidades_inv) and cantidades_inv[i] else (Decimal(str(cant)) * f_conv)
        except Exception:
            c_inv = Decimal(str(cant)) * f_conv

        if cant > 0:
            prod_obj = Producto.objects.filter(id=prod_id, empresa=empresa_actual).first()
            if not prod_obj:
                continue
            DetalleCompra.objects.create(
                orden_compra=orden,
                producto=prod_obj,
                cantidad=cant,
                precio_costo=precio,
                unidad_compra=u_compra or None,
                factor_conversion=f_conv,
                cantidad_inventario=c_inv
            )
            items_creados += 1
    
    if items_creados == 0:
        orden.delete() # Si no hay items, borramos la orden vacía
        raise ValueError("Debes agregar al menos un producto válido.")

    return orden