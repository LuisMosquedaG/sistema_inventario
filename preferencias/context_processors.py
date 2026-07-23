from .permissions import (
    get_sales_ui_permissions, 
    user_has_module_permission, 
    get_granular_sales_permissions, 
    get_granular_purchase_permissions,
    user_has_purchase_permission,
    get_granular_production_permissions,
    user_has_production_permission,
    get_granular_inventory_permissions,
    user_has_inventory_permission,
    user_has_treasury_permission,
    get_granular_treasury_permissions,
    user_has_hr_permission,
    get_granular_hr_permissions,
    SALES_PERMISSION_MATRIX,
    PURCHASES_PERMISSION_MATRIX,
    PRODUCTION_PERMISSION_MATRIX,
    INVENTORY_PERMISSION_MATRIX,
    TREASURY_PERMISSION_MATRIX,
    HR_PERMISSION_MATRIX
)


def app_permissions(request):
    from .permissions import get_empresa_actual
    empresa_actual = get_empresa_actual(request)

    sales_matrix = SALES_PERMISSION_MATRIX
    if empresa_actual and not getattr(empresa_actual, 'modulo_pos', True):
        sales_matrix = {k: v for k, v in SALES_PERMISSION_MATRIX.items() if k not in ['punto_de_venta', 'cortes_de_caja']}

    if not request.user.is_authenticated:
        return {
            'sales_ui_permissions': {},
            'purchase_ui_permissions': {},
            'inventory_ui_permissions': {},
            'production_ui_permissions': {},
            'treasury_ui_permissions': {},
            'hr_ui_permissions': {},
            'perms_produccion': {},
            'granular_sales_perms': {},
            'granular_purchase_perms': {},
            'granular_production_perms': {},
            'granular_inventory_perms': {},
            'granular_treasury_perms': {},
            'granular_hr_perms': {},
            'sales_permission_matrix': sales_matrix,
            'purchases_permission_matrix': PURCHASES_PERMISSION_MATRIX,
            'production_permission_matrix': PRODUCTION_PERMISSION_MATRIX,
            'inventory_permission_matrix': INVENTORY_PERMISSION_MATRIX,
            'treasury_permission_matrix': TREASURY_PERMISSION_MATRIX,
            'hr_permission_matrix': HR_PERMISSION_MATRIX,
        }
    
    # Permisos de Producción (Compatibilidad o legacy perms_produccion si se usa aún)
    p_produccion_legacy = {
        'ver': user_has_module_permission(request, 'produccion', 'ver'),
        'crear': user_has_module_permission(request, 'produccion', 'crear'),
        'editar': user_has_module_permission(request, 'produccion', 'editar'),
        'eliminar': user_has_module_permission(request, 'produccion', 'eliminar'),
    }

    # Permisos de Tesorería
    p_treasury_ui = {
        'cajas_bancos': user_has_treasury_permission(request, 'cajas_bancos', 'ver'),
        'egresos': user_has_treasury_permission(request, 'egresos', 'ver'),
        'ingresos': user_has_treasury_permission(request, 'ingresos', 'ver'),
    }

    # Permisos de Compras
    p_purchase_ui = {
        'proveedores': user_has_purchase_permission(request, 'proveedores', 'ver'),
        'solicitudes': user_has_purchase_permission(request, 'solicitudes', 'ver'),
        'ordenes_compra': user_has_purchase_permission(request, 'ordenes_compra', 'ver'),
        'recepciones': user_has_purchase_permission(request, 'recepciones', 'ver'),
    }

    # Permisos de Producción Granular (UI general)
    p_production_ui = {
        'tablero_control': user_has_production_permission(request, 'tablero_control', 'ver'),
        'catalogos_test': user_has_production_permission(request, 'catalogos_test', 'ver'),
    }

    # Permisos de Inventario
    p_inventory_ui = {
        'inventario': user_has_inventory_permission(request, 'inventario', 'ver'),
        'kardex': user_has_inventory_permission(request, 'kardex', 'ver'),
        'almacenes': user_has_inventory_permission(request, 'almacenes', 'ver'),
        'categorias': user_has_inventory_permission(request, 'categorias', 'ver'),
        'listas': user_has_inventory_permission(request, 'listas', 'ver'),
    }

    # Permisos de Costeos
    p_costing_ui = {
        'costeos': user_has_module_permission(request, 'costeos', 'ver'),
    }

    # Permisos de Recursos Humanos
    p_hr_ui = {
        'empleados': user_has_hr_permission(request, 'empleados', 'ver'),
        'contratos': user_has_hr_permission(request, 'contratos', 'ver'),
        'contratistas': user_has_hr_permission(request, 'contratistas', 'ver'),
        'beneficiarios': user_has_hr_permission(request, 'beneficiarios', 'ver'),
        'sua': user_has_hr_permission(request, 'sua', 'ver'),
        'nomina': user_has_hr_permission(request, 'nomina', 'ver'),
    }

    return {
        'sales_ui_permissions': get_sales_ui_permissions(request),
        'costing_ui_permissions': p_costing_ui,
        'purchase_ui_permissions': p_purchase_ui,
        'production_ui_permissions': p_production_ui,
        'inventory_ui_permissions': p_inventory_ui,
        'treasury_ui_permissions': p_treasury_ui,
        'hr_ui_permissions': p_hr_ui,
        'perms_produccion': p_produccion_legacy,
        'granular_sales_perms': get_granular_sales_permissions(request),
        'granular_purchase_perms': get_granular_purchase_permissions(request),
        'granular_production_perms': get_granular_production_permissions(request),
        'granular_inventory_perms': get_granular_inventory_permissions(request),
        'granular_treasury_perms': get_granular_treasury_permissions(request),
        'granular_hr_perms': get_granular_hr_permissions(request),
        'sales_permission_matrix': sales_matrix,
        'purchases_permission_matrix': PURCHASES_PERMISSION_MATRIX,
        'production_permission_matrix': PRODUCTION_PERMISSION_MATRIX,
        'inventory_permission_matrix': INVENTORY_PERMISSION_MATRIX,
        'treasury_permission_matrix': TREASURY_PERMISSION_MATRIX,
        'hr_permission_matrix': HR_PERMISSION_MATRIX,
    }
