from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
from .models import Empleado

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal

@login_required(login_url='/login/')
def lista_empleados(request):
    empresa_actual = get_empresa_actual(request)
    empleados = Empleado.objects.filter(empresa=empresa_actual).order_by('apellido_paterno')
    return render(request, 'recursos_humanos/lista_empleados.html', {'empleados': empleados})

@login_required(login_url='/login/')
@require_POST
def crear_empleado_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)

    try:
        # Extraer datos del POST
        data = request.POST
        
        # Validar unicidad de número de empleado para esta empresa (opcional, pero recomendado)
        num_emp = data.get('num_empleado')
        if Empleado.objects.filter(empresa=empresa_actual, num_empleado=num_emp).exists():
            return JsonResponse({'success': False, 'error': f'El número de empleado {num_emp} ya existe.'})

        nuevo_empleado = Empleado(
            empresa=empresa_actual,
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
        return JsonResponse({'success': True, 'message': 'Empleado registrado correctamente.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

