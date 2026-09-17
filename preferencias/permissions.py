from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from panel.models import Empresa
from .models import AsignacionRolUsuario, PermisoRolModulo, PermisoRolAccion


INICIO_PERMISSION_MATRIX = {
    'dashboard': ['ver'],
}


SALES_PERMISSION_MATRIX = {
    'clientes': ['ver', 'crear', 'editar', 'agenda_contactos', 'crear_cotizacion'],
    'actividades': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir', 'completar', 'reprogramar', 'cancelar'],
    'cotizaciones': ['ver', 'crear', 'editar', 'eliminar', 'aprobar', 'imprimir'],
    'pedidos': ['ver', 'crear', 'editar', 'imprimir', 'validar_stock', 'revision', 'reservar', 'solicitar', 'generar_solicitud_global', 'registrar_pago', 'PagarParaPedido'],
    'salidas': ['ver', 'crear', 'imprimir', 'aprobar', 'surtir_orden', 'actualizar_entrega'],
    'punto_de_venta': ['ver', 'crear', 'listas', 'desactivar_iva', 'descuento', 'hacer_corte_pos'],
    'cortes_de_caja': ['ver', 'nueva_caja', 'cajas', 'ver_ventas', 'ver_articulos', 'imprimir_articulo', 'hacer_corte'],
}

COSTING_PERMISSION_MATRIX = {
    'costeos': ['ver', 'crear', 'editar', 'eliminar'],
}

PURCHASES_PERMISSION_MATRIX = {
    'proveedores': ['ver', 'crear', 'editar', 'eliminar'],
    'solicitudes': ['ver', 'crear', 'editar', 'imprimir', 'autorizar', 'cancelar'],
    'ordenes_compra': ['ver', 'crear', 'editar', 'imprimir', 'registrar_pago', 'consolidar', 'aprobar', 'cancelar', 'CargasXML'],
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
    'contratos': ['ver', 'crear', 'editar', 'eliminar', 'importador'],
    'contratistas': ['ver', 'crear', 'editar', 'eliminar', 'importador', 'reporte_contratos', 'reporte_informacion', 'reporte_trabajadores', 'reporte_carga_trabajadores'],
    'beneficiarios': ['ver', 'crear', 'editar', 'eliminar', 'documentacion', 'documentacion_subir', 'documentacion_eliminar', 'documentacion_descargar', 'documentacion_aprobar', 'documentacion_rechazar'],
    'proveedores_contratistas': ['ver', 'crear', 'editar', 'eliminar', 'documentacion', 'documentacion_aprobar', 'documentacion_rechazar', 'documentacion_descargar'],
    'sua': ['ver', 'importar', 'eliminar', 'alta_empleados', 'exportar_excel'],
    'nomina': ['ver', 'crear', 'editar', 'eliminar', 'importador', 'exportador', 'xml_sat'],
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
        'costeos': 'modulo_costeos',
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

    if submodulo in ['punto_de_venta', 'cortes_de_caja'] and not getattr(empresa, 'modulo_pos', True):
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
        'punto_de_venta': user_has_sales_permission(request, 'punto_de_venta', 'ver'),
        'cortes_de_caja': user_has_sales_permission(request, 'cortes_de_caja', 'ver'),
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


def user_has_inicio_permission(request, submodulo, accion):
    user = request.user
    if not user.is_authenticated:
        return False

    empresa = get_empresa_actual(request)
    if not empresa:
        return user.is_superuser

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
        area='inicio',
        submodulo=submodulo,
        accion=accion
    ).first()
    if permiso_accion is not None:
        return bool(permiso_accion.permitido)

    return False


def require_inicio_permission(submodulo, accion, json_response=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_inicio_permission(request, submodulo, accion):
                return view_func(request, *args, **kwargs)

            if json_response:
                return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)

            # Redirigir dinámicamente al primer módulo permitido
            target_url = obtener_url_redireccion_segun_permisos(request)
            if target_url:
                return redirect(target_url)

            messages.error(request, 'No cuentas con permiso para acceder al Inicio.')
            return redirect('login')

        return wrapped

    return decorator


def get_granular_inicio_permissions(request):
    perms = {}
    for submodulo, acciones in INICIO_PERMISSION_MATRIX.items():
        perms[submodulo] = {accion: user_has_inicio_permission(request, submodulo, accion) for accion in acciones}
    return perms


def obtener_url_redireccion_segun_permisos(request):
    # 1. Ventas
    if user_has_sales_permission(request, 'clientes', 'ver'):
        return '/clientes/'
    if user_has_sales_permission(request, 'actividades', 'ver'):
        return '/actividades/'
    if user_has_sales_permission(request, 'cotizaciones', 'ver'):
        return '/cotizaciones/'
    if user_has_sales_permission(request, 'pedidos', 'ver'):
        return '/pedidos/'
    if user_has_sales_permission(request, 'salidas', 'ver'):
        return '/ventas/'
    if user_has_sales_permission(request, 'punto_de_venta', 'ver'):
        return '/ventas/pos/'
    if user_has_sales_permission(request, 'cortes_de_caja', 'ver'):
        return '/ventas/cortes-caja/'

    # 2. Compras
    if user_has_purchase_permission(request, 'proveedores', 'ver'):
        return '/proveedores/'
    if user_has_purchase_permission(request, 'solicitudes', 'ver'):
        return '/solicitudes-compras/'
    if user_has_purchase_permission(request, 'ordenes_compra', 'ver'):
        return '/compras/'
    if user_has_purchase_permission(request, 'recepciones', 'ver'):
        return '/recepciones/'

    # 3. Tesorería
    if user_has_treasury_permission(request, 'ingresos', 'ver'):
        return '/tesoreria/ingresos/'
    if user_has_treasury_permission(request, 'egresos', 'ver'):
        return '/tesoreria/egresos/'
    if user_has_treasury_permission(request, 'cajas_bancos', 'ver'):
        return '/tesoreria/cajas-bancos/'

    # 4. Producción
    if user_has_production_permission(request, 'tablero_control', 'ver'):
        return '/produccion/'
    if user_has_production_permission(request, 'catalogos_test', 'ver'):
        return '/produccion/tests/'

    # 5. Inventario
    if user_has_inventory_permission(request, 'inventario', 'ver'):
        return '/inventario/'
    if user_has_inventory_permission(request, 'kardex', 'ver'):
        return '/inventario/kardex/'
    if user_has_inventory_permission(request, 'almacenes', 'ver'):
        return '/inventario/almacenes/'
    if user_has_inventory_permission(request, 'categorias', 'ver'):
        return '/inventario/categorias/'
    if user_has_inventory_permission(request, 'listas', 'ver'):
        return '/inventario/listas/'

    # 6. Recursos Humanos
    if user_has_hr_permission(request, 'empleados', 'ver'):
        return '/recursos-humanos/empleados/'
    if user_has_hr_permission(request, 'contratos', 'ver'):
        return '/recursos-humanos/contratos/'
    if user_has_hr_permission(request, 'contratistas', 'ver'):
        return '/recursos-humanos/contratistas/'
    if user_has_hr_permission(request, 'beneficiarios', 'ver'):
        return '/recursos-humanos/beneficiarios/'
    if user_has_hr_permission(request, 'sua', 'ver'):
        return '/recursos-humanos/sua/'
    if user_has_hr_permission(request, 'nomina', 'ver'):
        return '/recursos-humanos/nomina/'

    # 7. Costeos
    if user_has_module_permission(request, 'costeos', 'ver'):
        return '/costeos/'

    return None
