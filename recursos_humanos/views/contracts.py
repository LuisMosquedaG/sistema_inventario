from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
import openpyxl
from datetime import datetime

from ..models import Empleado, Contrato, Contratista, Beneficiario
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual

@login_required(login_url='/login/')
@require_hr_permission('contratos', 'ver')
def lista_contratos(request):
    empresa_actual = get_empresa_actual(request)
    import datetime as dt
    today = dt.date.today()
    
    # 1. Sincronizar estado_vigencia
    # Vencidos
    Contrato.objects.filter(
        empresa=empresa_actual,
        vigencia_contrato__lt=today
    ).exclude(
        estado_vigencia='vencido'
    ).update(
        estado_vigencia='vencido'
    )
    # Vigentes (si la fecha es futura o es nula, restauramos a 'vigente')
    Contrato.objects.filter(
        empresa=empresa_actual
    ).filter(
        Q(vigencia_contrato__gte=today) | Q(vigencia_contrato__isnull=True)
    ).filter(
        estado_vigencia='vencido'
    ).update(
        estado_vigencia='vigente'
    )

    # 2. Sincronizar estado_periodicidad
    # Cerrados
    Contrato.objects.filter(
        empresa=empresa_actual,
        fecha_fin__lt=today
    ).exclude(
        estado_periodicidad='cerrado'
    ).update(
        estado_periodicidad='cerrado'
    )
    # Vigentes (si la fecha es futura o es nula, restauramos a 'vigente')
    Contrato.objects.filter(
        empresa=empresa_actual
    ).filter(
        Q(fecha_fin__gte=today) | Q(fecha_fin__isnull=True)
    ).filter(
        estado_periodicidad='cerrado'
    ).update(
        estado_periodicidad='vigente'
    )

    # 3. Sincronizar campo legacy 'estado' para compatibilidad
    Contrato.objects.filter(
        empresa=empresa_actual,
        estado_periodicidad='cerrado'
    ).exclude(
        estado='cerrado'
    ).update(
        estado='cerrado'
    )

    Contrato.objects.filter(
        empresa=empresa_actual,
        estado_vigencia='vencido'
    ).exclude(
        estado__in=['cerrado', 'vencido']
    ).update(
        estado='vencido'
    )

    Contrato.objects.filter(
        empresa=empresa_actual,
        estado_vigencia='vigente',
        estado_periodicidad='vigente'
    ).exclude(
        estado='vigente'
    ).update(
        estado='vigente'
    )

    contratos = Contrato.objects.filter(empresa=empresa_actual).prefetch_related('empleados', 'empleados__sucursal').order_by('-fecha_inicio')
    
    q = request.GET.get('q', '')
    folio = request.GET.get('folio', '')
    beneficiario_id = request.GET.get('beneficiario_id', '')
    contratista_id = request.GET.get('contratista_id', '')
    empleado_id = request.GET.get('empleado_id', '')
    estado = request.GET.get('estado', '')
    estado_vigencia = request.GET.get('estado_vigencia', '')
    estado_periodicidad = request.GET.get('estado_periodicidad', '')
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
    
    if folio:
        contratos = contratos.filter(folio__icontains=folio)
        
    if beneficiario_id:
        contratos = contratos.filter(beneficiario_id=beneficiario_id)
        
    if contratista_id:
        contratos = contratos.filter(contratista_id=contratista_id)
    
    if empleado_id:
        contratos = contratos.filter(empleados__id=empleado_id)
    
    if estado:
        contratos = contratos.filter(estado=estado)
    if estado_vigencia:
        contratos = contratos.filter(estado_vigencia=estado_vigencia)
    if estado_periodicidad:
        contratos = contratos.filter(estado_periodicidad=estado_periodicidad)
            
    if sucursal_id:
        contratos = contratos.filter(sucursal_id=sucursal_id)

    empleados = Empleado.objects.filter(empresa=empresa_actual).order_by('apellido_paterno')
    contratistas = Contratista.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    beneficiarios = Beneficiario.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')
    
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    # PAGINACIÓN
    paginator = Paginator(contratos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)


    return render(request, 'recursos_humanos/lista_contratos.html', {
        'page_obj': page_obj,
        'empleados': empleados,
        'contratistas': contratistas,
        'beneficiarios': beneficiarios,
        'sucursales': sucursales,
        'empresa': empresa_actual,
        'filtros': {
            'q': q,
            'folio': folio,
            'beneficiario_id': beneficiario_id,
            'contratista_id': contratista_id,
            'empleado_id': empleado_id,
            'estado': estado,
            'estado_vigencia': estado_vigencia,
            'estado_periodicidad': estado_periodicidad,
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
            'version': con.version,
            'tipo_contrato': con.tipo_contrato,
            'objeto_contrato': con.objeto_contrato,
            'monto_contrato': str(con.monto_contrato),
            'fecha_inicio': con.fecha_inicio.isoformat() if con.fecha_inicio else '',
            'fecha_fin': con.fecha_fin.isoformat() if con.fecha_fin else '',
            'vigencia_contrato': con.vigencia_contrato.isoformat() if con.vigencia_contrato else '',
            'num_estimado_trabajadores': con.num_estimado_trabajadores,
            'estado': con.estado,
            'estado_vigencia': con.estado_vigencia,
            'estado_periodicidad': con.estado_periodicidad,
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
                contratista_id=data.get('contratista') or None,
                beneficiario_id=data.get('beneficiario') or None,
                folio=data.get('folio'),
                version=data.get('version', '1'),
                tipo_contrato=data.get('tipo_contrato'),
                objeto_contrato=data.get('objeto_contrato'),
                monto_contrato=Decimal(data.get('monto_contrato') or '0'),
                fecha_inicio=data.get('fecha_inicio') or None,
                fecha_fin=data.get('fecha_fin') or None,
                vigencia_contrato=data.get('vigencia_contrato') or None,
                num_estimado_trabajadores=int(data.get('num_estimado_trabajadores') or 0),
                estado_periodicidad=data.get('estado_periodicidad', 'vigente'),
                estado_vigencia=data.get('estado_vigencia', 'vigente'),
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
            con.contratista_id = data.get('contratista') or None
            con.beneficiario_id = data.get('beneficiario') or None
            con.folio = data.get('folio')
            con.version = data.get('version', '1')
            con.tipo_contrato = data.get('tipo_contrato')
            con.objeto_contrato = data.get('objeto_contrato')
            con.monto_contrato = Decimal(data.get('monto_contrato') or '0')
            con.fecha_inicio = data.get('fecha_inicio') or None
            con.fecha_fin = data.get('fecha_fin') or None
            con.vigencia_contrato = data.get('vigencia_contrato') or None
            con.num_estimado_trabajadores = int(data.get('num_estimado_trabajadores') or 0)
            con.estado_periodicidad = data.get('estado_periodicidad', 'vigente')
            con.estado_vigencia = data.get('estado_vigencia', 'vigente')
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
@require_POST
@require_hr_permission('contratos', 'eliminar', json_response=True)
def eliminar_contrato_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        con = Contrato.objects.get(id=id, empresa=empresa_actual)
        con.delete()
        return JsonResponse({'success': True, 'message': 'Contrato eliminado correctamente.'})
    except Contrato.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contrato no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@transaction.atomic
def importar_contratos_ajax(request):
    """Cargador de contratos y beneficiarios desde Excel."""
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'status': 'error', 'message': 'Empresa no encontrada.'})
    
    file = request.FILES.get('archivo')
    if not file:
        return JsonResponse({'status': 'error', 'message': 'No se proporcionó ningún archivo.'})
    
    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        sheet = wb.active
        headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
        
        def get_val(row, header_name, default=None):
            try:
                idx = headers.index(header_name)
                val = row[idx].value
                return val if val is not None else default
            except (ValueError, IndexError):
                return default

        def to_decimal(val):
            if val is None: return Decimal('0')
            try:
                v = str(val).replace(',', '').replace('$', '').strip()
                return Decimal(v) if v else Decimal('0')
            except: return Decimal('0')

        def to_date(val):
            if isinstance(val, datetime): return val.date()
            if isinstance(val, str):
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%dT%H:%M:%S'):
                    try: return datetime.strptime(val.strip(), fmt).date()
                    except: pass
            return None

        TIPO_CONTRATO_MAP = {
            '01': '01', 'tiempo indeterminado': '01', 'indeterminado': '01',
            '02': '02', 'obra determinada': '02',
            '03': '03', 'tiempo determinado': '03', 'determinado': '03',
            '05': '05', 'prueba': '05',
            '06': '06', 'capacitacion': '06', 'capacitación': '06',
        }

        sucursal_id = request.session.get('sucursal_id')
        count = 0
        
        for row in sheet.iter_rows(min_row=2):
            rfc_beneficiario = str(get_val(row, 'Registro Federal de Contribuyentes', '')).strip().upper()
            if not rfc_beneficiario:
                continue

            rfc_sujeto_obligado = str(get_val(row, 'Registro Federal de Contribuyente del sujeto obligado', '')).strip().upper()
            contratista = None
            if rfc_sujeto_obligado:
                contratista = Contratista.objects.filter(empresa=empresa_actual, rfc=rfc_sujeto_obligado).first()

            objeto = str(get_val(row, 'Objeto del contrato', '')).strip()

            # Validación: Si existe el RFC pero el objeto es diferente, creamos otro beneficiario
            beneficiario = Beneficiario.objects.filter(
                empresa=empresa_actual,
                rfc=rfc_beneficiario,
                objeto_contrato=objeto
            ).first()

            if not beneficiario:
                # Si no existe con ese RFC y Objeto, creamos uno nuevo
                # Generamos una clave única temporal basada en RFC y un fragmento del objeto si es necesario
                nombre_ben = str(get_val(row, 'Nombre denominacion o razon social', '')).strip()
                beneficiario = Beneficiario.objects.create(
                    empresa=empresa_actual,
                    sucursal_id=sucursal_id,
                    rfc=rfc_beneficiario,
                    nombre_razon_social=nombre_ben,
                    objeto_contrato=objeto,
                    registro_patronal=str(get_val(row, 'Registro Patronal ante el IMSS', '')).strip(),
                    calle=str(get_val(row, 'Calle', '')).strip(),
                    num_ext=str(get_val(row, 'Numero exterior', '')).strip(),
                    num_int=str(get_val(row, 'Numero interior', '')).strip(),
                    entre_calle=str(get_val(row, 'Entre calle', '')).strip(),
                    y_calle=str(get_val(row, 'Y calle', '')).strip(),
                    colonia=str(get_val(row, 'Colonia', '')).strip(),
                    cp=str(get_val(row, 'Codigo Postal', '')).strip(),
                    municipio_alcaldia=str(get_val(row, 'Municipio o Alcaldia', '')).strip(),
                    entidad_federativa=str(get_val(row, 'Entidad Federativa', '')).strip(),
                    correo=str(get_val(row, 'Correo electronico', '')).strip(),
                    telefono=str(get_val(row, 'telefono (numero extension)', '')).strip(),
                )
                # Asignamos una clave basada en su ID para garantizar unicidad si no venía una
                if not beneficiario.clave:
                    beneficiario.clave = f"BEN-{beneficiario.id}"
                    beneficiario.save()

            folio = str(get_val(row, 'Numero de contrato', '')).strip()
            tipo_raw = str(get_val(row, 'Tipo de contrato', '01')).strip().lower()
            tipo_contrato = '01'
            for key, code in TIPO_CONTRATO_MAP.items():
                if key in tipo_raw:
                    tipo_contrato = code
                    break
            
            monto = to_decimal(get_val(row, 'Monto del contrato'))
            vigencia = to_date(get_val(row, 'Vigencia (del contrato)'))
            f_inicio = to_date(get_val(row, 'Fecha de inicio (del contrato)'))
            f_fin = to_date(get_val(row, 'Fecha de termino (del contrato)'))
            num_trabajadores_raw = get_val(row, 'Numero estimado mensual de trabajadores que se pondran a disposicion (del contrato)', 0)
            try:
                num_trabajadores = int(num_trabajadores_raw) if num_trabajadores_raw else 0
            except:
                num_trabajadores = 0

            fecha_inicio_val = f_inicio or datetime.now().date()
            
            # Evitar duplicados: verificar si ya existe un contrato para el mismo folio, vigencia y periodo (inicio y fin)
            contrato_existente = Contrato.objects.filter(
                empresa=empresa_actual,
                folio=folio,
                vigencia_contrato=vigencia,
                fecha_inicio=fecha_inicio_val,
                fecha_fin=f_fin
            ).first()

            if contrato_existente:
                contrato_existente.beneficiario = beneficiario
                contrato_existente.contratista = contratista
                contrato_existente.tipo_contrato = tipo_contrato
                contrato_existente.objeto_contrato = objeto
                contrato_existente.monto_contrato = monto
                contrato_existente.num_estimado_trabajadores = num_trabajadores
                contrato_existente.save()
            else:
                Contrato.objects.create(
                    empresa=empresa_actual,
                    sucursal_id=sucursal_id,
                    beneficiario=beneficiario,
                    contratista=contratista,
                    folio=folio,
                    tipo_contrato=tipo_contrato,
                    objeto_contrato=objeto,
                    monto_contrato=monto,
                    vigencia_contrato=vigencia,
                    fecha_inicio=fecha_inicio_val,
                    fecha_fin=f_fin,
                    num_estimado_trabajadores=num_trabajadores,
                    estado='vigente'
                )
            count += 1

        return JsonResponse({
            'status': 'success', 
            'message': f'Proceso completado. Se registraron {count} contratos.'
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al procesar el archivo: {str(e)}'})
