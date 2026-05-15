from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
import re
import csv
from django.http import JsonResponse, HttpResponse
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from panel.models import Empresa
from .models import Empleado, Contrato, Contratista, Beneficiario, ImportacionSUA, TrabajadorSUA
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission

def limpiar_basura_header(texto):
    """Elimina textos innecesarios del encabezado del SUA como convenios y versiones."""
    if not texto: return ""
    patrones = [
        r'Convenio\s+de\s+Re?mbolso:.*',
        r'Aportación\s+Patronal:.*',
        r'V\s?\d\.\d\.\d.*',
        r'Página:.*',
        r'Hoja:.*'
    ]
    for p in patrones:
        texto = re.sub(p, '', texto, flags=re.I)
    return texto.strip()

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

def get_sucursal_actual_id(request):
    """Auxiliar para obtener la sucursal de la sesión o el filtro."""
    suc_id = request.POST.get('sucursal') or request.GET.get('sucursal') or request.session.get('sucursal_id')
    return suc_id

@login_required(login_url='/login/')
@require_hr_permission('empleados', 'ver')
def lista_empleados(request):
    empresa_actual = get_empresa_actual(request)
    empleados = Empleado.objects.filter(empresa=empresa_actual).select_related('sucursal').order_by('apellido_paterno')
    
    q = request.GET.get('q', '')
    depto = request.GET.get('departamento', '')
    estado = request.GET.get('estado', '')
    sucursal_id = request.GET.get('sucursal', '')

    if q:
        empleados = empleados.filter(
            Q(nombre__icontains=q) |
            Q(apellido_paterno__icontains=q) |
            Q(apellido_materno__icontains=q) |
            Q(num_empleado__icontains=q) |
            Q(puesto__icontains=q)
        )
    
    if depto:
        empleados = empleados.filter(departamento=depto)
    
    if estado:
        if estado == 'baja':
            empleados = empleados.filter(estado__icontains='baja')
        else:
            empleados = empleados.filter(estado=estado)
            
    if sucursal_id:
        empleados = empleados.filter(sucursal_id=sucursal_id)
            
    departamentos = Empleado.objects.filter(empresa=empresa_actual).values_list('departamento', flat=True).distinct()

    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    contratos_disponibles = Contrato.objects.filter(empresa=empresa_actual).select_related('contratista', 'beneficiario')

    return render(request, 'recursos_humanos/lista_empleados.html', {
        'empleados': empleados,
        'departamentos': departamentos,
        'sucursales': sucursales,
        'contratos_disponibles': contratos_disponibles,
        'empresa': empresa_actual,
        'filtros': {
            'q': q,
            'departamento': depto,
            'estado': estado,
            'sucursal': sucursal_id
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

        return JsonResponse({'success': True, 'message': 'Empleado actualizado correctamente.'})
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
            riesgo_trabajo=data.get('riesgo_trabajo'),
            tipo_trabajador=data.get('tipo_trabajador'),
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
        )
        nuevo_empleado.save()

        contrato_id = data.get('contrato_id')
        if contrato_id:
            try:
                contrato = Contrato.objects.get(id=contrato_id, empresa=empresa_actual)
                contrato.empleados.add(nuevo_empleado)
            except Contrato.DoesNotExist:
                pass

        return JsonResponse({'success': True, 'message': 'Empleado registrado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('contratos', 'ver')
def lista_contratos(request):
    empresa_actual = get_empresa_actual(request)
    contratos = Contrato.objects.filter(empresa=empresa_actual).prefetch_related('empleados', 'empleados__sucursal').order_by('-fecha_inicio')
    
    q = request.GET.get('q', '')
    empleado_id = request.GET.get('empleado_id', '')
    estado = request.GET.get('estado', '')
    sucursal_id = request.GET.get('sucursal', '')

    if q:
        contratos = contratos.filter(
            Q(folio__icontains=q) |
            Q(beneficiario__nombre_razon_social__icontains=q) |
            Q(contratista__nombre_razon_social__icontains=q) |
            Q(empleados__nombre__icontains=q) |
            Q(empleados__apellido_paterno__icontains=q) |
            Q(notes__icontains=q)
        ).distinct()
    
    if empleado_id:
        contratos = contratos.filter(empleados__id=empleado_id)
    
    if estado:
        contratos = contratos.filter(estado=estado)
            
    if sucursal_id:
        contratos = contratos.filter(sucursal_id=sucursal_id)

    empleados = Empleado.objects.filter(empresa=empresa_actual).order_by('apellido_paterno')
    contratistas = Contratista.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    beneficiarios = Beneficiario.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    return render(request, 'recursos_humanos/lista_contratos.html', {
        'contratos': contratos,
        'empleados': empleados,
        'contratistas': contratistas,
        'beneficiarios': beneficiarios,
        'sucursales': sucursales,
        'empresa': empresa_actual,
        'filtros': {
            'q': q,
            'empleado_id': empleado_id,
            'estado': estado,
            'sucursal': sucursal_id
        }
    })

@login_required(login_url='/login/')
@require_hr_permission('contratos', 'ver', json_response=True)
def obtener_contrato_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        con = Contrato.objects.get(id=id, empresa=empresa_actual)
        data = {
            'id': con.id,
            'empleados_ids': list(con.empleados.values_list('id', flat=True)),
            'contratista': con.contratista_id,
            'beneficiario': con.beneficiario_id,
            'folio': con.folio,
            'tipo_contrato': con.tipo_contrato,
            'objeto_contrato': con.objeto_contrato,
            'monto_contrato': str(con.monto_contrato),
            'fecha_inicio': con.fecha_inicio.isoformat() if con.fecha_inicio else '',
            'fecha_fin': con.fecha_fin.isoformat() if con.fecha_fin else '',
            'vigencia_contrato': con.vigencia_contrato.isoformat() if con.vigencia_contrato else '',
            'num_estimado_trabajadores': con.num_estimado_trabajadores,
            'estado': con.estado,
            'notas': con.notas,
        }
        return JsonResponse({'success': True, 'data': data})
    except Contrato.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contrato no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratos', 'crear', json_response=True)
def crear_contrato_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)

    try:
        data = request.POST
        sucursal_id = request.session.get('sucursal_id')
        with transaction.atomic():
            nuevo_contrato = Contrato(
                empresa=empresa_actual,
                sucursal_id=sucursal_id,
                contratista_id=data.get('contratista'),
                beneficiario_id=data.get('beneficiario'),
                folio=data.get('folio'),
                tipo_contrato=data.get('tipo_contrato'),
                objeto_contrato=data.get('objeto_contrato'),
                monto_contrato=Decimal(data.get('monto_contrato', '0')),
                fecha_inicio=data.get('fecha_inicio'),
                fecha_fin=data.get('fecha_fin') or None,
                vigencia_contrato=data.get('vigencia_contrato') or None,
                num_estimado_trabajadores=int(data.get('num_estimado_trabajadores', 0)),
                estado=data.get('estado', 'vigente'),
                notas=data.get('notas', '')
            )
            nuevo_contrato.save()
            
            empleados_ids = request.POST.getlist('empleados[]') or request.POST.getlist('empleados')
            if empleados_ids:
                nuevo_contrato.empleados.set(empleados_ids)
                
            return JsonResponse({'success': True, 'message': 'Contrato registrado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratos', 'editar', json_response=True)
def editar_contrato_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        con = Contrato.objects.get(id=id, empresa=empresa_actual)
        data = request.POST

        with transaction.atomic():
            con.contratista_id = data.get('contratista')
            con.beneficiario_id = data.get('beneficiario')
            con.folio = data.get('folio')
            con.tipo_contrato = data.get('tipo_contrato')
            con.objeto_contrato = data.get('objeto_contrato')
            con.monto_contrato = Decimal(data.get('monto_contrato', '0'))
            con.fecha_inicio = data.get('fecha_inicio')
            con.fecha_fin = data.get('fecha_fin') or None
            con.vigencia_contrato = data.get('vigencia_contrato') or None
            con.num_estimado_trabajadores = int(data.get('num_estimado_trabajadores', 0))
            con.estado = data.get('estado')
            con.notas = data.get('notas', '')
            con.save()
            
            empleados_ids = request.POST.getlist('empleados[]') or request.POST.getlist('empleados')
            con.empleados.set(empleados_ids)
            
            return JsonResponse({'success': True, 'message': 'Contrato actualizado correctamente.'})
    except Contrato.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contrato no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'ver')
def lista_contratistas(request):
    empresa_actual = get_empresa_actual(request)
    contratistas = Contratista.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    q = request.GET.get('q', '')
    sucursal_id = request.GET.get('sucursal', '')
    
    if q:
        contratistas = contratistas.filter(
            Q(nombre_razon_social__icontains=q) |
            Q(rfc__icontains=q) |
            Q(representante_legal__icontains=q) |
            Q(correo__icontains=q)
        )
    if sucursal_id:
        contratistas = contratistas.filter(sucursal_id=sucursal_id)

    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    return render(request, 'recursos_humanos/lista_contratistas.html', {
        'contratistas': contratistas,
        'sucursales': sucursales,
        'empresa': empresa_actual,
        'filtros': {'q': q, 'sucursal': sucursal_id}
    })

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'ver', json_response=True)
def obtener_contratista_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        cont = Contratista.objects.get(id=id, empresa=empresa_actual)
        data = {
            'id': cont.id, 'rfc': cont.rfc, 'nombre_razon_social': cont.nombre_razon_social,
            'correo': cont.correo, 'telefono': cont.telefono, 'registro_patronal': cont.registro_patronal,
            'calle': cont.calle, 'num_ext': cont.num_ext, 'num_int': cont.num_int,
            'entre_calle': cont.entre_calle, 'y_calle': cont.y_calle, 'colonia': cont.colonia,
            'cp': cont.cp, 'municipio_alcaldia': cont.municipio_alcaldia,
            'entidad_federativa': cont.entidad_federativa, 'representante_legal': cont.representante_legal,
            'administrador_unico': cont.administrador_unico, 'num_escritura': cont.num_escritura,
            'nombre_notario_publico': cont.nombre_notario_publico, 'num_notario_publico': cont.num_notario_publico,
            'fecha_escritura_publica': cont.fecha_escritura_publica.isoformat() if cont.fecha_escritura_publica else '',
            'folio_mercantil': cont.folio_mercantil, 'numero_stps': cont.numero_stps,
        }
        return JsonResponse({'success': True, 'data': data})
    except Contratista.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratistas', 'crear', json_response=True)
def crear_contratista_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual: return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)
    try:
        data = request.POST
        sucursal_id = request.session.get('sucursal_id')
        nuevo = Contratista(
            empresa=empresa_actual, sucursal_id=sucursal_id, rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'), correo=data.get('correo'),
            telefono=data.get('telefono'), registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'), num_ext=data.get('num_ext'), num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'), y_calle=data.get('y_calle'), colonia=data.get('colonia'),
            cp=data.get('cp'), municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'), representante_legal=data.get('representante_legal'),
            administrador_unico=data.get('administrador_unico'), num_escritura=data.get('num_escritura'),
            nombre_notario_publico=data.get('nombre_notario_publico'), num_notario_publico=data.get('num_notario_publico'),
            fecha_escritura_publica=data.get('fecha_escritura_publica') or None, folio_mercantil=data.get('folio_mercantil'),
            numero_stps=data.get('numero_stps'),
        )
        nuevo.save()
        return JsonResponse({'success': True, 'message': 'Contratista registrado correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratistas', 'editar', json_response=True)
def editar_contratista_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        cont = Contratista.objects.get(id=id, empresa=empresa_actual)
        data = request.POST
        cont.rfc = data.get('rfc', '').upper()
        cont.nombre_razon_social = data.get('nombre_razon_social')
        cont.correo = data.get('correo'); cont.telefono = data.get('telefono')
        cont.registro_patronal = data.get('registro_patronal'); cont.calle = data.get('calle')
        cont.num_ext = data.get('num_ext'); cont.num_int = data.get('num_int')
        cont.entre_calle = data.get('entre_calle'); cont.y_calle = data.get('y_calle')
        cont.colonia = data.get('colonia'); cont.cp = data.get('cp')
        cont.municipio_alcaldia = data.get('municipio_alcaldia'); cont.entidad_federativa = data.get('entidad_federativa')
        cont.representante_legal = data.get('representante_legal'); cont.administrador_unico = data.get('administrador_unico')
        cont.num_escritura = data.get('num_escritura'); cont.nombre_notario_publico = data.get('nombre_notario_publico')
        cont.num_notario_publico = data.get('num_notario_publico'); cont.fecha_escritura_publica = data.get('fecha_escritura_publica') or None
        cont.folio_mercantil = data.get('folio_mercantil'); cont.numero_stps = data.get('numero_stps')
        cont.save()
        return JsonResponse({'success': True, 'message': 'Contratista actualizado correctamente.'})
    except Contratista.DoesNotExist: return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver')
def lista_beneficiarios(request):
    empresa_actual = get_empresa_actual(request)
    beneficiarios = Beneficiario.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    q = request.GET.get('q', ''); sucursal_id = request.GET.get('sucursal', '')
    if q:
        beneficiarios = beneficiarios.filter(Q(nombre_razon_social__icontains=q) | Q(rfc__icontains=q) | Q(correo__icontains=q))
    if sucursal_id: beneficiarios = beneficiarios.filter(sucursal_id=sucursal_id)
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    return render(request, 'recursos_humanos/lista_beneficiarios.html', {
        'beneficiarios': beneficiarios, 'sucursales': sucursales, 'empresa': empresa_actual, 'filtros': {'q': q, 'sucursal': sucursal_id}
    })

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver', json_response=True)
def obtener_beneficiario_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        data = {
            'id': ben.id, 'rfc': ben.rfc, 'nombre_razon_social': ben.nombre_razon_social,
            'registro_patronal': ben.registro_patronal, 'calle': ben.calle, 'num_ext': ben.num_ext,
            'num_int': ben.num_int, 'entre_calle': ben.entre_calle, 'y_calle': ben.y_calle,
            'colonia': ben.colonia, 'cp': ben.cp, 'municipio_alcaldia': ben.municipio_alcaldia,
            'entidad_federativa': ben.entidad_federativa, 'correo': ben.correo, 'telefono': ben.telefono,
        }
        return JsonResponse({'success': True, 'data': data})
    except Beneficiario.DoesNotExist: return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'crear', json_response=True)
