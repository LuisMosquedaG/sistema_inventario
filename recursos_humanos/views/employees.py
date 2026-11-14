from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q, Count
from decimal import Decimal

from ..models import Empleado, Contrato, Contratista, Beneficiario, TipoTurno
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual
from notificaciones.utils import crear_notificacion


def _sincronizar_usuario_empleado(empresa_actual, data, empleado=None):
    """Crea, actualiza o desvincula el User de portal de un Empleado según los datos del modal."""
    usuario_portal = (data.get('usuario_portal') or '').strip()
    password_portal = data.get('password_portal') or ''
    confirmar_password = data.get('confirmar_password') or ''

    if (password_portal or confirmar_password) and not usuario_portal:
        return None, 'Debes indicar un nombre de usuario para asignar contraseña.'

    if password_portal != confirmar_password:
        return None, 'Las contraseñas no coinciden.'

    user_obj = None
    if empleado and empleado.usuario_id:
        try:
            user_obj = empleado.usuario
        except User.DoesNotExist:
            user_obj = None

    if not usuario_portal:
        if user_obj:
            user_obj.delete()
        return None, None

    sufijo = f"@{empresa_actual.subdominio}"
    if usuario_portal.lower().endswith(sufijo.lower()):
        usuario_portal = usuario_portal[:-len(sufijo)].strip()
    if not usuario_portal:
        return None, 'El nombre de usuario no es válido.'

    username_completo = f"{usuario_portal}{sufijo}"
    dup_qs = User.objects.filter(username=username_completo)
    if user_obj:
        dup_qs = dup_qs.exclude(id=user_obj.id)
    if dup_qs.exists():
        return None, f'El usuario {username_completo} ya existe.'

    email = (data.get('correo_personal') or '').strip()
    first_name = (data.get('nombre') or '').strip()[:150]
    last_name = f"{(data.get('apellido_paterno') or '').strip()} {(data.get('apellido_materno') or '').strip()}".strip()[:150]

    if user_obj:
        user_obj.username = username_completo
        user_obj.email = email
        user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.is_staff = False
        user_obj.is_superuser = False
        if password_portal:
            user_obj.set_password(password_portal)
        user_obj.save()
        return user_obj, None

    if not password_portal:
        return None, 'La contraseña y su confirmación son obligatorias para crear el usuario.'

    user_obj = User.objects.create_user(
        username=username_completo,
        email=email,
        password=password_portal,
        first_name=first_name,
        last_name=last_name,
    )
    user_obj.is_staff = False
    user_obj.is_superuser = False
    user_obj.save(update_fields=['is_staff', 'is_superuser'])
    return user_obj, None

