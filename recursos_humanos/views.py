from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
import re
try:
    import pypdf
except ImportError:
    pypdf = None

from panel.models import Empresa
from .models import Empleado, Contrato, Contratista, Beneficiario, RegistroSUA
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission

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
    # Prioridad: 1. Parámetro POST (si existiera), 2. Parámetro GET, 3. Sesión
    suc_id = request.POST.get('sucursal') or request.GET.get('sucursal') or request.session.get('sucursal_id')
    return suc_id

@login_required(login_url='/login/')
@require_hr_permission('empleados', 'ver')
def lista_empleados(request):
    empresa_actual = get_empresa_actual(request)
    empleados = Empleado.objects.filter(empresa=empresa_actual).select_related('sucursal').order_by('apellido_paterno')
    
    # --- LÓGICA DE FILTRADO ---
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
            
    # Obtener lista de departamentos únicos para el filtro
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
        # Buscar contrato vinculado (el más reciente)
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

        # Validar número de empleado (si cambió)
        num_emp = data.get('num_empleado')
        if num_emp != emp.num_empleado and Empleado.objects.filter(empresa=empresa_actual, num_empleado=num_emp).exists():
            return JsonResponse({'success': False, 'error': f'El número de empleado {num_emp} ya existe.'})

        # Actualizar campos
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
        emp.num_empleado = num_emp
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
        
        # Sucursal se mantiene si ya tiene una, o se actualiza de la sesión si es necesario.
        # Pero el usuario dice "se coloca en automático", así que para editar mantendremos la que ya tiene
        # a menos que explícitamente se quiera forzar la de la sesión.
        # Por ahora lo dejamos como está (no se toca en editar si se quitó del modal).
        
        emp.save()

        # Actualizar vínculo con contrato
        contrato_id = data.get('contrato_id')
        if contrato_id:
            try:
                contrato = Contrato.objects.get(id=contrato_id, empresa=empresa_actual)
                # Si el contrato cambió, lo removemos de otros y lo agregamos al nuevo
                # (Asumimos lógica de 1 contrato activo para esta interfaz)
                emp.contratos_asignados.clear()
                contrato.empleados.add(emp)
            except Contrato.DoesNotExist:
                pass
        else:
            # Si se seleccionó "Sin Contrato", remover de todos
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
        num_emp = data.get('num_empleado')
        if Empleado.objects.filter(empresa=empresa_actual, num_empleado=num_emp).exists():
            return JsonResponse({'success': False, 'error': f'El número de empleado {num_emp} ya existe.'})

        # Obtener sucursal de la sesión
        sucursal_id = request.session.get('sucursal_id')

        nuevo_empleado = Empleado(
            empresa=empresa_actual,
            sucursal_id=sucursal_id,
            # 1. Identificación
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
            # Domicilio
            calle=data.get('calle'),
            num_ext=data.get('num_ext'),
            num_int=data.get('num_int'),
            colonia=data.get('colonia'),
            cp=data.get('cp'),
            ciudad=data.get('ciudad'),
            estado_dir=data.get('estado_dir'),
            # 2. Control
            num_empleado=num_emp,
            estado=data.get('estado'),
            # 3. Puesto
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
            # 4. Salarial
            salario_diario_ordinario=Decimal(data.get('salario_diario_ordinario', '0')),
            sbc=Decimal(data.get('sbc', '0')),
            sdi=Decimal(data.get('sdi', '0')),
            forma_pago=data.get('forma_pago'),
            clave_percepcion_sat=data.get('clave_percepcion_sat', '001'),
            tipo_salario=data.get('tipo_salario'),
            # 5. Beneficios
            registro_patronal=data.get('registro_patronal'),
            num_infonavit=data.get('num_infonavit'),
            num_fonacot=data.get('num_fonacot'),
            fondo_ahorro=(data.get('fondo_ahorro') == 'on'),
            porcentaje_fondo=Decimal(data.get('porcentaje_fondo', '0')),
            caja_ahorro=(data.get('caja_ahorro') == 'on'),
            # 6. Bancarios
            banco_nombre=data.get('banco_nombre'),
            clabe=data.get('clabe'),
            num_cuenta=data.get('num_cuenta'),
            tipo_cuenta=data.get('tipo_cuenta'),
            tarjeta_nomina=(data.get('tarjeta_nomina') == 'on'),
            num_tarjeta=data.get('num_tarjeta'),
        )
        
        nuevo_empleado.save()

        # Vincular con contrato si se proporcionó
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
    
    # --- LÓGICA DE FILTRADO ---
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
            Q(notas__icontains=q)
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
    
    from preferencias.models import Sucursal
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
            
            # Manejar ManyToMany para empleados
            empleados_ids = request.POST.getlist('empleados[]')
            if not empleados_ids:
                empleados_ids = request.POST.getlist('empleados')
                
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
            
            # Actualizar empleados
            empleados_ids = request.POST.getlist('empleados[]')
            if not empleados_ids:
                empleados_ids = request.POST.getlist('empleados')
                
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
    
    # --- LÓGICA DE FILTRADO ---
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

    from preferencias.models import Sucursal
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
            'id': cont.id,
            'rfc': cont.rfc,
            'nombre_razon_social': cont.nombre_razon_social,
            'correo': cont.correo,
            'telefono': cont.telefono,
            'registro_patronal': cont.registro_patronal,
            'calle': cont.calle,
            'num_ext': cont.num_ext,
            'num_int': cont.num_int,
            'entre_calle': cont.entre_calle,
            'y_calle': cont.y_calle,
            'colonia': cont.colonia,
            'cp': cont.cp,
            'municipio_alcaldia': cont.municipio_alcaldia,
            'entidad_federativa': cont.entidad_federativa,
            'representante_legal': cont.representante_legal,
            'administrador_unico': cont.administrador_unico,
            'num_escritura': cont.num_escritura,
            'nombre_notario_publico': cont.nombre_notario_publico,
            'num_notario_publico': cont.num_notario_publico,
            'fecha_escritura_publica': cont.fecha_escritura_publica.isoformat() if cont.fecha_escritura_publica else '',
            'folio_mercantil': cont.folio_mercantil,
            'numero_stps': cont.numero_stps,
        }
        return JsonResponse({'success': True, 'data': data})
    except Contratista.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratistas', 'crear', json_response=True)
