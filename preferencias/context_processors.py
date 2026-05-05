from .permissions import get_sales_ui_permissions, user_has_module_permission, get_granular_sales_permissions


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
            'perms_produccion': {
                'ver': False, 'crear': False, 'editar': False, 'eliminar': False, 'aprobar': False, 'imprimir': False
            },
            'granular_sales_perms': {}
        }
    
    # Permisos de Producción
    p_produccion = {
        'ver': user_has_module_permission(request, 'produccion', 'ver'),
        'crear': user_has_module_permission(request, 'produccion', 'crear'),
        'editar': user_has_module_permission(request, 'produccion', 'editar'),
        'eliminar': user_has_module_permission(request, 'produccion', 'eliminar'),
        'aprobar': user_has_module_permission(request, 'produccion', 'aprobar'),
        'imprimir': user_has_module_permission(request, 'produccion', 'imprimir'),
    }

    return {
        'sales_ui_permissions': get_sales_ui_permissions(request),
        'perms_produccion': p_produccion,
        'granular_sales_perms': get_granular_sales_permissions(request)
    }