@login_required(login_url='/login/')
@require_hr_permission('empleados', 'ver')
def lista_empleados(request):
    empresa_actual = get_empresa_actual(request)
    empleados = Empleado.objects.filter(empresa=empresa_actual).select_related('sucursal', 'contratista', 'beneficiario').order_by('apellido_paterno')
    
    # Obtener parámetros de filtros
    q = request.GET.get('q', '')
    f_nss = request.GET.get('nss', '')
    f_empleado = request.GET.get('empleado', '')
    f_contratista = request.GET.get('contratista', '')
    f_beneficiario = request.GET.get('beneficiario', '')
    f_sucursal = request.GET.get('sucursal')
    if f_sucursal is None:
        f_sucursal = str(request.session.get('sucursal_id') or '')
    f_estado = request.GET.get('estado', '')

    # Aplicar Filtros
    if q:
        empleados = empleados.filter(
            Q(nombre__icontains=q) |
            Q(apellido_paterno__icontains=q) |
            Q(apellido_materno__icontains=q) |
            Q(nss__icontains=q) |
            Q(curp__icontains=q) |
            Q(rfc__icontains=q) |
            Q(puesto__icontains=q)
        )
    
    if f_nss:
        empleados = empleados.filter(nss__icontains=f_nss)
    
    if f_empleado:
        empleados = empleados.filter(
            Q(nombre__icontains=f_empleado) |
            Q(apellido_paterno__icontains=f_empleado) |
            Q(apellido_materno__icontains=f_empleado)
        )
    
    if f_contratista:
        empleados = empleados.filter(contratista_id=f_contratista)
    
    if f_beneficiario:
        empleados = empleados.filter(beneficiario_id=f_beneficiario)
            
    if f_sucursal:
        empleados = empleados.filter(sucursal_id=f_sucursal)

    if f_estado:
        if f_estado == 'baja':
            empleados = empleados.filter(estado__icontains='baja')
        else:
            empleados = empleados.filter(estado=f_estado)
            
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    contratistas = Contratista.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    beneficiarios = Beneficiario.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    contratos_disponibles = Contrato.objects.filter(empresa=empresa_actual).select_related('contratista', 'beneficiario')
    tipos_turno = TipoTurno.objects.filter(empresa=empresa_actual).annotate(num_empleados=Count('empleados')).order_by('nombre')
    vista = request.GET.get('vista', 'empleados')

    # PAGINACIÓN
    turnos_paginator = Paginator(tipos_turno, 20)
    turnos_page_number = request.GET.get('page') if vista == 'turnos' else 1
    turnos_page_obj = turnos_paginator.get_page(turnos_page_number)

    paginator = Paginator(empleados, 20)
    page_number = request.GET.get('page') if vista != 'turnos' else 1
    page_obj = paginator.get_page(page_number)

    return render(request, 'recursos_humanos/lista_empleados.html', {
        'page_obj': page_obj,
        'turnos_page_obj': turnos_page_obj,
        'sucursales': sucursales,
        'contratistas': contratistas,
        'beneficiarios': beneficiarios,
        'contratos_disponibles': contratos_disponibles,
        'tipos_turno': tipos_turno,
        'vista': vista,
        'empresa': empresa_actual,
        'filtros': {
            'q': q,
            'nss': f_nss,
            'empleado': f_empleado,
            'contratista': f_contratista,
            'beneficiario': f_beneficiario,
            'sucursal': f_sucursal,
            'estado': f_estado,
        }
    })

