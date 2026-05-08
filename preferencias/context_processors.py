from .permissions import (
    get_sales_ui_permissions, 
    user_has_module_permission, 
    get_granular_sales_permissions, 
    get_granular_purchase_permissions,
    user_has_purchase_permission,
    get_granular_production_permissions,
    user_has_production_permission,
    get_granular_inventory_permissions,
    user_has_inventory_permission
)


def app_permissions(request):
    if not request.user.is_authenticated:
        return {
            'sales_ui_permissions': {
                'clientes': False,
                'actividades': False,
                'cotizaciones': False,
                'pedidos': False,
                'salidas': False,
            },
            'purchase_ui_permissions': {
                'proveedores': False,
                'solicitudes': False,
                'ordenes_compra': False,
                'recepciones': False,
            },
            'inventory_ui_permissions': {
                'inventario': False,
                'kardex': False,
                'almacenes': False,
                'categorias': False,
            },
            'perms_produccion': {
                'ver': False, 'crear': False, 'editar': False, 'eliminar': False, 'aprobar': False, 'imprimir': False
            },
            'granular_sales_perms': {},
            'granular_purchase_perms': {},
            'granular_production_perms': {},
            'granular_inventory_perms': {}
        }
    
    # Permisos de Producción (Compatibilidad o legacy perms_produccion si se usa aún)
    p_produccion_legacy = {
        'ver': user_has_module_permission(request, 'produccion', 'ver'),
        'crear': user_has_module_permission(request, 'produccion', 'crear'),
        'editar': user_has_module_permission(request, 'produccion', 'editar'),
        'eliminar': user_has_module_permission(request, 'produccion', 'eliminar'),
        'aprobar': user_has_module_permission(request, 'produccion', 'aprobar'),
        'imprimir': user_has_module_permission(request, 'produccion', 'imprimir'),
    }

    p_purchase_ui = {
        'proveedores': user_has_purchase_permission(request, 'proveedores', 'ver'),
        'solicitudes': user_has_purchase_permission(request, 'solicitudes', 'ver'),
        'ordenes_compra': user_has_purchase_permission(request, 'ordenes_compra', 'ver'),
        'recepciones': user_has_purchase_permission(request, 'recepciones', 'ver'),
    }

    p_production_ui = {
        'tablero_control': user_has_production_permission(request, 'tablero_control', 'ver'),
        'catalogos_test': user_has_production_permission(request, 'catalogos_test', 'ver'),
    }

    p_inventory_ui = {
        'inventario': user_has_inventory_permission(request, 'inventario', 'ver'),
        'kardex': user_has_inventory_permission(request, 'kardex', 'ver'),
        'almacenes': user_has_inventory_permission(request, 'almacenes', 'ver'),
        'categorias': user_has_inventory_permission(request, 'categorias', 'ver'),
    }

    return {
        'sales_ui_permissions': get_sales_ui_permissions(request),
        'purchase_ui_permissions': p_purchase_ui,
        'production_ui_permissions': p_production_ui,
        'inventory_ui_permissions': p_inventory_ui,
        'perms_produccion': p_produccion_legacy,
        'granular_sales_perms': get_granular_sales_permissions(request),
        'granular_purchase_perms': get_granular_purchase_permissions(request),
        'granular_production_perms': get_granular_production_permissions(request),
        'granular_inventory_perms': get_granular_inventory_permissions(request)
    }
