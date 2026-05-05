from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction # <--- ESTE FALTABA
from django.utils import timezone
from .models import Moneda, Rol, PermisoRolModulo, AsignacionRolUsuario, PermisoRolAccion
from .permissions import SALES_PERMISSION_MATRIX
from panel.models import Empresa
import csv
import io
import zipfile
from django.apps import apps
from django.db.models import Q

# Importaciones de modelos para exportación/limpieza
from ventas.models import OrdenVenta, DetalleOrdenVenta
from compras.models import OrdenCompra, DetalleCompra
from pedidos.models import Pedido, DetallePedido
from solicitudcompras.models import SolicitudCompra, DetalleSolicitudCompra
from produccion.models import OrdenProduccion, DetalleOrdenProduccion, Test, ItemTest, ResultadoTestOP
from actividades.models import Actividad
from almacenes.models import Almacen, Inventario, Kardex
from core.models import Producto, Categoria as CategoriaCore, Transaccion as TransaccionCore
from categorias.models import Categoria, Subcategoria
from clientes.models import Cliente, ContactoCliente
from proveedores.models import Proveedor
from recepciones.models import Recepcion, DetalleRecepcion, DetalleRecepcionExtra
from cotizaciones.models import Cotizacion, DetalleCotizacion

# --- HELPER MULTI-TENANCY ---
def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

# --- VISTA PRINCIPAL (MODIFICADA) ---
@login_required(login_url='/login/')
def dashboard_preferencias(request):
    empresa_actual = get_empresa_actual(request)
    
    # El usuario Master (madmin) puede entrar aquí pero sin empresa asociada
    is_master = (request.user.username == 'madmin@crossoversuite')
    
    if not empresa_actual and not is_master:
        return render(request, 'error_sin_empresa.html', status=403)

    seccion_activa = request.GET.get('section', 'usuarios')
    
    contexto = {
        'seccion': seccion_activa,
        'empresa': empresa_actual,
        'sales_permission_matrix': SALES_PERMISSION_MATRIX,
    }

    if seccion_activa == 'usuarios':
        # --- REGLA 1 y 3: Filtrar por empresa, ocultar madmin y sadmins ---
        qs = User.objects.exclude(username='madmin@crossoversuite')
        
        # Ocultar todos los sadmin@...
        qs = qs.exclude(username__startswith='sadmin@')
        
        if not is_master:
            # Solo ver usuarios que tengan el prefijo de la empresa (ej: @demo)
            qs = qs.filter(username__contains=f"@{empresa_actual.subdominio}")
            
        contexto['usuarios'] = qs.order_by('-id')
        contexto['roles'] = Rol.objects.filter(empresa=empresa_actual, activo=True).order_by('nombre')
    
    elif seccion_activa == 'roles':
        if not request.user.is_staff and not is_master:
            return render(request, 'error_sin_empresa.html', status=403)

        roles = Rol.objects.filter(empresa=empresa_actual).order_by('nombre')
        roles_info = []
        for rol in roles:
            permiso_ventas = PermisoRolModulo.objects.filter(rol=rol, modulo='ventas').first()
            roles_info.append({
                'rol': rol,
                'permiso_ventas': permiso_ventas,
                'total_usuarios': AsignacionRolUsuario.objects.filter(rol=rol).count(),
                'total_permisos_accion': PermisoRolAccion.objects.filter(rol=rol, area='ventas', permitido=True).count()
            })
        contexto['roles_info'] = roles_info

    elif seccion_activa == 'monedas':
        contexto['monedas'] = Moneda.objects.filter(empresa=empresa_actual)
    
    elif seccion_activa == 'datos':
        # Solo admin/sadmin pueden entrar aquí
        if not request.user.is_staff:
            return render(request, 'error_sin_empresa.html', status=403)
            
    return render(request, 'dashboard_preferencias.html', contexto)