@login_required(login_url='/login/')
@require_hr_permission('empleados', 'ver', json_response=True)
def obtener_empleado_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        emp = Empleado.objects.get(id=id, empresa=empresa_actual)
        contrato_vinculado = emp.contratos_asignados.order_by('-fecha_inicio').first()

        data = {
            'id': emp.id,
            'contrato_id': contrato_vinculado.id if contrato_vinculado else '',
            'curp': emp.curp,
            'rfc': emp.rfc,
            'nss': emp.nss,
            'id_oficial': emp.id_oficial,
            'fecha_nacimiento': emp.fecha_nacimiento.isoformat() if emp.fecha_nacimiento else '',
            'genero': emp.genero,
            'nacionalidad': emp.nacionalidad,
            'nombre': emp.nombre,
            'apellido_paterno': emp.apellido_paterno,
            'apellido_materno': emp.apellido_materno,
            'estado_civil': emp.estado_civil,
            'correo_personal': emp.correo_personal,
            'telefono_movil': emp.telefono_movil,
            'telefono_fijo': emp.telefono_fijo,
            'calle': emp.calle,
            'num_ext': emp.num_ext,
            'num_int': emp.num_int,
            'colonia': emp.colonia,
            'cp': emp.cp,
            'ciudad': emp.ciudad,
            'estado_dir': emp.estado_dir,
            'num_empleado': emp.num_empleado,
            'estado': emp.estado,
            'fecha_ingreso': emp.fecha_ingreso.isoformat() if emp.fecha_ingreso else '',
            'fecha_antiguedad': emp.fecha_antiguedad.isoformat() if emp.fecha_antiguedad else '',
            'fecha_expiracion': emp.fecha_expiracion.isoformat() if emp.fecha_expiracion else '',
            'tipo_contrato': emp.tipo_contrato,
            'jornada': emp.jornada,
            'tipo_turno_id': emp.tipo_turno_id or '',
            'tipo_turno_nombre': str(emp.tipo_turno) if emp.tipo_turno else '',
            'puesto': emp.puesto,
            'departamento': emp.departamento,
            'supervisor': emp.supervisor,
            'clave_ubicacion': emp.clave_ubicacion or '',
            'notas': emp.notas or '',
            'riesgo_trabajo': emp.riesgo_trabajo,
            'tipo_trabajador': emp.tipo_trabajador,
            'salario_diario_ordinario': str(emp.salario_diario_ordinario),
            'sbc': str(emp.sbc),
            'sdi': str(emp.sdi),
            'forma_pago': emp.forma_pago,
            'clave_percepcion_sat': emp.clave_percepcion_sat,
            'tipo_salario': emp.tipo_salario,
            'registro_patronal': emp.registro_patronal,
            'num_infonavit': emp.num_infonavit,
            'num_fonacot': emp.num_fonacot,
            'fondo_ahorro': emp.fondo_ahorro,
            'porcentaje_fondo': str(emp.porcentaje_fondo),
            'banco_nombre': emp.banco_nombre,
            'clabe': emp.clabe,
            'num_cuenta': emp.num_cuenta,
            'tipo_cuenta': emp.tipo_cuenta,
            'sucursal': emp.sucursal_id or '',
            'contratista_id': emp.contratista_id or '',
            'beneficiario_id': emp.beneficiario_id or '',
            'usuario_portal': (
                emp.usuario.username[:-len(f"@{empresa_actual.subdominio}")]
                if emp.usuario and emp.usuario.username.lower().endswith(f"@{empresa_actual.subdominio}".lower())
                else (emp.usuario.username.split('@')[0] if emp.usuario else '')
            ),
        }
        return JsonResponse({'success': True, 'data': data})
    except Empleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Empleado no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar', json_response=True)
