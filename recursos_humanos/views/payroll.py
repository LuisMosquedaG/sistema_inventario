from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q
from decimal import Decimal
import openpyxl
import math
import re
from datetime import datetime

from ..models import Empleado, Contrato, Contratista, Nomina
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual

@login_required(login_url='/login/')
@require_hr_permission('nomina', 'ver')
def lista_nomina(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html')

    nominas = Nomina.objects.filter(empresa=empresa_actual).select_related('empleado', 'sucursal').order_by('-fecha_pago', 'nombre')

    # Filtros
    q = request.GET.get('q', '')
    f_folio = request.GET.get('folio', '')
    f_uuid = request.GET.get('uuid', '')
    f_colaborador = request.GET.get('colaborador', '')
    f_rfc_contratista = request.GET.get('rfc_contratista', '')
    f_fecha_pago = request.GET.get('fecha_pago', '')
    f_sucursal = request.GET.get('sucursal', '')

    if q:
        nominas = nominas.filter(
            Q(nombre__icontains=q) |
            Q(rfc__icontains=q) |
            Q(curp__icontains=q) |
            Q(folio__icontains=q) |
            Q(uuid__icontains=q) |
            Q(rfc_contratista__icontains=q)
        )
    
    if f_folio:
        nominas = nominas.filter(folio__icontains=f_folio)
    if f_uuid:
        nominas = nominas.filter(uuid__icontains=f_uuid)
    if f_colaborador:
        nominas = nominas.filter(nombre__icontains=f_colaborador)
    if f_rfc_contratista:
        nominas = nominas.filter(rfc_contratista__icontains=f_rfc_contratista)
    if f_fecha_pago:
        nominas = nominas.filter(fecha_pago=f_fecha_pago)
    if f_sucursal:
        nominas = nominas.filter(sucursal_id=f_sucursal)

    # Paginación
    paginator = Paginator(nominas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    empleados = Empleado.objects.filter(empresa=empresa_actual).order_by('apellido_paterno')
    contratistas = Contratista.objects.filter(empresa=empresa_actual).order_by('nombre_razon_social')

    return render(request, 'recursos_humanos/lista_nomina.html', {
        'page_obj': page_obj,
        'sucursales': sucursales,
        'empleados': empleados,
        'contratistas': contratistas,
        'empresa': empresa_actual,
        'filtros': {
            'q': q, 'folio': f_folio, 'uuid': f_uuid, 'colaborador': f_colaborador, 'rfc_contratista': f_rfc_contratista, 'fecha_pago': f_fecha_pago, 'sucursal': f_sucursal
        }
    })

@login_required(login_url='/login/')
@require_hr_permission('nomina', 'ver', json_response=True)
def obtener_nomina_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        nom = Nomina.objects.get(id=id, empresa=empresa_actual)
        def safe_decimal(val): return str(val) if val is not None else '0.00'
        data = {
            'id': nom.id, 'empleado': nom.empleado_id or '', 'periodo': nom.periodo, 'uso_cfdi': nom.uso_cfdi, 'uuid': nom.uuid or '', 'tipo_nomina': nom.tipo_nomina, 'serie': nom.serie or '', 'folio': nom.folio or '', 'fecha_emision': nom.fecha_emision.strftime('%Y-%m-%dT%H:%M') if nom.fecha_emision else '', 'fecha_certificacion': nom.fecha_certificacion.strftime('%Y-%m-%dT%H:%M') if nom.fecha_certificacion else '', 'fecha_pago': nom.fecha_pago.isoformat() if nom.fecha_pago else '', 'fecha_inicial_pago': nom.fecha_inicial_pago.isoformat() if nom.fecha_inicial_pago else '', 'fecha_final_pago': nom.fecha_final_pago.isoformat() if nom.fecha_final_pago else '', 'dias_pagados': safe_decimal(nom.dias_pagados), 'rfc': nom.rfc, 'curp': nom.curp, 'nss': nom.nss, 'nombre': nom.nombre, 'rfc_contratista': nom.rfc_contratista or '', 'sdi': safe_decimal(nom.sdi), 'sbc': safe_decimal(nom.sbc), 'vacaciones_exento': safe_decimal(nom.vacaciones_exento), 'vacaciones_dignas_exento': safe_decimal(nom.vacaciones_dignas_exento), 'aguinaldo_exento': safe_decimal(nom.aguinaldo_exento), 'sueldo_gravado': safe_decimal(nom.sueldo_gravado), 'vacaciones_gravado': safe_decimal(nom.vacaciones_gravado), 'vacaciones_dignas_gravado': safe_decimal(nom.vacaciones_dignas_gravado), 'aguinaldo_gravado': safe_decimal(nom.aguinaldo_gravado),
        }
        return JsonResponse({'success': True, 'data': data})
    except Nomina.DoesNotExist: return JsonResponse({'success': False, 'error': 'Registro de nómina no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': f'Error en el servidor: {str(e)}'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'crear', json_response=True)
def crear_nomina_ajax(request):
    empresa_actual = get_empresa_actual(request)
    try:
        data = request.POST; sucursal_id = request.session.get('sucursal_id'); empleado_id = data.get('empleado')
        empleado = Empleado.objects.get(id=empleado_id, empresa=empresa_actual) if empleado_id else None
        nueva_nom = Nomina(
            empresa=empresa_actual, sucursal_id=sucursal_id, empleado=empleado, periodo=data.get('periodo'), uso_cfdi=data.get('uso_cfdi', 'CN01'), uuid=data.get('uuid'), tipo_nomina=data.get('tipo_nomina', 'O'), serie=data.get('serie'), folio=data.get('folio'), fecha_emision=data.get('fecha_emision') or None, fecha_certificacion=data.get('fecha_certificacion') or None, fecha_pago=data.get('fecha_pago') or None, fecha_inicial_pago=data.get('fecha_inicial_pago') or None, fecha_final_pago=data.get('fecha_final_pago') or None, dias_pagados=Decimal(data.get('dias_pagados', '0')), rfc=data.get('rfc', '').upper(), curp=data.get('curp', '').upper(), nss=data.get('nss', ''), nombre=data.get('nombre', ''), rfc_contratista=data.get('rfc_contratista', '').upper(), sdi=Decimal(data.get('sdi', '0')), sbc=Decimal(data.get('sbc', '0')), vacaciones_exento=Decimal(data.get('vacaciones_exento', '0')), vacaciones_dignas_exento=Decimal(data.get('vacaciones_dignas_exento', '0')), aguinaldo_exento=Decimal(data.get('aguinaldo_exento', '0')), sueldo_gravado=Decimal(data.get('sueldo_gravado', '0')), vacaciones_gravado=Decimal(data.get('vacaciones_gravado', '0')), vacaciones_dignas_gravado=Decimal(data.get('vacaciones_dignas_gravado', '0')), aguinaldo_gravado=Decimal(data.get('aguinaldo_gravado', '0')),
        )
        nueva_nom.save(); return JsonResponse({'success': True, 'message': 'Nómina registrada correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'editar', json_response=True)
def editar_nomina_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        nom = Nomina.objects.get(id=id, empresa=empresa_actual); data = request.POST
        nom.empleado_id = data.get('empleado') or None; nom.periodo = data.get('periodo'); nom.uso_cfdi = data.get('uso_cfdi', 'CN01'); nom.uuid = data.get('uuid'); nom.tipo_nomina = data.get('tipo_nomina'); nom.serie = data.get('serie'); nom.folio = data.get('folio'); nom.fecha_emision = data.get('fecha_emision') or None; nom.fecha_certificacion = data.get('fecha_certificacion') or None; nom.fecha_pago = data.get('fecha_pago') or None; nom.fecha_inicial_pago = data.get('fecha_inicial_pago') or None; nom.fecha_final_pago = data.get('fecha_final_pago') or None; nom.dias_pagados = Decimal(data.get('dias_pagados', '0')); nom.rfc = data.get('rfc', '').upper(); nom.curp = data.get('curp', '').upper(); nom.nss = data.get('nss', ''); nom.nombre = data.get('nombre', ''); nom.rfc_contratista = data.get('rfc_contratista', '').upper(); nom.sdi = Decimal(data.get('sdi', '0')); nom.sbc = Decimal(data.get('sbc', '0')); nom.vacaciones_exento = Decimal(data.get('vacaciones_exento', '0')); nom.vacaciones_dignas_exento = Decimal(data.get('vacaciones_dignas_exento', '0')); nom.aguinaldo_exento = Decimal(data.get('aguinaldo_exento', '0')); nom.sueldo_gravado = Decimal(data.get('sueldo_gravado', '0')); nom.vacaciones_gravado = Decimal(data.get('vacaciones_gravado', '0')); nom.vacaciones_dignas_gravado = Decimal(data.get('vacaciones_dignas_gravado', '0')); nom.aguinaldo_gravado = Decimal(data.get('aguinaldo_gravado', '0'))
        nom.save(); return JsonResponse({'success': True, 'message': 'Nómina actualizada correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'eliminar', json_response=True)
def eliminar_nomina_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        nom = Nomina.objects.get(id=id, empresa=empresa_actual); nom.delete()
        return JsonResponse({'success': True, 'message': 'Registro de nómina eliminado correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'crear', json_response=True)
def importar_nomina_ajax(request):
    empresa_actual = get_empresa_actual(request)
    archivo = request.FILES.get('archivo')
    if not archivo: return JsonResponse({'success': False, 'error': 'No se proporcionó ningún archivo.'})
    try:
        wb = openpyxl.load_workbook(archivo, data_only=True); sheet = wb.active
        headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]; col_map = {h: i for i, h in enumerate(headers) if h}
        def get_val(row, header, default=None): idx = col_map.get(header); return row[idx].value if idx is not None and row[idx].value is not None else default
        def to_decimal(val):
            try: v = str(val or 0).replace(',', '').replace('$', '').strip(); return Decimal(v) if v else Decimal('0')
            except: return Decimal('0')
        def to_date(val):
            if isinstance(val, datetime): return val.date()
            if isinstance(val, str):
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try: return datetime.strptime(val, fmt).date()
                    except: pass
            return None
        def to_datetime(val):
            if isinstance(val, datetime): return val
            if isinstance(val, str):
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M'):
                    try: return datetime.strptime(val, fmt)
                    except: pass
            return None

        sucursal_id = request.session.get('sucursal_id'); count = 0
        for row in sheet.iter_rows(min_row=2):
            curp_file = str(get_val(row, 'CURP', '')).strip().upper(); nss_file = str(get_val(row, 'No Seguro social', '')).strip()
            if not curp_file or not nss_file: continue
            empleado = Empleado.objects.filter(empresa=empresa_actual, curp=curp_file, nss=nss_file).first()
            if empleado:
                empleado.rfc = str(get_val(row, 'RFC receptor', empleado.rfc)).strip().upper()
                empleado.cp = str(get_val(row, 'Domicilio receptor', empleado.cp)).strip()
                fecha_ing = to_date(get_val(row, 'Fecha inicio relacion laboral'))
                if fecha_ing: empleado.fecha_ingreso = fecha_ing
                empleado.jornada_sat = str(get_val(row, 'Tipo jornada', empleado.jornada_sat or '')).strip()
                empleado.tipo_regimen_sat = str(get_val(row, 'Tipo regimen', empleado.tipo_regimen_sat or '')).strip()
                empleado.num_empleado = str(get_val(row, 'Num empleado', empleado.num_empleado)).strip()
                empleado.antiguedad_sat = str(get_val(row, 'Antiguedad', empleado.antiguedad_sat or '')).strip()
                empleado.puesto = str(get_val(row, 'Puesto', empleado.puesto)).strip()
                empleado.periodicidad_pago_sat = str(get_val(row, 'Periodicidad pago', empleado.periodicidad_pago_sat or '')).strip()
                sbc_val = to_decimal(get_val(row, 'Salario base cot apor'))
                if sbc_val > 0: empleado.sbc = sbc_val
                empleado.save()

            tipo_nom_raw = str(get_val(row, 'Tipo nomina', 'O')).strip().upper()
            tipo_nom = 'E' if 'EXTRAORDINARIA' in tipo_nom_raw or tipo_nom_raw == 'E' else 'O'
            nueva_nom = Nomina(
                empresa=empresa_actual, sucursal_id=sucursal_id, empleado=empleado, periodo=str(get_val(row, 'Periodo', '')), uso_cfdi=str(get_val(row, 'Uso CFDI', 'CN01')), uuid=str(get_val(row, 'UUID', '')), tipo_nomina=tipo_nom, serie=str(get_val(row, 'Serie', '')), folio=str(get_val(row, 'Folio', '')), fecha_emision=to_datetime(get_val(row, 'Fecha emision')), fecha_certificacion=to_datetime(get_val(row, 'Fecha certificacion')), fecha_pago=to_date(get_val(row, 'Fecha pago')), fecha_inicial_pago=to_date(get_val(row, 'Fecha inicial pago')), fecha_final_pago=to_date(get_val(row, 'Fecha final pago')), dias_pagados=to_decimal(get_val(row, 'Dias pagados')), nombre=(empleado.nombre + " " + empleado.apellido_paterno + " " + empleado.apellido_materno) if empleado else str(get_val(row, 'Razon receptor', '')), rfc=empleado.rfc if empleado else str(get_val(row, 'RFC receptor', '')), curp=empleado.curp if empleado else curp_file, nss=empleado.nss if empleado else nss_file, rfc_contratista=str(get_val(row, 'RFC emisor', '')), sdi=empleado.sdi if empleado else to_decimal(get_val(row, 'Salario diario integrado')), sbc=empleado.sbc if empleado else to_decimal(get_val(row, 'Salario base cot apor')), vacaciones_exento=to_decimal(get_val(row, '001/P009/Exento/VACACIONES')), vacaciones_dignas_exento=to_decimal(get_val(row, '001/P009/Exento/VACACIONES DIGNAS')), aguinaldo_exento=to_decimal(get_val(row, '002/P004/Exento/AGUINALDO')), sueldo_gravado=to_decimal(get_val(row, '001/P001/Gravado/SUELDO')), vacaciones_gravado=to_decimal(get_val(row, '001/P009/Gravado/VACACIONES')), vacaciones_dignas_gravado=to_decimal(get_val(row, '001/P009/Gravado/VACACIONES DIGNAS')), aguinaldo_gravado=to_decimal(get_val(row, '002/P004/Gravado/AGUINALDO')),
            )
            nueva_nom.save(); count += 1
        return JsonResponse({'success': True, 'message': f'Se importaron {count} registros correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': f'Error al procesar el archivo: {str(e)}'})

@login_required(login_url='/login/')
def exportar_sisub_trabajadores(request, id):
    empresa_actual = get_empresa_actual(request)
    contratista = get_object_or_404(Contratista, id=id, empresa=empresa_actual)
    cuat = int(request.GET.get('cuatrimestre', 1)); anio = int(request.GET.get('anio', datetime.now().year))
    
    # Cuatrimestres SISUB: 1(Ene-Abr), 2(May-Ago), 3(Sep-Dic)
    meses_filtro = {1: [1, 2, 3, 4], 2: [5, 6, 7, 8], 3: [9, 10, 11, 12]}.get(cuat, [1, 2, 3, 4])
    
    # Limpiamos el RFC del contratista para una comparación robusta
    rfc_cont_clean = re.sub(r'[^A-Z0-9]', '', contratista.rfc.upper()).strip()

    # Buscamos nóminas que coincidan con el contratista por objeto o por RFC emisor (limpio)
    nominas_qs = Nomina.objects.filter(
        empresa=empresa_actual, 
        fecha_pago__year=anio, 
        fecha_pago__month__in=meses_filtro
    ).filter(
        Q(empleado__contratista=contratista) | 
        Q(rfc_contratista__icontains=rfc_cont_clean) |
        Q(rfc_contratista__icontains=contratista.rfc.strip())
    ).select_related('empleado', 'empleado__contratista')

    from ..models import ImportacionSUA, TrabajadorSUA
    incapacidades = {}
    
    # Mapeo de meses para búsqueda en SUA
    nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    for mes in meses_filtro:
        nombre_mes = nombres_meses[mes]
        # Búsqueda más flexible del periodo (ej: "ABRIL 2026")
        sua_reg = ImportacionSUA.objects.filter(
            empresa=empresa_actual, 
            periodo__icontains=nombre_mes.upper()
        ).filter(
            periodo__icontains=str(anio)
        ).first()
        
        if sua_reg:
            # Bimestre: 1(Ene-Feb), 2(Mar-Abr), 3(May-Jun), 4(Jul-Ago), 5(Sep-Oct), 6(Nov-Dic)
            bimestre_actual = (mes + 1) // 2
            for ts in TrabajadorSUA.objects.filter(importacion=sua_reg):
                nss_key = re.sub(r'[^0-9]', '', ts.nss) if ts.nss else ""
                if nss_key:
                    try: inc_val = int(float(ts.inc or 0))
                    except: inc_val = 0
                    k = (nss_key, bimestre_actual)
                    incapacidades[k] = incapacidades.get(k, 0) + inc_val

    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Trabajadores SISUB"
    fill_brand = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
    fill_gray_dark = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    fill_gray_light = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    border = Border(left=Side(style='thin', color="B2B2B2"), right=Side(style='thin', color="B2B2B2"), top=Side(style='thin', color="B2B2B2"), bottom=Side(style='thin', color="B2B2B2"))
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.merge_cells('A1:N1'); ws['A1'] = "d-Informacion de los trabajadores"; ws.merge_cells('O1:S1'); ws['O1'] = "e-Determinacion del salario base de aportacion"
    for c in range(1, 20): cell = ws.cell(row=1, column=c); cell.fill = fill_brand; cell.font = Font(bold=True, color="FFFFFF"); cell.alignment = center_align; cell.border = border

    ws.merge_cells('A2:C2'); ws['A2'] = "Periodo"; ws.merge_cells('D2:N2'); ws['D2'] = "a-Identificacion"; ws.merge_cells('O2:S2'); ws['O2'] = "a-Percepciones por bimestre 1"
    for c in range(1, 20): cell = ws.cell(row=2, column=c); cell.fill = fill_gray_dark; cell.font = Font(bold=True); cell.alignment = center_align; cell.border = border

    headers = ["cuatrimestre que declara", "anio que se declara", "bimestre", "Registro Federal de Contribuyente del sujeto obligado", "Numero de contrato", "Registro Patronal ante el IMSS", "Numero de Seguro Social del trabajador", "Calle (centro del trabajo)", "Numero exterior (centro del trabajo)", "Numero interior (centro de trabajo)", "Colonia (centro de trabajo)", "Codigo Postal (centro de trabajo)", "Municipio o Alcaldia (centro de trabajo)", "Entidad federativa (centro de trabajo)", "Monto Percepciones variables", "Monto Percepciones fijas", "Dias de Incapacidad", "Percepciones no integrables al SBA", "salario no excedente (VSM)"]
    for col_num, header in enumerate(headers, 1): cell = ws.cell(row=3, column=col_num); cell.value = header; cell.font = Font(bold=True); cell.fill = fill_gray_light; cell.alignment = center_align; cell.border = border

    data_procesada = {}
    for nom in nominas_qs:
        bimestre_nom = (nom.fecha_pago.month + 1) // 2
        nss_clean = re.sub(r'[^0-9]', '', nom.nss) if nom.nss else f"REF-{nom.id}"
        key = (nss_clean, bimestre_nom)
        
        if key not in data_procesada:
            # Buscar contrato vinculado a este empleado y contratista
            contrato = Contrato.objects.filter(empleados=nom.empleado, contratista=contratista, estado='vigente').first() if nom.empleado else None
            data_procesada[key] = {
                'nss': nss_clean, 
                'sdi': nom.sdi, 
                'bimestre': bimestre_nom, 
                'percepciones_fijas': Decimal('0'), 
                'contrato_folio': contrato.folio if (contrato and contrato.folio) else "SIN FOLIO", 
                'beneficiario': contrato.beneficiario if contrato else (nom.empleado.beneficiario if nom.empleado else None)
            }
        
        # Sumar todas las percepciones registradas en la nómina
        percepciones = (
            (nom.vacaciones_exento or 0) + (nom.vacaciones_dignas_exento or 0) + 
            (nom.aguinaldo_exento or 0) + (nom.sueldo_gravado or 0) + 
            (nom.vacaciones_gravado or 0) + (nom.vacaciones_dignas_gravado or 0) + 
            (nom.aguinaldo_gravado or 0)
        )
        data_procesada[key]['percepciones_fijas'] += percepciones

    row_num = 4
    for k in sorted(data_procesada.keys(), key=lambda x: (x[1], x[0])):
        data = data_procesada[k]; b = data['beneficiario']
        ws.cell(row=row_num, column=1).value = cuat
        ws.cell(row=row_num, column=2).value = anio
        ws.cell(row=row_num, column=3).value = data['bimestre']
        ws.cell(row=row_num, column=4).value = contratista.rfc
        ws.cell(row=row_num, column=5).value = data['contrato_folio']
        ws.cell(row=row_num, column=6).value = contratista.registro_patronal
        ws.cell(row=row_num, column=7).value = data['nss']
        
        if b:
            ws.cell(row=row_num, column=8).value = b.calle
            ws.cell(row=row_num, column=9).value = b.num_ext
            ws.cell(row=row_num, column=10).value = b.num_int
            ws.cell(row=row_num, column=11).value = b.colonia
            ws.cell(row=row_num, column=12).value = b.cp
            ws.cell(row=row_num, column=13).value = b.municipio_alcaldia
            ws.cell(row=row_num, column=14).value = b.entidad_federativa
        
        ws.cell(row=row_num, column=15).value = 0
        ws.cell(row=row_num, column=16).value = math.ceil(float(data['percepciones_fijas']))
        ws.cell(row=row_num, column=17).value = incapacidades.get((data['nss'], data['bimestre']), 0)
        ws.cell(row=row_num, column=18).value = 0
        ws.cell(row=row_num, column=19).value = float(data['sdi'] or 0)
        ws.cell(row=row_num, column=19).number_format = '#,##0.00'
        
        for c in range(1, 20): ws.cell(row=row_num, column=c).border = border
        row_num += 1

    from openpyxl.utils import get_column_letter
    for i in range(1, 20): ws.column_dimensions[get_column_letter(i)].width = 22
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="SISUB_TRABAJADORES_{contratista.rfc}_{anio}_C{cuat}.xlsx"'
    wb.save(response)
    return response
