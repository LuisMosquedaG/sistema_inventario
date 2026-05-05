from .permissions import get_sales_ui_permissions


def app_permissions(request):
    if not request.user.is_authenticated:
        return {
            'sales_ui_permissions': {
                'clientes': False,
                'actividades': False,
                'cotizaciones': False,
                'pedidos': False,
                'salidas': False,
            }
        }
    return {
        'sales_ui_permissions': get_sales_ui_permissions(request)
    }