def editar_empleado_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        emp = Empleado.objects.get(id=id, empresa=empresa_actual)
        data = request.POST

        num_empleado = data.get('num_empleado')
        if num_empleado != emp.num_empleado and Empleado.objects.filter(empresa=empresa_actual, num_empleado=num_empleado).exists():
            return JsonResponse({'success': False, 'error': f'El número de empleado {num_empleado} ya existe.'})

        emp.curp = (data.get('curp') or '').upper()
        emp.rfc = (data.get('rfc') or '').upper()
        emp.nss = data.get('nss') or ''
        emp.id_oficial = data.get('id_oficial')
        emp.fecha_nacimiento = data.get('fecha_nacimiento') or None
        emp.genero = data.get('genero') or emp.genero or 'H'
        emp.nacionalidad = data.get('nacionalidad') or emp.nacionalidad or 'Mexicana'
        emp.nombre = data.get('nombre') or ''
        emp.apellido_paterno = data.get('apellido_paterno') or ''
        emp.apellido_materno = data.get('apellido_materno') or ''
        emp.estado_civil = data.get('estado_civil') or emp.estado_civil or 'soltero'
        emp.correo_personal = data.get('correo_personal') or ''
        emp.telefono_movil = data.get('telefono_movil') or ''
        emp.telefono_fijo = data.get('telefono_fijo')
        emp.calle = data.get('calle')
        emp.num_ext = data.get('num_ext')
        emp.num_int = data.get('num_int')
        emp.colonia = data.get('colonia')
        emp.cp = data.get('cp')
        emp.ciudad = data.get('ciudad')
        emp.estado_dir = data.get('estado_dir')
        emp.num_empleado = num_empleado
        emp.estado = data.get('estado') or emp.estado or 'activo'
        emp.fecha_ingreso = data.get('fecha_ingreso') or None
        emp.fecha_antiguedad = data.get('fecha_antiguedad') or None
        emp.tipo_contrato = data.get('tipo_contrato') or emp.tipo_contrato or '01'
        emp.jornada = data.get('jornada') or emp.jornada or 'diurna'
        tipo_turno_raw = data.get('tipo_turno_id')
        emp.tipo_turno_id = int(tipo_turno_raw) if tipo_turno_raw and str(tipo_turno_raw).isdigit() else None
        emp.puesto = data.get('puesto') or ''
        emp.departamento = data.get('departamento') or ''
        emp.supervisor = data.get('supervisor')
        emp.riesgo_trabajo = data.get('riesgo_trabajo') or emp.riesgo_trabajo or 'I'
        emp.tipo_trabajador = data.get('tipo_trabajador') or emp.tipo_trabajador or 'base'
        
        # Relaciones directas
        emp.contratista_id = data.get('contratista') or None
        emp.beneficiario_id = data.get('beneficiario') or None
        
        emp.salario_diario_ordinario = Decimal(data.get('salario_diario_ordinario') or '0')
        emp.sbc = Decimal(data.get('sbc') or '0')
        emp.sdi = Decimal(data.get('sdi') or '0')
        emp.forma_pago = data.get('forma_pago') or emp.forma_pago or 'quincenal'
        emp.clave_percepcion_sat = data.get('clave_percepcion_sat') or emp.clave_percepcion_sat or '001'
        emp.tipo_salario = data.get('tipo_salario') or emp.tipo_salario or 'fijo'
        emp.registro_patronal = data.get('registro_patronal')
        emp.num_infonavit = data.get('num_infonavit')
        emp.num_fonacot = data.get('num_fonacot')
        emp.fondo_ahorro = (data.get('fondo_ahorro') == 'on')
        emp.porcentaje_fondo = Decimal(data.get('porcentaje_fondo') or '0')
        emp.banco_nombre = data.get('banco_nombre')
        emp.clabe = data.get('clabe')
        emp.num_cuenta = data.get('num_cuenta')
        emp.tipo_cuenta = data.get('tipo_cuenta') or emp.tipo_cuenta or 'tarjeta'

        with transaction.atomic():
            user_obj, user_error = _sincronizar_usuario_empleado(empresa_actual, data, empleado=emp)
            if user_error:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'error': user_error})
            emp.usuario = user_obj
            emp.save()

        contrato_id = data.get('contrato_id')
        if contrato_id:
            try:
                contrato = Contrato.objects.get(id=contrato_id, empresa=empresa_actual)
                emp.contratos_asignados.clear()
                contrato.empleados.add(emp)
            except Contrato.DoesNotExist:
                pass
        else:
            emp.contratos_asignados.clear()

        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'editó al empleado {emp.nombre} {emp.apellido_paterno}',
            link='/recursos-humanos/empleados/',
            propietario=emp.creado_por or request.user
        )

        return JsonResponse({'success': True, 'message': 'Empleado actualizado correctamente.'})
    except Empleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Empleado no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'eliminar', json_response=True)
def eliminar_empleado_ajax(request, id):
    """Eliminar un empleado."""
    empresa_actual = get_empresa_actual(request)
    try:
        emp = Empleado.objects.get(id=id, empresa=empresa_actual)
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'eliminó al empleado {emp.nombre} {emp.apellido_paterno}',
            link='/recursos-humanos/empleados/',
            propietario=emp.creado_por or request.user
        )
        emp.delete()
        return JsonResponse({'success': True, 'message': 'Empleado eliminado correctamente.'})
    except Empleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Empleado no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'crear', json_response=True)
