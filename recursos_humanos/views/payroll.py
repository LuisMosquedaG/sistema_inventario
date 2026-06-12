from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q
from decimal import Decimal, ROUND_HALF_UP
import openpyxl
import math
import re
from datetime import datetime, date

from ..models import Empleado, Contrato, Contratista, Nomina, Beneficiario, ImportacionSUA, TrabajadorSUA
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
    q = request.GET.get('q', '').strip()
    f_folio = request.GET.get('folio', '').strip()
    f_uuid = request.GET.get('uuid', '').strip()
    f_colaborador = request.GET.get('colaborador', '').strip()
    f_rfc_contratista = request.GET.get('rfc_contratista', '').strip()
    f_fecha_pago = request.GET.get('fecha_pago', '').strip()
    f_sucursal = request.GET.get('sucursal', '').strip()

    if q:
        nominas = nominas.filter(
            Q(nombre__icontains=q) |
            Q(rfc__icontains=q) |
            Q(curp__icontains=q) |
            Q(nss__icontains=q) |
            Q(folio__icontains=q) |
            Q(uuid__icontains=q) |
            Q(rfc_contratista__icontains=q)
        ).distinct()
    
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

    # Re-ordenar para asegurar consistencia después de los filtros
    nominas = nominas.order_by('-fecha_pago', 'nombre')

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
@require_POST
def actualizar_datos_trabajadores_nomina_ajax(request):
    empresa_actual = get_empresa_actual(request)
    try:
        # 1. Mapear empleados por RFC para búsqueda rápida
        # Limpiamos el RFC de espacios y guiones
        empleados_qs = Empleado.objects.filter(empresa=empresa_actual)
        empleados_map = {re.sub(r'[^A-Z0-9]', '', (e.rfc or '').upper()): e for e in empleados_qs if e.rfc}

        # 2. Obtener todas las nóminas de la empresa
        nominas = Nomina.objects.filter(empresa=empresa_actual)
        
        actualizados = 0
        for nom in nominas:
            rfc_nom = re.sub(r'[^A-Z0-9]', '', (nom.rfc or '').upper())
            empleado = empleados_map.get(rfc_nom)
            
            if empleado:
                # Solo actualizamos si los campos están vacíos o el SDI es distinto de 0
                changed = False
                if not nom.nss and empleado.nss: nom.nss = empleado.nss; changed = True
                if not nom.curp and empleado.curp: nom.curp = empleado.curp; changed = True
                if (not nom.sdi or nom.sdi == 0) and empleado.sdi: nom.sdi = empleado.sdi; changed = True
                if (not nom.sbc or nom.sbc == 0) and empleado.sbc: nom.sbc = empleado.sbc; changed = True
                if not nom.empleado: nom.empleado = empleado; changed = True
                
                if changed:
                    nom.save(); actualizados += 1
        
        return JsonResponse({'success': True, 'message': f'Proceso completado. Se actualizaron los datos de {actualizados} recibos de nómina.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
def exportar_nominas_excel(request):
    empresa_actual = get_empresa_actual(request)
    nominas = Nomina.objects.filter(empresa=empresa_actual).select_related('empleado', 'sucursal')

    # Replicar Filtros
    q = request.GET.get('q', '').strip()
    f_folio = request.GET.get('folio', '').strip()
    f_uuid = request.GET.get('uuid', '').strip()
    f_colaborador = request.GET.get('colaborador', '').strip()
    f_rfc_contratista = request.GET.get('rfc_contratista', '').strip()
    f_fecha_pago = request.GET.get('fecha_pago', '').strip()
    f_sucursal = request.GET.get('sucursal', '').strip()

    if q:
        nominas = nominas.filter(
            Q(nombre__icontains=q) | Q(rfc__icontains=q) | Q(curp__icontains=q) |
            Q(nss__icontains=q) | Q(folio__icontains=q) | Q(uuid__icontains=q) |
            Q(rfc_contratista__icontains=q)
        ).distinct()
    
    if f_folio: nominas = nominas.filter(folio__icontains=f_folio)
    if f_uuid: nominas = nominas.filter(uuid__icontains=f_uuid)
    if f_colaborador: nominas = nominas.filter(nombre__icontains=f_colaborador)
    if f_rfc_contratista: nominas = nominas.filter(rfc_contratista__icontains=f_rfc_contratista)
    if f_fecha_pago: nominas = nominas.filter(fecha_pago=f_fecha_pago)
    if f_sucursal: nominas = nominas.filter(sucursal_id=f_sucursal)

    nominas = nominas.order_by('-fecha_pago', 'nombre')

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Nominas"
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    
    # Estilos
    header_fill = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    headers = [
        "Folio", "Serie", "UUID", "Uso CFDI", "Tipo Nomina", "Periodo", 
        "Fecha Emision", "Fecha Certificacion", "Fecha Pago", "Fecha Inicial", "Fecha Final", 
        "Dias Pagados", "Colaborador", "RFC", "CURP", "NSS", "RFC Contratista", 
        "SDI", "SBC", "Vacaciones (Exento)", "Vacaciones Dignas (Exento)", "Aguinaldo (Exento)", 
        "Sueldo (Gravado)", "Vacaciones (Gravado)", "Vacaciones Dignas (Gravado)", "Aguinaldo (Gravado)", "Sucursal"
    ]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill; cell.font = header_font; cell.alignment = Alignment(horizontal="center"); cell.border = border

    for row_num, nom in enumerate(nominas, 2):
        data = [
            nom.folio, nom.serie, nom.uuid, nom.uso_cfdi,
            "Ordinaria" if nom.tipo_nomina == 'O' else "Extraordinaria",
            nom.periodo, nom.fecha_emision, nom.fecha_certificacion, 
            nom.fecha_pago, nom.fecha_inicial_pago, nom.fecha_final_pago,
            nom.dias_pagados, nom.nombre, nom.rfc, nom.curp, nom.nss, nom.rfc_contratista,
            nom.sdi, nom.sbc, nom.vacaciones_exento, nom.vacaciones_dignas_exento, nom.aguinaldo_exento,
            nom.sueldo_gravado, nom.vacaciones_gravado, nom.vacaciones_dignas_gravado, nom.aguinaldo_gravado,
            nom.sucursal.nombre if nom.sucursal else "General"
        ]
        for col_num, val in enumerate(data, 1):
            # Formatear fechas para Excel si es necesario
            if isinstance(val, (datetime, date)):
                cell = ws.cell(row=row_num, column=col_num, value=val)
                cell.number_format = 'yyyy-mm-dd'
            else:
                cell = ws.cell(row=row_num, column=col_num, value=str(val) if val is not None else "")
            cell.border = border

    for i in range(1, len(headers) + 1): ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 20

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Listado_Nominas.xlsx"'
    wb.save(response); return response

@login_required(login_url='/login/')
def exportar_sisub_trabajadores(request, id):
    empresa_actual = get_empresa_actual(request)
    contratista = get_object_or_404(Contratista, id=id, empresa=empresa_actual)
    cuat = int(request.GET.get('cuatrimestre', 1)); anio_val = request.GET.get('anio', '')
    if not anio_val: return HttpResponse("Año requerido", status=400)
    anio = int(anio_val)
    
    meses_filtro = {1: [1, 2, 3, 4], 2: [5, 6, 7, 8], 3: [9, 10, 11, 12]}.get(cuat, [1, 2, 3, 4])
    
    # 1. Obtener empleados vinculados a los contratos vigentes
    contratos = Contrato.objects.filter(contratista=contratista, empresa=empresa_actual, estado='vigente').prefetch_related('empleados', 'beneficiario')
    
    emp_map = {} # nss -> c, curp -> c, name -> c
    for c in contratos:
        for e in c.empleados.all():
            n_clean = re.sub(r'[^0-9]', '', e.nss) if e.nss else ""
            c_clean = re.sub(r'[^A-Z0-9]', '', (e.curp or '').upper())
            name = f"{e.nombre} {e.apellido_paterno} {e.apellido_materno}".strip().upper()
            
            if n_clean: emp_map[n_clean] = c
            if c_clean: emp_map[c_clean] = c
            if name: emp_map[name] = c

    # 2. Buscar TODOS los recibos de nómina en el periodo
    recibos_total = Nomina.objects.filter(
        empresa=empresa_actual,
        fecha_pago__year=anio,
        fecha_pago__month__in=meses_filtro
    ).order_by('fecha_pago')

    recibos_filtrados = []
    for r in recibos_total:
        n_nom = re.sub(r'[^0-9]', '', r.nss) if r.nss else ""
        c_nom = re.sub(r'[^A-Z0-9]', '', (r.curp or '').upper())
        name_nom = (r.nombre or "").strip().upper()
        
        # Estrategia de Match Triple (NSS, CURP, NOMBRE)
        con_match = emp_map.get(n_nom) or emp_map.get(c_nom) or emp_map.get(name_nom)
        
        if con_match:
            recibos_filtrados.append((r, con_match))

    # 3. Obtener información de SUA (Bimestral)
    from ..models import ImportacionSUA, TrabajadorSUA
    sua_data = {}
    nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    for mes in meses_filtro:
        sua_regs = ImportacionSUA.objects.filter(empresa=empresa_actual, periodo__icontains=nombres_meses[mes].upper()).filter(periodo__icontains=str(anio))
        for sr in sua_regs:
            bim = (mes + 1) // 2
            for ts in sr.trabajadores.all():
                ts_nss = re.sub(r'[^0-9]', '', ts.nss) if ts.nss else ""
                ts_curp = re.sub(r'[^A-Z0-9]', '', (ts.rfc_curp or '').upper())
                ts_name = (ts.nombre or "").strip().upper()
                
                val = {'sdi': ts.sdi, 'inc': 0}
                try: val['inc'] = int(float(ts.incapacidades or 0))
                except: pass
                
                if ts_nss: sua_data[(ts_nss, bim)] = val
                if ts_curp: sua_data[(ts_curp, bim)] = val
                if ts_name: sua_data[(ts_name, bim)] = val

    # 4. Generar el Excel
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Trabajadores SISUB"
    fill_brand = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
    fill_gray_dark = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    fill_gray_light = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    border = Border(left=Side(style='thin', color="B2B2B2"), right=Side(style='thin', color="B2B2B2"), top=Side(style='thin', color="B2B2B2"), bottom=Side(style='thin', color="B2B2B2"))
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.merge_cells('A1:N1'); ws['A1'] = "d-Informacion de los trabajadores"; ws.merge_cells('O1:S1'); ws['O1'] = "e-Determinacion del salario base de aportacion"
    for c in range(1, 20): cell = ws.cell(row=1, column=c); cell.fill = fill_brand; cell.font = Font(bold=True, color="FFFFFF"); cell.alignment = center_align; cell.border = border
    ws.merge_cells('A2:C2'); ws['A2'] = "Periodo"; ws.merge_cells('D2:N2'); ws['D2'] = "a-Identificacion"; ws.merge_cells('O2:S2'); ws['O2'] = "a-Percepciones por bimestre"
    for c in range(1, 20): cell = ws.cell(row=2, column=c); cell.fill = fill_gray_dark; cell.font = Font(bold=True); cell.alignment = center_align; cell.border = border

    headers = ["cuatrimestre que declara", "anio que se declara", "bimestre", "Registro Federal de Contribuyente del sujeto obligado", "Numero de contrato", "Registro Patronal ante el IMSS", "Numero de Seguro Social del trabajador", "Calle (centro del trabajo)", "Numero exterior (centro del trabajo)", "Numero interior (centro de trabajo)", "Colonia (centro de trabajo)", "Codigo Postal (centro de trabajo)", "Municipio o Alcaldia (centro de trabajo)", "Entidad federativa (centro de trabajo)", "Monto Percepciones variables", "Monto Percepciones fijas", "Dias de Incapacidad", "Percepciones no integrables al SBA", "salario no excedente (VSM)"]
    for i, h in enumerate(headers, 1): cell = ws.cell(row=3, column=i); cell.value = h; cell.font = Font(bold=True); cell.fill = fill_gray_light; cell.alignment = center_align; cell.border = border

    row_num = 4
    for r, con in recibos_filtrados:
        n_nom = re.sub(r'[^0-9]', '', r.nss) if r.nss else ""
        c_nom = re.sub(r'[^A-Z0-9]', '', (r.curp or '').upper())
        name_nom = (r.nombre or "").strip().upper()
        
        ben = con.beneficiario
        bim = (r.fecha_pago.month + 1) // 2
        
        ws.cell(row=row_num, column=1).value = cuat
        ws.cell(row=row_num, column=2).value = anio
        ws.cell(row=row_num, column=3).value = bim
        ws.cell(row=row_num, column=4).value = contratista.rfc
        ws.cell(row=row_num, column=5).value = con.folio or "SIN FOLIO"
        ws.cell(row=row_num, column=6).value = contratista.registro_patronal
        ws.cell(row=row_num, column=7).value = n_nom or r.nss
        
        if ben:
            ws.cell(row=row_num, column=8).value = ben.calle
            ws.cell(row=row_num, column=9).value = ben.num_ext
            ws.cell(row=row_num, column=10).value = ben.num_int
            ws.cell(row=row_num, column=11).value = ben.colonia
            ws.cell(row=row_num, column=12).value = ben.cp
            ws.cell(row=row_num, column=13).value = ben.municipio_alcaldia
            ws.cell(row=row_num, column=14).value = ben.entidad_federativa
        
        ws.cell(row=row_num, column=15).value = 0
        per_sum = (r.vacaciones_exento or 0) + (r.vacaciones_dignas_exento or 0) + (r.aguinaldo_exento or 0) + (r.sueldo_gravado or 0) + (r.vacaciones_gravado or 0) + (r.vacaciones_dignas_gravado or 0) + (r.aguinaldo_gravado or 0)
        ws.cell(row=row_num, column=16).value = int(Decimal(per_sum).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        
        # Match SUA por NSS, CURP o NOMBRE
        s_info = sua_data.get((n_nom, bim)) or sua_data.get((c_nom, bim)) or sua_data.get((name_nom, bim)) or {'sdi': Decimal('0.00'), 'inc': 0}
        ws.cell(row=row_num, column=17).value = s_info['inc']
        ws.cell(row=row_num, column=18).value = 0
        # Column S: Salario (SDI de la cédula SUA) sin redondeo, exacto como en la base
        # Usamos Decimal para mantener la precisión original de la cédula
        ws.cell(row=row_num, column=19).value = s_info['sdi']
        ws.cell(row=row_num, column=19).number_format = '#,##0.00'
        
        for c_idx in range(1, 20): ws.cell(row=row_num, column=c_idx).border = border
        row_num += 1

    for i in range(1, 20): ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 22
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="SISUB_TRABAJADORES_{contratista.rfc}_{anio}_C{cuat}.xlsx"'
    wb.save(response)
    return response