def crear_contratista_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)

    try:
        data = request.POST
        sucursal_id = request.session.get('sucursal_id')
        nuevo = Contratista(
            empresa=empresa_actual,
            sucursal_id=sucursal_id,
            rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'),
            correo=data.get('correo'),
            telefono=data.get('telefono'),
            registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'),
            num_ext=data.get('num_ext'),
            num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'),
            y_calle=data.get('y_calle'),
            colonia=data.get('colonia'),
            cp=data.get('cp'),
            municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'),
            representante_legal=data.get('representante_legal'),
            administrador_unico=data.get('administrador_unico'),
            num_escritura=data.get('num_escritura'),
            nombre_notario_publico=data.get('nombre_notario_publico'),
            num_notario_publico=data.get('num_notario_publico'),
            fecha_escritura_publica=data.get('fecha_escritura_publica') or None,
            folio_mercantil=data.get('folio_mercantil'),
            numero_stps=data.get('numero_stps'),
        )
        nuevo.save()
        return JsonResponse({'success': True, 'message': 'Contratista registrado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

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
        cont.correo = data.get('correo')
        cont.telefono = data.get('telefono')
        cont.registro_patronal = data.get('registro_patronal')
        cont.calle = data.get('calle')
        cont.num_ext = data.get('num_ext')
        cont.num_int = data.get('num_int')
        cont.entre_calle = data.get('entre_calle')
        cont.y_calle = data.get('y_calle')
        cont.colonia = data.get('colonia')
        cont.cp = data.get('cp')
        cont.municipio_alcaldia = data.get('municipio_alcaldia')
        cont.entidad_federativa = data.get('entidad_federativa')
        cont.representante_legal = data.get('representante_legal')
        cont.administrador_unico = data.get('administrador_unico')
        cont.num_escritura = data.get('num_escritura')
        cont.nombre_notario_publico = data.get('nombre_notario_publico')
        cont.num_notario_publico = data.get('num_notario_publico')
        cont.fecha_escritura_publica = data.get('fecha_escritura_publica') or None
        cont.folio_mercantil = data.get('folio_mercantil')
        cont.numero_stps = data.get('numero_stps')
        
        cont.save()
        return JsonResponse({'success': True, 'message': 'Contratista actualizado correctamente.'})
    except Contratista.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver')
def lista_beneficiarios(request):
    empresa_actual = get_empresa_actual(request)
    beneficiarios = Beneficiario.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    
    q = request.GET.get('q', '')
    sucursal_id = request.GET.get('sucursal', '')

    if q:
        beneficiarios = beneficiarios.filter(
            Q(nombre_razon_social__icontains=q) |
            Q(rfc__icontains=q) |
            Q(correo__icontains=q)
        )
        
    if sucursal_id:
        beneficiarios = beneficiarios.filter(sucursal_id=sucursal_id)

    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    return render(request, 'recursos_humanos/lista_beneficiarios.html', {
        'beneficiarios': beneficiarios,
        'sucursales': sucursales,
        'empresa': empresa_actual,
        'filtros': {'q': q, 'sucursal': sucursal_id}
    })

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver', json_response=True)
def obtener_beneficiario_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        data = {
            'id': ben.id,
            'rfc': ben.rfc,
            'nombre_razon_social': ben.nombre_razon_social,
            'registro_patronal': ben.registro_patronal,
            'calle': ben.calle,
            'num_ext': ben.num_ext,
            'num_int': ben.num_int,
            'entre_calle': ben.entre_calle,
            'y_calle': ben.y_calle,
            'colonia': ben.colonia,
            'cp': ben.cp,
            'municipio_alcaldia': ben.municipio_alcaldia,
            'entidad_federativa': ben.entidad_federativa,
            'correo': ben.correo,
            'telefono': ben.telefono,
        }
        return JsonResponse({'success': True, 'data': data})
    except Beneficiario.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'crear', json_response=True)
def crear_beneficiario_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)

    try:
        data = request.POST
        sucursal_id = request.session.get('sucursal_id')
        nuevo = Beneficiario(
            empresa=empresa_actual,
            sucursal_id=sucursal_id,
            rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'),
            registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'),
            num_ext=data.get('num_ext'),
            num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'),
            y_calle=data.get('y_calle'),
            colonia=data.get('colonia'),
            cp=data.get('cp'),
            municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'),
            correo=data.get('correo'),
            telefono=data.get('telefono'),
        )
        nuevo.save()
        return JsonResponse({'success': True, 'message': 'Beneficiario registrado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'editar', json_response=True)
def editar_beneficiario_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        data = request.POST

        ben.rfc = data.get('rfc', '').upper()
        ben.nombre_razon_social = data.get('nombre_razon_social')
        ben.registro_patronal = data.get('registro_patronal')
        ben.calle = data.get('calle')
        ben.num_ext = data.get('num_ext')
        ben.num_int = data.get('num_int')
        ben.entre_calle = data.get('entre_calle')
        ben.y_calle = data.get('y_calle')
        ben.colonia = data.get('colonia')
        ben.cp = data.get('cp')
        ben.municipio_alcaldia = data.get('municipio_alcaldia')
        ben.entidad_federativa = data.get('entidad_federativa')
        ben.correo = data.get('correo')
        ben.telefono = data.get('telefono')
        
        ben.save()
        return JsonResponse({'success': True, 'message': 'Beneficiario actualizado correctamente.'})
    except Beneficiario.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('sua', 'ver')
def lista_sua(request):
    empresa_actual = get_empresa_actual(request)
    registros = RegistroSUA.objects.filter(empresa=empresa_actual).select_related('sucursal').order_by('-fecha_importacion')
    
    q = request.GET.get('q', '')
    sucursal_id = request.GET.get('sucursal', '')
    
    if q:
        registros = registros.filter(
            Q(nombre_trabajador__icontains=q) |
            Q(nss__icontains=q) |
            Q(periodo__icontains=q)
        )
    if sucursal_id:
        registros = registros.filter(sucursal_id=sucursal_id)

    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    
    return render(request, 'recursos_humanos/lista_sua.html', {
        'registros': registros,
        'sucursales': sucursales,
        'empresa': empresa_actual,
        'filtros': {'q': q, 'sucursal': sucursal_id}
    })

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('sua', 'importar', json_response=True)
def importar_sua_ajax(request):
    empresa_actual = get_empresa_actual(request)
    pdf_file = request.FILES.get('archivo_sua')
    
    if not pdf_file:
        return JsonResponse({'success': False, 'error': 'No se proporcionó ningún archivo.'})

    try:
        if not pypdf:
            return JsonResponse({'success': False, 'error': 'Librería de lectura PDF (pypdf) no instalada.'})

        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        # Extraer Periodo (Mes/Año)
        p_match = re.search(r'MES:\s*(\d+)\s*AÑO:\s*(\d+)', text, re.IGNORECASE)
        periodo_str = f"{p_match.group(1)}/{p_match.group(2)}" if p_match else "No detectado"

        # Buscar patrones de trabajadores (NSS de 11 dígitos)
        worker_pattern = re.compile(r'(\d{11})\s+([A-ZÁÉÍÓÚÑ\s\.]+?)\s+(\d+)\s+([\d\.,]+)')
        matches = worker_pattern.findall(text)

        created_count = 0
        sucursal_id = request.session.get('sucursal_id')

        with transaction.atomic():
            for m in matches:
                nss, nombre, dias, sdi_raw = m
                sdi_val = Decimal(sdi_raw.replace(',', ''))
                
                RegistroSUA.objects.create(
                    empresa=empresa_actual,
                    sucursal_id=sucursal_id,
                    nss=nss,
                    nombre_trabajador=nombre.strip(),
                    dias_cotizados=int(dias),
                    sdi=sdi_val,
                    periodo=periodo_str
                )
                created_count += 1

        if created_count == 0:
            return JsonResponse({'success': False, 'error': 'No se encontraron trabajadores legibles en el PDF. Verifique que sea un archivo oficial de SUA.'})

        return JsonResponse({'success': True, 'message': f'Procesado con éxito: {created_count} registros importados.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Error al procesar PDF: {str(e)}"})