def crear_empleado_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)

    try:
        data = request.POST
        num_empleado = data.get('num_empleado')
        if Empleado.objects.filter(empresa=empresa_actual, num_empleado=num_empleado).exists():
            return JsonResponse({'success': False, 'error': f'El número de empleado {num_empleado} ya existe.'})

        sucursal_id = request.session.get('sucursal_id')

        with transaction.atomic():
            user_obj, user_error = _sincronizar_usuario_empleado(empresa_actual, data)
            if user_error:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'error': user_error})

            nuevo_empleado = Empleado(
                empresa=empresa_actual,
                sucursal_id=sucursal_id,
                usuario=user_obj,
                curp=(data.get('curp') or '').upper(),
                rfc=(data.get('rfc') or '').upper(),
                nss=data.get('nss') or '',
                id_oficial=data.get('id_oficial'),
                fecha_nacimiento=data.get('fecha_nacimiento') or None,
                genero=data.get('genero') or 'H',
                nacionalidad=data.get('nacionalidad') or 'Mexicana',
                nombre=data.get('nombre') or '',
                apellido_paterno=data.get('apellido_paterno') or '',
                apellido_materno=data.get('apellido_materno') or '',
                estado_civil=data.get('estado_civil') or 'soltero',
                correo_personal=data.get('correo_personal') or '',
                telefono_movil=data.get('telefono_movil') or '',
                telefono_fijo=data.get('telefono_fijo'),
                calle=data.get('calle'),
                num_ext=data.get('num_ext'),
                num_int=data.get('num_int'),
                colonia=data.get('colonia'),
                cp=data.get('cp'),
                ciudad=data.get('ciudad'),
                estado_dir=data.get('estado_dir'),
                num_empleado=num_empleado,
                estado=data.get('estado') or 'activo',
                fecha_ingreso=data.get('fecha_ingreso') or None,
                fecha_antiguedad=data.get('fecha_antiguedad') or data.get('fecha_ingreso') or None,
                fecha_expiracion=data.get('fecha_expiracion') or None,
                tipo_contrato=data.get('tipo_contrato') or '01',
                jornada=data.get('jornada') or 'diurna',
                tipo_turno_id=int(data.get('tipo_turno_id')) if data.get('tipo_turno_id') and str(data.get('tipo_turno_id')).isdigit() else None,
                puesto=data.get('puesto') or '',
                departamento=data.get('departamento') or '',
                supervisor=data.get('supervisor'),
                clave_ubicacion=data.get('clave_ubicacion'),
                notas=data.get('notas'),
                riesgo_trabajo=data.get('riesgo_trabajo') or 'I',
                tipo_trabajador=data.get('tipo_trabajador') or 'base',
                contratista_id=data.get('contratista') or None,
                beneficiario_id=data.get('beneficiario') or None,
                salario_diario_ordinario=Decimal(data.get('salario_diario_ordinario') or '0'),
                sbc=Decimal(data.get('sbc') or '0'),
                sdi=Decimal(data.get('sdi') or '0'),
                forma_pago=data.get('forma_pago') or 'quincenal',
                clave_percepcion_sat=data.get('clave_percepcion_sat') or '001',
                tipo_salario=data.get('tipo_salario') or 'fijo',
                registro_patronal=data.get('registro_patronal'),
                num_infonavit=data.get('num_infonavit'),
                num_fonacot=data.get('num_fonacot'),
                fondo_ahorro=(data.get('fondo_ahorro') == 'on'),
                porcentaje_fondo=Decimal(data.get('porcentaje_fondo') or '0'),
                caja_ahorro=(data.get('caja_ahorro') == 'on'),
                banco_nombre=data.get('banco_nombre'),
                clabe=data.get('clabe'),
                num_cuenta=data.get('num_cuenta'),
                tipo_cuenta=data.get('tipo_cuenta') or 'tarjeta',
                tarjeta_nomina=(data.get('tarjeta_nomina') == 'on'),
                num_tarjeta=data.get('num_tarjeta'),
                creado_por=request.user,
            )
            nuevo_empleado.save()

        contrato_id = data.get('contrato_id')
        if contrato_id:
            try:
                contrato = Contrato.objects.get(id=contrato_id, empresa=empresa_actual)
                contrato.empleados.add(nuevo_empleado)
            except Contrato.DoesNotExist:
                pass

        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'creó al empleado {nuevo_empleado.nombre} {nuevo_empleado.apellido_paterno}',
            link='/recursos-humanos/empleados/',
            propietario=request.user
        )

        return JsonResponse({'success': True, 'message': 'Empleado registrado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
