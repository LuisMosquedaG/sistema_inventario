from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q
from decimal import Decimal

from ..models import Empleado, Contrato, Contratista, Beneficiario
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual
from notificaciones.utils import crear_notificacion

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
    f_sucursal = request.GET.get('sucursal', '')
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

    # PAGINACIÓN
    paginator = Paginator(empleados, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'recursos_humanos/lista_empleados.html', {
        'page_obj': page_obj,
        'sucursales': sucursales,
        'contratistas': contratistas,
        'beneficiarios': beneficiarios,
        'contratos_disponibles': contratos_disponibles,
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

        emp.curp = data.get('curp', '').upper()
        emp.rfc = data.get('rfc', '').upper()
        emp.nss = data.get('nss', '')
        emp.id_oficial = data.get('id_oficial')
        emp.fecha_nacimiento = data.get('fecha_nacimiento') or None
        emp.genero = data.get('genero')
        emp.nacionalidad = data.get('nacionalidad', 'Mexicana')
        emp.nombre = data.get('nombre')
        emp.apellido_paterno = data.get('apellido_paterno')
        emp.apellido_materno = data.get('apellido_materno')
        emp.estado_civil = data.get('estado_civil')
        emp.correo_personal = data.get('correo_personal')
        emp.telefono_movil = data.get('telefono_movil')
        emp.telefono_fijo = data.get('telefono_fijo')
        emp.calle = data.get('calle')
        emp.num_ext = data.get('num_ext')
        emp.num_int = data.get('num_int')
        emp.colonia = data.get('colonia')
        emp.cp = data.get('cp')
        emp.ciudad = data.get('ciudad')
        emp.estado_dir = data.get('estado_dir')
        emp.num_empleado = num_empleado
        emp.estado = data.get('estado')
        emp.fecha_ingreso = data.get('fecha_ingreso') or None
        emp.fecha_antiguedad = data.get('fecha_antiguedad') or None
        emp.tipo_contrato = data.get('tipo_contrato')
        emp.jornada = data.get('jornada')
        emp.puesto = data.get('puesto')
        emp.departamento = data.get('departamento')
        emp.supervisor = data.get('supervisor')
        emp.riesgo_trabajo = data.get('riesgo_trabajo')
        emp.tipo_trabajador = data.get('tipo_trabajador')
        
        # Relaciones directas
        emp.contratista_id = data.get('contratista') or None
        emp.beneficiario_id = data.get('beneficiario') or None
        
        emp.salario_diario_ordinario = Decimal(data.get('salario_diario_ordinario', '0'))
        emp.sbc = Decimal(data.get('sbc', '0'))
        emp.sdi = Decimal(data.get('sdi', '0'))
        emp.forma_pago = data.get('forma_pago')
        emp.clave_percepcion_sat = data.get('clave_percepcion_sat', '001')
        emp.tipo_salario = data.get('tipo_salario')
        emp.registro_patronal = data.get('registro_patronal')
        emp.num_infonavit = data.get('num_infonavit')
        emp.num_fonacot = data.get('num_fonacot')
        emp.fondo_ahorro = (data.get('fondo_ahorro') == 'on')
        emp.porcentaje_fondo = Decimal(data.get('porcentaje_fondo', '0'))
        emp.banco_nombre = data.get('banco_nombre')
        emp.clabe = data.get('clabe')
        emp.num_cuenta = data.get('num_cuenta')
        emp.tipo_cuenta = data.get('tipo_cuenta')
        
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

        nuevo_empleado = Empleado(
            empresa=empresa_actual,
            sucursal_id=sucursal_id,
            curp=data.get('curp', '').upper(),
            rfc=data.get('rfc', '').upper(),
            nss=data.get('nss', ''),
            id_oficial=data.get('id_oficial'),
            fecha_nacimiento=data.get('fecha_nacimiento') or None,
            genero=data.get('genero'),
            nacionalidad=data.get('nacionalidad', 'Mexicana'),
            nombre=data.get('nombre'),
            apellido_paterno=data.get('apellido_paterno'),
            apellido_materno=data.get('apellido_materno'),
            estado_civil=data.get('estado_civil'),
            correo_personal=data.get('correo_personal'),
            telefono_movil=data.get('telefono_movil'),
            telefono_fijo=data.get('telefono_fijo'),
            calle=data.get('calle'),
            num_ext=data.get('num_ext'),
            num_int=data.get('num_int'),
            colonia=data.get('colonia'),
            cp=data.get('cp'),
            ciudad=data.get('ciudad'),
            estado_dir=data.get('estado_dir'),
            num_empleado=num_empleado,
            estado=data.get('estado'),
            fecha_ingreso=data.get('fecha_ingreso') or None,
            fecha_antiguedad=data.get('fecha_antiguedad') or data.get('fecha_ingreso') or None,
            fecha_expiracion=data.get('fecha_expiracion') or None,
            tipo_contrato=data.get('tipo_contrato'),
            jornada=data.get('jornada'),
            puesto=data.get('puesto'),
            departamento=data.get('departamento'),
            supervisor=data.get('supervisor'),
            clave_ubicacion=data.get('clave_ubicacion'),
            notas=data.get('notas'),
            riesgo_trabajo=data.get('riesgo_trabajo'),
            tipo_trabajador=data.get('tipo_trabajador'),
            contratista_id=data.get('contratista') or None,
            beneficiario_id=data.get('beneficiario') or None,
            salario_diario_ordinario=Decimal(data.get('salario_diario_ordinario', '0')),
            sbc=Decimal(data.get('sbc', '0')),
            sdi=Decimal(data.get('sdi', '0')),
            forma_pago=data.get('forma_pago'),
            clave_percepcion_sat=data.get('clave_percepcion_sat', '001'),
            tipo_salario=data.get('tipo_salario'),
            registro_patronal=data.get('registro_patronal'),
            num_infonavit=data.get('num_infonavit'),
            num_fonacot=data.get('num_fonacot'),
            fondo_ahorro=(data.get('fondo_ahorro') == 'on'),
            porcentaje_fondo=Decimal(data.get('porcentaje_fondo', '0')),
            caja_ahorro=(data.get('caja_ahorro') == 'on'),
            banco_nombre=data.get('banco_nombre'),
            clabe=data.get('clabe'),
            num_cuenta=data.get('num_cuenta'),
            tipo_cuenta=data.get('tipo_cuenta'),
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
