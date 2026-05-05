from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from panel.models import Empresa
from .models import AsignacionRolUsuario, PermisoRolModulo, PermisoRolAccion


SALES_PERMISSION_MATRIX = {
    'clientes': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir', 'agenda_contactos'],
    'actividades': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir'],
    'cotizaciones': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir'],
    'pedidos': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir', 'validar_stock', 'registrar_pago'],
    'salidas': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir'],
}


def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None


def user_has_module_permission(request, modulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    empresa = get_empresa_actual(request)
    if not empresa:
        return False

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    # Compatibilidad hacia atras: si no hay rol asignado, conserva acceso.
    if not asignacion:
        return True

    permiso = PermisoRolModulo.objects.filter(
        rol=asignacion.rol,
        modulo=modulo
    ).first()
    if not permiso:
        return False

    return bool(getattr(permiso, f'puede_{accion}', False))


def user_has_sales_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    empresa = get_empresa_actual(request)
    if not empresa:
        return False

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    # Compatibilidad hacia atras
    if not asignacion:
        return True

    permiso_accion = PermisoRolAccion.objects.filter(
        rol=asignacion.rol,
        area='ventas',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)

    # Fallback para salidas ya existentes en PermisoRolModulo
    if submodulo == 'salidas':
        permiso_modulo = PermisoRolModulo.objects.filter(
            rol=asignacion.rol,
            modulo='ventas'
        ).first()
        if permiso_modulo:
            return bool(getattr(permiso_modulo, f'puede_{accion}', False))

    return False


def require_module_permission(modulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_module_permission(request, modulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')

        return wrapped

    return decorator


def require_sales_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_sales_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')

        return wrapped

    return decorator


def get_sales_ui_permissions(request):
    return {
        'clientes': user_has_sales_permission(request, 'clientes', 'ver'),
        'actividades': user_has_sales_permission(request, 'actividades', 'ver'),
        'cotizaciones': user_has_sales_permission(request, 'cotizaciones', 'ver'),
        'pedidos': user_has_sales_permission(request, 'pedidos', 'ver'),
        'salidas': user_has_sales_permission(request, 'salidas', 'ver'),
    }
