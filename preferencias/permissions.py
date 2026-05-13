from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from panel.models import Empresa
from .models import AsignacionRolUsuario, PermisoRolModulo, PermisoRolAccion


SALES_PERMISSION_MATRIX = {
    'clientes': ['ver', 'crear', 'editar', 'agenda_contactos', 'crear_cotizacion'],
    'actividades': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir', 'completar', 'reprogramar', 'cancelar'],
    'cotizaciones': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir'],
    'pedidos': ['ver', 'crear', 'editar', 'imprimir', 'validar_stock', 'revision', 'reservar', 'solicitar', 'generar_solicitud_global', 'registrar_pago'],
    'salidas': ['ver', 'crear', 'imprimir', 'aprobar', 'surtir_orden', 'actualizar_entrega'],
}

PURCHASES_PERMISSION_MATRIX = {
    'proveedores': ['ver', 'crear', 'editar', 'eliminar'],
    'solicitudes': ['ver', 'crear', 'editar', 'imprimir', 'autorizar'],
    'ordenes_compra': ['ver', 'crear', 'editar', 'imprimir', 'registrar_pago', 'consolidar', 'aprobar', 'cancelar'],
    'recepciones': ['ver', 'crear', 'imprimir', 'cancelar'],
}

PRODUCTION_PERMISSION_MATRIX = {
    'tablero_control': ['ver', 'crear', 'imprimir', 'editar', 'iniciar_trabajo', 'cancelar_orden', 'enviar_testeo', 'validar_calidad', 'guardar_avance', 'finalizar_trabajo'],
    'catalogos_test': ['ver', 'crear', 'editar', 'eliminar'],
}

TREASURY_PERMISSION_MATRIX = {
    'ingresos': ['ver', 'cancelar'],
    'egresos': ['ver', 'cancelar'],
    'cajas_bancos': ['ver', 'crear', 'editar'],
}

INVENTORY_PERMISSION_MATRIX = {
    'inventario': ['ver', 'crear', 'receta', 'traslado', 'editar', 'precios', 'existencias', 'recetas'],
    'kardex': ['ver'],
    'almacenes': ['ver', 'crear', 'editar'],
    'categorias': ['ver', 'crear', 'editar', 'eliminar'],
    'listas': ['ver', 'crear', 'editar', 'eliminar'],
}

HR_PERMISSION_MATRIX = {
    'empleados': ['ver', 'crear', 'editar', 'eliminar'],
    'contratos': ['ver', 'crear', 'editar', 'eliminar'],
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

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    mapa_modulos = {
        'ventas': 'modulo_ventas',
        'compras': 'modulo_compras',
        'produccion': 'modulo_produccion',
        'inventario': 'modulo_inventarios',
        'tesoreria': 'modulo_tesoreria',
        'recursos_humanos': 'modulo_recursos_humanos',
    }
    
    campo_modulo = mapa_modulos.get(modulo)
    if campo_modulo and not getattr(empresa, campo_modulo, True):
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    if not asignacion:
        return False

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

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    if not empresa.modulo_ventas:
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    if not asignacion:
        return False

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


def user_has_purchase_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    if not empresa.modulo_compras:
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    if not asignacion:
        return False

    permiso_accion = PermisoRolAccion.objects.filter(
        rol=asignacion.rol,
        area='compras',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)

    return False


def require_purchase_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_purchase_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')

        return wrapped

    return decorator


def get_granular_purchase_permissions(request):
    perms = {}
    for submodulo, acciones in PURCHASES_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_purchase_permission(request, submodulo, accion) for accion in acciones}
    return perms


def user_has_production_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    if not empresa.modulo_produccion:
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    if not asignacion:
        return False

    permiso_accion = PermisoRolAccion.objects.filter(
        rol=asignacion.rol,
        area='produccion',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)

    return False


def require_production_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_production_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')

        return wrapped

    return decorator


def get_granular_production_permissions(request):
    perms = {}
    for submodulo, acciones in PRODUCTION_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_production_permission(request, submodulo, accion) for accion in acciones}
    return perms


def user_has_inventory_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    if not empresa.modulo_inventarios:
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    if not asignacion:
        return False

    permiso_accion = PermisoRolAccion.objects.filter(
        rol=asignacion.rol,
        area='inventario',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)

    return False


def require_inventory_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_inventory_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')

        return wrapped

    return decorator


def get_granular_inventory_permissions(request):
    perms = {}
    for submodulo, acciones in INVENTORY_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_inventory_permission(request, submodulo, accion) for accion in acciones}
    return perms


def get_sales_ui_permissions(request):
    return {
        'clientes': user_has_sales_permission(request, 'clientes', 'ver'),
        'actividades': user_has_sales_permission(request, 'actividades', 'ver'),
        'cotizaciones': user_has_sales_permission(request, 'cotizaciones', 'ver'),
        'pedidos': user_has_sales_permission(request, 'pedidos', 'ver'),
        'salidas': user_has_sales_permission(request, 'salidas', 'ver'),
    }


def get_granular_sales_permissions(request):
    perms = {}
    for submodulo, acciones in SALES_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_sales_permission(request, submodulo, accion) for accion in acciones}
    return perms


def user_has_treasury_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    if not empresa.modulo_tesoreria:
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()
    if not asignacion:
        return False
    permiso_accion = PermisoRolAccion.objects.filter(
        rol=asignacion.rol,
        area='tesoreria',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)
    return False


def require_treasury_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_treasury_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)
            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)
            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')
        return wrapped
    return decorator


def get_granular_treasury_permissions(request):
    perms = {}
    for submodulo, acciones in TREASURY_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_treasury_permission(request, submodulo, accion) for accion in acciones}
    return perms


def user_has_hr_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

    # Verificar si el módulo está habilitado para la empresa
    if not empresa.modulo_recursos_humanos:
        return False

    if user.is_superuser:
        return True

    asignacion = AsignacionRolUsuario.objects.select_related('rol').filter(
        usuario=user,
        empresa=empresa
    ).first()

    if not asignacion:
        return False

    permiso_accion = PermisoRolAccion.objects.filter(
        rol=asignacion.rol,
        area='recursos_humanos',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)

    return False


def require_hr_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_hr_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            messages.error(request, 'No cuentas con permiso para esta acción.')
            return redirect('dashboard_inicio')

        return wrapped

    return decorator


def get_granular_hr_permissions(request):
    perms = {}
    for submodulo, acciones in HR_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_hr_permission(request, submodulo, accion) for accion in acciones}
    return perms