# --- VISTA: EXPORTAR DATOS ZIP/CSV ---
@login_required
def exportar_datos_zip(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual or not request.user.is_staff:
        return HttpResponse("Acceso denegado", status=403)

    # Definir modelos a exportar (incluyendo tablas de detalle)
    modelos = [
        (Producto, "Productos"),
        (Cliente, "Clientes"),
        (ContactoCliente, "ContactosClientes"),
        (Proveedor, "Proveedores"),
        (Almacen, "Almacenes"),
        (Categoria, "Categorias"),
        (Subcategoria, "Subcategorias"),
        (Moneda, "Monedas"),
        (Pedido, "Pedidos"),
        (DetallePedido, "DetallesPedidos"),
        (OrdenVenta, "OrdenesVenta"),
        (DetalleOrdenVenta, "DetallesOrdenesVenta"),
        (OrdenCompra, "OrdenesCompra"),
        (DetalleCompra, "DetallesOrdenesCompra"),
        (SolicitudCompra, "SolicitudesCompra"),
        (DetalleSolicitudCompra, "DetallesSolicitudesCompra"),
        (Cotizacion, "Cotizaciones"),
        (DetalleCotizacion, "DetallesCotizaciones"),
        (Recepcion, "Recepciones"),
        (DetalleRecepcion, "DetallesRecepciones"),
        (DetalleRecepcionExtra, "DetallesRecepcionesExtra"),
        (OrdenProduccion, "OrdenesProduccion"),
        (DetalleOrdenProduccion, "DetallesOrdenesProduccion"),
        (Test, "TestsCalidad"),
        (ItemTest, "ItemsTestsCalidad"),
        (ResultadoTestOP, "ResultadosTestsOP"),
        (Actividad, "Actividades"),
        (Kardex, "Kardex"),
        (Inventario, "InventarioActual")
    ]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zip_file:
        for model, name in modelos:
            # Crear CSV en memoria
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            
            # Obtener campos del modelo
            fields = [field.name for field in model._meta.fields]
            writer.writerow(fields)
            
            # Filtrar por empresa
            try:
                if 'empresa' in fields:
                    queryset = model.objects.filter(empresa=empresa_actual)
                elif 'pedido' in fields:
                    queryset = model.objects.filter(pedido__empresa=empresa_actual)
                elif 'orden_venta' in fields:
                    queryset = model.objects.filter(orden_venta__empresa=empresa_actual)
                elif 'orden_compra' in fields:
                    queryset = model.objects.filter(orden_compra__empresa=empresa_actual)
                elif 'solicitud' in fields:
                    queryset = model.objects.filter(solicitud__empresa=empresa_actual)
                elif 'recepcion' in fields:
                    queryset = model.objects.filter(recepcion__empresa=empresa_actual)
                elif 'orden_produccion' in fields:
                    queryset = model.objects.filter(orden_produccion__empresa=empresa_actual)
                elif 'cliente' in fields:
                    queryset = model.objects.filter(cliente__empresa=empresa_actual)
                elif 'test' in fields:
                    queryset = model.objects.filter(test__empresa=empresa_actual)
                elif 'detalle_recepcion' in fields:
                    queryset = model.objects.filter(detalle_recepcion__recepcion__empresa=empresa_actual)
                elif 'cotizacion' in fields:
                    queryset = model.objects.filter(cotizacion__empresa=empresa_actual)
                else:
                    continue
            except:
                continue
            
            for obj in queryset:
                row = []
                for field in fields:
                    val = getattr(obj, field)
                    if hasattr(val, 'id'):
                        val = val.id
                    row.append(str(val))
                writer.writerow(row)
            
            zip_file.writestr(f"{name}.csv", csv_buffer.getvalue())

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    filename = f"Backup_{empresa_actual.subdominio}_{timezone.now().strftime('%Y%m%d')}.zip"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# --- VISTA: REINICIAR TRANSACCIONES (AJAX) ---
@login_required
@transaction.atomic
def reiniciar_transacciones_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual or not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'})

    if request.method == 'POST':
        try:
            # Borrar transacciones en orden de dependencia (Hijos primero para evitar PROTECT)
            Recepcion.objects.filter(empresa=empresa_actual).delete()
            OrdenCompra.objects.filter(empresa=empresa_actual).delete()
            SolicitudCompra.objects.filter(empresa=empresa_actual).delete()
            OrdenVenta.objects.filter(empresa=empresa_actual).delete()
            OrdenProduccion.objects.filter(empresa=empresa_actual).delete()
            Pedido.objects.filter(empresa=empresa_actual).delete()
            Cotizacion.objects.filter(empresa=empresa_actual).delete()
            TransaccionCore.objects.filter(empresa=empresa_actual).delete()
            Actividad.objects.filter(empresa=empresa_actual).delete()
            Kardex.objects.filter(empresa=empresa_actual).delete()
            
            # Resetear stock en inventario
            Inventario.objects.filter(empresa=empresa_actual).update(cantidad=0, reservado=0)
            
            return JsonResponse({'success': True, 'message': 'Transacciones reiniciadas correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- VISTA: REINICIAR CATÁLOGOS (AJAX) ---
@login_required
@transaction.atomic
def reiniciar_catalogos_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual or not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'})

    if request.method == 'POST':
        try:
            # Primero transacciones por integridad (aunque cascade debería manejarlo)
            reiniciar_transacciones_ajax(request)
            
            # Borrar catálogos
            Producto.objects.filter(empresa=empresa_actual).delete()
            Cliente.objects.filter(empresa=empresa_actual).delete()
            Proveedor.objects.filter(empresa=empresa_actual).delete()
            Almacen.objects.filter(empresa=empresa_actual).delete()
            Categoria.objects.filter(empresa=empresa_actual).delete()
            Subcategoria.objects.filter(empresa=empresa_actual).delete()
            Moneda.objects.filter(empresa=empresa_actual).exclude(siglas='MXN').delete() # Mantener MXN por seguridad
            
            return JsonResponse({'success': True, 'message': 'Catálogos reiniciados correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- API: CREAR MONEDA ---
@login_required
def crear_moneda_ajax(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            nombre = request.POST.get('nombre')
            siglas = request.POST.get('siglas')
            simbolo = request.POST.get('simbolo')
            factor = request.POST.get('factor', 1.0)

            Moneda.objects.create(
                nombre=nombre,
                siglas=siglas,
                simbolo=simbolo,
                factor=factor,
                responsable=request.user,
                empresa=empresa_actual
            )
            return JsonResponse({'success': True, 'message': 'Moneda registrada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_detalle_moneda(request, moneda_id):
    empresa_actual = get_empresa_actual(request)
    moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
    return JsonResponse({
        'success': True,
        'id': moneda.id,
        'nombre': moneda.nombre,
        'siglas': moneda.siglas,
        'simbolo': moneda.simbolo,
        'factor': str(moneda.factor)
    })

@login_required
def actualizar_moneda_ajax(request, moneda_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
            moneda.nombre = request.POST.get('nombre')
            moneda.siglas = request.POST.get('siglas')
            moneda.simbolo = request.POST.get('simbolo')
            moneda.factor = request.POST.get('factor')
            moneda.save()
            return JsonResponse({'success': True, 'message': 'Moneda actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- VISTA: CREAR USUARIO (REGLA 2: PREFIJO AUTOMÁTICO) ---
@login_required(login_url='/login/')
def crear_usuario_ajax(request):
    if request.method == 'POST':
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'success': False, 'error': 'No se detectó empresa para asignar el prefijo.'})

        username_corto = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password1')
        rol = request.POST.get('rol')
        rol_acceso_id = request.POST.get('rol_acceso_id')

        if not username_corto or not password:
            return JsonResponse({'success': False, 'error': 'El usuario y la contraseña son obligatorios.'})

        # --- REGLA 2: ASIGNAR PREFIJO AUTOMÁTICO ---
        # Si el usuario puso "juan", se guarda como "juan@demo"
        username_completo = f"{username_corto}@{empresa_actual.subdominio}"

        if User.objects.filter(username=username_completo).exists():
            return JsonResponse({'success': False, 'error': f'El usuario {username_completo} ya existe.'})

        try:
            user = User.objects.create_user(username=username_completo, email=email, password=password)
            
            if rol == 'admin':
                user.is_staff = True
                user.is_superuser = True
            else:
                # Los usuarios con rol 'usuario' no son is_staff para restringir su visibilidad en notificaciones
                user.is_staff = False
                user.is_superuser = False 

            user.save()

            if rol_acceso_id:
                rol_acceso = Rol.objects.filter(id=rol_acceso_id, empresa=empresa_actual, activo=True).first()
                if rol_acceso:
                    AsignacionRolUsuario.objects.update_or_create(
                        usuario=user,
                        empresa=empresa_actual,
                        defaults={'rol': rol_acceso}
                    )
            return JsonResponse({'success': True, 'message': f'Usuario {username_completo} creado correctamente.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_detalle_usuario(request, user_id):
    empresa_actual = get_empresa_actual(request)
    user = get_object_or_404(User, id=user_id)
    
    if f"@{empresa_actual.subdominio}" not in user.username:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)

    asignacion_rol = AsignacionRolUsuario.objects.filter(usuario=user, empresa=empresa_actual).first()

    return JsonResponse({
        'success': True,
        'id': user.id,
        'username_corto': user.username.split('@')[0],
        'email': user.email,
        'rol': 'admin' if user.is_superuser else 'usuario',
        'rol_acceso_id': asignacion_rol.rol_id if asignacion_rol else ''
    })

@login_required
@transaction.atomic
def actualizar_usuario_ajax(request, user_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            user = get_object_or_404(User, id=user_id)
            
            if f"@{empresa_actual.subdominio}" not in user.username:
                return JsonResponse({'success': False, 'error': 'Acceso denegado'})

            user.email = request.POST.get('email')
            rol = request.POST.get('rol')
            rol_acceso_id = request.POST.get('rol_acceso_id')
            if rol == 'admin':
                user.is_staff = True; user.is_superuser = True
            else:
                user.is_staff = False; user.is_superuser = False
            
            passw = request.POST.get('password1')
            if passw: user.set_password(passw)
            
            user.save()

            if rol_acceso_id:
                rol_acceso = Rol.objects.filter(id=rol_acceso_id, empresa=empresa_actual, activo=True).first()
                if rol_acceso:
                    AsignacionRolUsuario.objects.update_or_create(
                        usuario=user,
                        empresa=empresa_actual,
                        defaults={'rol': rol_acceso}
                    )
            else:
                AsignacionRolUsuario.objects.filter(usuario=user, empresa=empresa_actual).delete()
            return JsonResponse({'success': True, 'message': 'Usuario actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
def crear_rol_ajax(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual or not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'}, status=403)

    nombre = (request.POST.get('nombre') or '').strip()
    descripcion = (request.POST.get('descripcion') or '').strip()
    if not nombre:
        return JsonResponse({'success': False, 'error': 'El nombre del rol es obligatorio.'})

    try:
        rol = Rol.objects.create(nombre=nombre, descripcion=descripcion, empresa=empresa_actual, activo=True)
        PermisoRolModulo.objects.create(
            rol=rol,
            modulo='ventas',
            puede_ver=(request.POST.get('ventas_ver') == 'on'),
            puede_crear=(request.POST.get('ventas_crear') == 'on'),
            puede_editar=(request.POST.get('ventas_editar') == 'on'),
            puede_eliminar=(request.POST.get('ventas_eliminar') == 'on'),
            puede_aprobar=(request.POST.get('ventas_aprobar') == 'on'),
            puede_imprimir=(request.POST.get('ventas_imprimir') == 'on')
        )

        for submodulo, acciones in SALES_PERMISSION_MATRIX.items():
            for accion in acciones:
                key = f"perm_ventas__{submodulo}__{accion}"
                PermisoRolAccion.objects.create(
                    rol=rol,
                    area='ventas',
                    submodulo=submodulo,
                    accion=accion,
                    permitido=(request.POST.get(key) == 'on')
                )
        return JsonResponse({'success': True, 'message': 'Rol creado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_detalle_rol(request, rol_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no detectada'}, status=403)

    rol = get_object_or_404(Rol, id=rol_id, empresa=empresa_actual)
    permiso_ventas = PermisoRolModulo.objects.filter(rol=rol, modulo='ventas').first()
    permisos_accion = {}
    permisos_qs = PermisoRolAccion.objects.filter(rol=rol, area='ventas')
    for p in permisos_qs:
        permisos_accion.setdefault(p.submodulo, {})[p.accion] = p.permitido

    return JsonResponse({
        'success': True,
        'id': rol.id,
        'nombre': rol.nombre,
        'descripcion': rol.descripcion or '',
        'activo': rol.activo,
        'ventas': {
            'ver': permiso_ventas.puede_ver if permiso_ventas else False,
            'crear': permiso_ventas.puede_crear if permiso_ventas else False,
            'editar': permiso_ventas.puede_editar if permiso_ventas else False,
            'eliminar': permiso_ventas.puede_eliminar if permiso_ventas else False,
            'aprobar': permiso_ventas.puede_aprobar if permiso_ventas else False,
            'imprimir': permiso_ventas.puede_imprimir if permiso_ventas else False,
        },
        'permisos_accion': permisos_accion
    })


@login_required
def actualizar_rol_ajax(request, rol_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual or not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'}, status=403)

    rol = get_object_or_404(Rol, id=rol_id, empresa=empresa_actual)
    try:
        rol.nombre = (request.POST.get('nombre') or '').strip()
        rol.descripcion = (request.POST.get('descripcion') or '').strip()
        rol.activo = (request.POST.get('activo') == 'on')
        rol.save()

        permiso_ventas, _ = PermisoRolModulo.objects.get_or_create(rol=rol, modulo='ventas')
        permiso_ventas.puede_ver = (request.POST.get('ventas_ver') == 'on')
        permiso_ventas.puede_crear = (request.POST.get('ventas_crear') == 'on')
        permiso_ventas.puede_editar = (request.POST.get('ventas_editar') == 'on')
        permiso_ventas.puede_eliminar = (request.POST.get('ventas_eliminar') == 'on')
        permiso_ventas.puede_aprobar = (request.POST.get('ventas_aprobar') == 'on')
        permiso_ventas.puede_imprimir = (request.POST.get('ventas_imprimir') == 'on')
        permiso_ventas.save()

        for submodulo, acciones in SALES_PERMISSION_MATRIX.items():
            for accion in acciones:
                key = f"perm_ventas__{submodulo}__{accion}"
                permiso_accion, _ = PermisoRolAccion.objects.get_or_create(
                    rol=rol,
                    area='ventas',
                    submodulo=submodulo,
                    accion=accion
                )
                permiso_accion.permitido = (request.POST.get(key) == 'on')
                permiso_accion.save()

        return JsonResponse({'success': True, 'message': 'Rol actualizado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})