def crear_beneficiario_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual: return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)
    try:
        data = request.POST; sucursal_id = request.session.get('sucursal_id')
        nuevo = Beneficiario(
            empresa=empresa_actual, sucursal_id=sucursal_id, rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'), registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'), num_ext=data.get('num_ext'), num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'), y_calle=data.get('y_calle'), colonia=data.get('colonia'),
            cp=data.get('cp'), municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'), correo=data.get('correo'), telefono=data.get('telefono'),
        )
        nuevo.save()
        return JsonResponse({'success': True, 'message': 'Beneficiario registrado correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'editar', json_response=True)
def editar_beneficiario_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        data = request.POST
        ben.rfc = data.get('rfc', '').upper(); ben.nombre_razon_social = data.get('nombre_razon_social')
        ben.registro_patronal = data.get('registro_patronal'); ben.calle = data.get('calle')
        ben.num_ext = data.get('num_ext'); ben.num_int = data.get('num_int')
        ben.entre_calle = data.get('entre_calle'); ben.y_calle = data.get('y_calle')
        ben.colonia = data.get('colonia'); ben.cp = data.get('cp')
        ben.municipio_alcaldia = data.get('municipio_alcaldia'); ben.entidad_federativa = data.get('entidad_federativa')
        ben.correo = data.get('correo'); ben.telefono = data.get('telefono')
        ben.save()
        return JsonResponse({'success': True, 'message': 'Beneficiario actualizado correctamente.'})
    except Beneficiario.DoesNotExist: return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('sua', 'ver')
def lista_sua(request):
    empresa_actual = get_empresa_actual(request)
    importaciones = ImportacionSUA.objects.filter(empresa=empresa_actual).select_related('sucursal').order_by('-fecha_importacion')
    
    q_reg_pat = request.GET.get('reg_patronal', '')
    q_razon = request.GET.get('razon_social', '')
    q_periodo = request.GET.get('periodo', '')
    sucursal_id = request.GET.get('sucursal', '')

    if q_reg_pat:
        importaciones = importaciones.filter(registro_patronal__icontains=q_reg_pat)
    if q_razon:
        importaciones = importaciones.filter(nombre_razon_social__icontains=q_razon)
    if q_periodo:
        importaciones = importaciones.filter(periodo__icontains=q_periodo)
    if sucursal_id:
        importaciones = importaciones.filter(sucursal_id=sucursal_id)

    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    
    return render(request, 'recursos_humanos/lista_sua.html', {
        'importaciones': importaciones, 
        'sucursales': sucursales, 
        'empresa': empresa_actual, 
        'filtros': {
            'reg_patronal': q_reg_pat, 
            'razon_social': q_razon, 
            'periodo': q_periodo, 
            'sucursal': sucursal_id
        }
    })

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('sua', 'importar', json_response=True)
def importar_sua_ajax(request):
    empresa_actual = get_empresa_actual(request)
    pdf_file = request.FILES.get('archivo_sua')
    tipo_importacion = request.POST.get('tipo', 'bimestral')
    if not pdf_file: return JsonResponse({'success': False, 'error': 'No se proporcionó ningún archivo.'})
    try:
        if not pdfplumber: return JsonResponse({'success': False, 'error': 'Librería pdfplumber no instalada.'})
        
        text_lines = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if text:
                    text_lines.extend(text.split('\n'))
        
        full_text = "\n".join(text_lines)
        
        reg_pat_val, rfc_emp_val, area_val = "", "", ""
        nom_razon_val, deleg_val = "", ""
        actividad_val, subdeleg_val = "", ""
        domicilio_val, mun_alc_val = "", ""
        cp_val, entidad_val, prima_val = "", "", ""
        periodo_val = "Desconocido"

        for line in text_lines:
            if "Registro Patronal:" in line:
                m_rp = re.search(r'Registro Patronal:\s*([\w-]+)', line, re.I)
                m_rfc = re.search(r'RFC:\s*([\w\d-]+)', line, re.I)
                m_area = re.search(r'Area Geográfica:\s*(.*?)(?=\s{2,}|Delegación|$)', line, re.I)
                if m_rp: reg_pat_val = m_rp.group(1).strip()
                if m_rfc: rfc_emp_val = m_rfc.group(1).strip()
                if m_area: area_val = m_area.group(1).strip()
            
            if "Nombre o Razón Social:" in line:
                m_nom = re.search(r'Nombre o Razón Social:\s*(.*?)(?=\s{2,}|Delegación|Convenio|Aportación|V \d|$)', line, re.I)
                m_del = re.search(r'Delegación IMSS:\s*(.*?)(?=\s{2,}|Fecha|Convenio|Aportación|V \d|$)', line, re.I)
                if m_nom: nom_razon_val = m_nom.group(1).strip()
                if m_del: deleg_val = m_del.group(1).strip()

            if "Actividad:" in line:
                m_act = re.search(r'Actividad:\s*(.*?)(?=\s{2,}|Subdelegación|Convenio|Aportación|V \d|$)', line, re.I)
                m_sub = re.search(r'SubDelegación IMSS:\s*(.*?)(?=\s{2,}|Area|Convenio|Aportación|V \d|$)', line, re.I)
                if m_act: actividad_val = m_act.group(1).strip()
                if m_sub: subdeleg_val = m_sub.group(1).strip()

            if "Domicilio:" in line:
                m_dom = re.search(r'Domicilio:\s*(.*?)(?=\s{2,}|Pob|Convenio|Aportación|V \d|$)', line, re.I)
                m_mun = re.search(r'Pob\., Mun\. / Alcaldía:\s*(.*?)(?=\s{2,}|Prima|Convenio|Aportación|V \d|$)', line, re.I)
                if m_dom: domicilio_val = m_dom.group(1).strip()
                if m_mun: mun_alc_val = m_mun.group(1).strip()

            if "Código Postal:" in line:
                m_cp = re.search(r'Código Postal:\s*(\d+)', line, re.I)
                m_ent = re.search(r'Entidad:\s*(.*?)(?=\s{2,}|Prima|Convenio|Aportación|V \d|$)', line, re.I)
                m_pri = re.search(r'Prima de R\.T\.\s*([\d\.,%]+)', line, re.I)
                if m_cp: cp_val = m_cp.group(1).strip()
                if m_ent: entidad_val = m_ent.group(1).strip()
                if m_pri: prima_val = m_pri.group(1).strip()
            
            if "Proceso:" in line:
                m_per = re.search(r'(?:Período|Bimestre)\s+de\s+Proceso:\s*([\w\d-]+)', line, re.I)
                if m_per: periodo_val = m_per.group(1).strip()

        total_reporte = 0
        m_total_rep = re.search(r'Total\s+de\s+cotizaciones:\s*(\d+)', full_text, re.I)
        if m_total_rep:
            total_reporte = int(m_total_rep.group(1))

        sucursal_id = request.session.get('sucursal_id')
        created_count = 0
        nss_encontrados = set()

        with transaction.atomic():
            importacion = ImportacionSUA.objects.create(
                empresa=empresa_actual, sucursal_id=sucursal_id,
                registro_patronal=reg_pat_val,
                rfc_empresa=rfc_emp_val,
                nombre_razon_social=nom_razon_val,
                actividad=limpiar_basura_header(actividad_val),
                domicilio=limpiar_basura_header(domicilio_val),
                cp=limpiar_basura_header(cp_val),
                entidad=limpiar_basura_header(entidad_val),
                area_geografica=limpiar_basura_header(area_val),
                delegacion_imss=limpiar_basura_header(deleg_val),
                subdelegacion_imss=limpiar_basura_header(subdeleg_val),
                municipio_alcaldia=limpiar_basura_header(mun_alc_val),
                prima_rt=prima_val,
                periodo=limpiar_basura_header(periodo_val),
                tipo=tipo_importacion
            )

            current_worker_info = None
            stop_workers = False
            
            KEYWORDS_EXCLUDE = [
                'REGISTRO PATRONAL', 'RFC', 'NOMBRE O RAZÓN SOCIAL', 'DELEGACIÓN', 
                'ACTIVIDAD', 'DOMICILIO', 'BIMESTRE', 'PERIODO', 'POB.', 
                'CÓDIGO POSTAL', 'ENTIDAD', 'PRIMA', 'PAGINA', 'HOJA'
            ]

            for line in text_lines:
                l_clean = line.replace('$', '').strip()
                if not l_clean: continue

                # PARO DEFINITIVO REFORZADO:
                # Si la línea tiene palabras de resumen contable O bloques de subrayado, cerramos contexto.
                if re.search(r'TOTAL\s+DE\s+(DÍAS|COTIZACIONES|RCV|INFONAVIT)', l_clean.upper()) or \
                   re.search(r'([_-]\s?){7,}', l_clean):
                    current_worker_info = None
                    # Si es la sección final de totales, activamos el stop general
                    if re.search(r'TOTAL\s+DE\s+COTIZACIONES', l_clean.upper()) or "TOTALES" in l_clean.upper():
                        stop_workers = True 
                    continue
                
                if stop_workers: continue

                # Detección de Identidad (L1) con soporte para espacios en ubicación
                nss_match = re.search(r'(\d{2}-\d{2}-\d{2}-\d{4}-\d)', l_clean)
                if nss_match:
                    nss = nss_match.group(1)
                    # Buscamos el RFC/CURP que siempre rodea al nombre y antecede a la ubicación
                    m_rfc = re.search(r'\s([A-Z0-9]{13,18})\s', l_clean)
                    if m_rfc:
                        rfc = m_rfc.group(1)
                        # El nombre está entre el NSS y el RFC
                        # La ubicación está después del RFC
                        parts_nss = l_clean.split(nss)
                        if len(parts_nss) > 1:
                            parts_rfc = parts_nss[1].split(rfc)
                            if len(parts_rfc) > 1:
                                current_worker_info = {
                                    'nss': nss,
                                    'nombre': parts_rfc[0].strip(),
                                    'rfc': rfc,
                                    'clave_u': parts_rfc[1].strip()
                                }
                                nss_encontrados.add(nss)
                                continue

                if current_worker_info:
                    # Detectar cabecera de movimiento
                    m_header = re.match(r'^([^0-9\s,]{2,})?\s*(\d{2}/\d{2}/\d{4})?\s*(.*)', l_clean, re.I)
                    
                    clave_mov = '-'
                    fecha_mov = ''
                    resto_linea = l_clean

                    if m_header:
                        clave_mov = m_header.group(1).strip().rstrip(',') if m_header.group(1) else '-'
                        fecha_mov = m_header.group(2) or ''
                        resto_linea = m_header.group(3).strip()

                    tokens = re.findall(r'\$?\s*[\d\.,]+%?|FD', resto_linea)
                    tokens = [t.replace(',', '').strip() for t in tokens if t.strip()]

                    clave_limpia = clave_mov.lower()
                    es_movimiento_puro = (clave_limpia in ['baja', 'reingreso', 'modificación', 'alta'] and fecha_mov != "")
                    
                    # VALIDACIÓN CRÍTICA SUGERIDA: 
                    # 1. El token 0 (Días) no puede ser de más de 2 dígitos (máx 99).
                    # 2. Debe haber un SDI válido en el token 1.
                    try:
                        dias_val = int(float(tokens[0]))
                        tiene_sdi = len(tokens) >= 2 and re.match(r'^\d+\.?\d*$', tokens[1]) and float(tokens[1]) > 0
                        es_movimiento_datos = (dias_val <= 99 and tiene_sdi)
                    except:
                        es_movimiento_datos = False

                    if es_movimiento_puro or es_movimiento_datos:
                        cred_viv, tipo_cred, fecha_cred = "", "", ""
                        cred_match = re.search(r'(\d{10})\s+([A-Z]+)\s+(\d{2}/\d{2}/\d{4})$', resto_linea)
                        if cred_match:
                            cred_viv, tipo_cred, fecha_cred = cred_match.groups()

                        trabajador_data = {
                            'importacion': importacion,
                            'nss': current_worker_info['nss'],
                            'nombre': current_worker_info['nombre'],
                            'rfc_curp': current_worker_info['rfc'],
                            'clave_ubicacion': current_worker_info['clave_u'],
                            'clave_mov': clave_mov,
                            'fecha_mov': fecha_mov,
                            'cred_vivienda': cred_viv,
                            'tipo_mov_credito': tipo_cred,
                            'fecha_mov_credito': fecha_cred,
                            'dias': 0, 'sdi': 0, 'licencias': 0, 'incapacidades': 0, 'ausentismos': 0,
                            'retiro': 0, 'patronal': 0, 'obrera': 0, 'subtotal': 0,
                            'aportacion_patronal': 0, 'tipo_valor_infonavit': '-', 'amortizacion': 0, 'suma_infonavit': 0,
                            'total_general': 0
                        }

                        if es_movimiento_datos:
                            try:
                                trabajador_data.update({
                                    'dias': dias_val,
                                    'sdi': Decimal(tokens[1])
                                })
                                if len(tokens) >= 5:
                                    trabajador_data.update({
                                        'licencias': int(float(tokens[2])), 
                                        'incapacidades': int(float(tokens[3])), 
                                        'ausentismos': int(float(tokens[4]))
                                    })
                                if len(tokens) >= 9:
                                    trabajador_data.update({
                                        'retiro': Decimal(tokens[5]), 
                                        'patronal': Decimal(tokens[6]),
                                        'obrera': Decimal(tokens[7]), 
                                        'subtotal': Decimal(tokens[8])
                                    })
                                if len(tokens) >= 13:
                                    trabajador_data.update({
                                        'aportacion_patronal': Decimal(tokens[9]),
                                        'tipo_valor_infonavit': tokens[10],
                                        'amortizacion': Decimal(tokens[11]),
                                        'suma_infonavit': Decimal(tokens[12])
                                    })
                                elif len(tokens) == 12:
                                    trabajador_data.update({
                                        'aportacion_patronal': Decimal(tokens[9]),
                                        'tipo_valor_infonavit': '-',
                                        'amortizacion': Decimal(tokens[10]),
                                        'suma_infonavit': Decimal(tokens[11])
                                    })
                                elif len(tokens) == 11:
                                    trabajador_data.update({
                                        'aportacion_patronal': Decimal(tokens[9]),
                                        'tipo_valor_infonavit': '-',
                                        'amortizacion': Decimal('0.00'),
                                        'suma_infonavit': Decimal(tokens[10])
                                    })
                                
                                trabajador_data['total_general'] = trabajador_data['subtotal'] + trabajador_data['suma_infonavit']
                            except: pass

                        TrabajadorSUA.objects.create(**trabajador_data)
                        created_count += 1
                    else:
                        # Si encontramos TOTAL o algo que no cuadra con días/SDI, cerramos contexto
                        if not nss_match:
                            current_worker_info = None

            if created_count == 0:
                raise Exception("No se detectaron trabajadores válidos.")
            
            unique_count = len(nss_encontrados)
            msg_validacion = ""
            if total_reporte > 0 and unique_count != total_reporte:
                msg_validacion = f" Advertencia: Se detectaron {unique_count} trabajadores únicos pero el reporte indica un total de {total_reporte}."

        return JsonResponse({'success': True, 'message': f'Importación exitosa: {created_count} registros procesados.{msg_validacion}'})
    except Exception as e: 
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('sua', 'ver', json_response=True)
def obtener_registro_sua_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        imp = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        trabajadores = []
        totales = {
            'dias': 0, 'retiro': 0, 'patronal_rcv': 0, 'obrera_rcv': 0, 'total_rcv': 0,
            'ap_pat_inf': 0, 'tipo_val_inf': 0, 'amortiz': 0, 'total_inf': 0, 'total_general': 0
        }

        for t in imp.trabajadores.all().order_by('id'):
            trabajadores.append({
                'nss': t.nss,
                'nombre': t.nombre,
                'rfc': t.rfc_curp,
                'clave_u': t.clave_ubicacion,
                'clave_mov': t.clave_mov,
                'fecha_mov': t.fecha_mov,
                'dias': t.dias,
                'sdi': str(t.sdi),
                'lic': t.licencias,
                'inc': t.incapacidades,
                'aus': t.ausentismos,
                'retiro': str(t.retiro),
                'patronal_rcv': str(t.patronal),
                'obrera_rcv': str(t.obrera),
                'total_rcv': str(t.subtotal),
                'ap_pat_inf': str(t.aportacion_patronal),
                'tipo_val_inf': t.tipo_valor_infonavit or '-',
                'amortiz': str(t.amortizacion),
                'total_inf': str(t.suma_infonavit),
                'cred_viv': t.cred_vivienda or '',
                'tipo_mov_cred': t.tipo_mov_credito or '',
                'fecha_mov_cred': t.fecha_mov_credito or '',
                'baja_clave': t.baja_clave or '',
                'baja_fecha': t.baja_fecha or '',
                'total_general': str(t.total_general),
            })
            totales['dias'] += t.dias
            totales['retiro'] += float(t.retiro)
            totales['patronal_rcv'] += float(t.patronal)
            totales['obrera_rcv'] += float(t.obrera)
            totales['total_rcv'] += float(t.subtotal)
            totales['ap_pat_inf'] += float(t.aportacion_patronal)
            
            if t.tipo_valor_infonavit and t.tipo_valor_infonavit != '-':
                val_limpio = re.sub(r'[^\d.]', '', t.tipo_valor_infonavit)
                if val_limpio:
                    totales['tipo_val_inf'] += float(val_limpio)

            totales['amortiz'] += float(t.amortizacion)
            totales['total_inf'] += float(t.suma_infonavit)
            totales['total_general'] += float(t.total_general)

        for key in totales:
            if key == 'dias': totales[key] = int(totales[key])
            else: totales[key] = "{:,.2f}".format(totales[key])

        data = {
            'empresa': {
                'razon_social': imp.nombre_razon_social,
                'rfc': imp.rfc_empresa,
                'reg_patronal': imp.registro_patronal,
                'actividad': limpiar_basura_header(imp.actividad),
                'domicilio': limpiar_basura_header(imp.domicilio),
                'cp': limpiar_basura_header(imp.cp),
                'entidad': limpiar_basura_header(imp.entidad),
                'periodo': limpiar_basura_header(imp.periodo),
                'tipo': imp.get_tipo_display()
            },
            'trabajadores': trabajadores,
            'totales': totales
        }
        return JsonResponse({'success': True, 'data': data})
    except ImportacionSUA.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No se encontró la importación.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('sua', 'eliminar', json_response=True)
def eliminar_sua_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        imp = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        imp.delete()
        return JsonResponse({'success': True, 'message': 'Registro eliminado correctamente.'})
    except ImportacionSUA.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No se encontró la importación.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('sua', 'ver')
def exportar_sua_excel(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        imp = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="SUA_{imp.periodo}_{imp.registro_patronal}.csv"'
        response.write(u'\ufeff'.encode('utf8'))
        
        writer = csv.writer(response)
        writer.writerow(['REPORTE DE INTEGRACIÓN SUA'])
        writer.writerow(['Empresa', imp.nombre_razon_social])
        writer.writerow(['Registro Patronal', imp.registro_patronal])
        writer.writerow(['Periodo', imp.periodo])
        writer.writerow(['Tipo', imp.get_tipo_display()])
        writer.writerow([])
        writer.writerow([
            'NSS', 'Nombre', 'RFC/CURP', 'Ubicación', 'Movimiento', 'Fecha Mov.', 
            'Días', 'SDI', 'Licencias', 'Incapacidad', 'Ausentismo',
            'Retiro', 'Cesantía Pat.', 'Cesantía Obr.', 'Suma RCV',
            'Ap. Pat. Infonavit', '% o $ o FD', 'Amortización', 'Suma Infonavit',
            'Cred. Vivienda', 'Tipo Mov. Cred.', 'Fecha Mov. Cred.',
            'Baja/Otros Mov.', 'Fecha Baja', 'Total General'
        ])
        
        for t in imp.trabajadores.all().order_by('id'):
            writer.writerow([
                t.nss, t.nombre, t.rfc_curp, t.clave_ubicacion, t.clave_mov, t.fecha_mov,
                t.dias, t.sdi, t.licencias, t.incapacidades, t.ausentismos,
                t.retiro, t.patronal, t.obrera, t.subtotal,
                t.aportacion_patronal, t.tipo_valor_infonavit or '-', t.amortizacion, t.suma_infonavit,
                t.cred_vivienda, t.tipo_mov_credito, t.fecha_mov_credito,
                t.baja_clave, t.baja_fecha, t.total_general
            ])
            
        return response
    except ImportacionSUA.DoesNotExist:
        return HttpResponse("No se encontró la importación", status=404)
