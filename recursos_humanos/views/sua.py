from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
import re
import csv
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from ..models import Empleado, Contrato, Contratista, Beneficiario, ImportacionSUA, TrabajadorSUA
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual, limpiar_basura_header

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
    
    # PAGINACIÓN
    paginator = Paginator(importaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'recursos_humanos/lista_sua.html', {
        'page_obj': page_obj, 
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

        periodo_final = limpiar_basura_header(periodo_val).strip()
        razon_final = nom_razon_val.strip()
        reg_pat_final = reg_pat_val.strip()
        
        if ImportacionSUA.objects.filter(
            empresa=empresa_actual, periodo=periodo_final,
            nombre_razon_social=razon_final, registro_patronal=reg_pat_final,
            tipo=tipo_importacion
        ).exists():
            return JsonResponse({'success': False, 'error': f'Error: Esta cédula ya fue registrada (Periodo: {periodo_final}, Empresa: {razon_final}, Tipo: {tipo_importacion.upper()}).'})

        total_reporte = 0
        m_total_rep = re.search(r'Total\s+de\s+cotizaciones:\s*(\d+)', full_text, re.I)
        if m_total_rep: total_reporte = int(m_total_rep.group(1))

        sucursal_id = request.session.get('sucursal_id')
        created_count = 0; nss_encontrados = set()

        with transaction.atomic():
            importacion = ImportacionSUA.objects.create(
                empresa=empresa_actual, sucursal_id=sucursal_id,
                registro_patronal=reg_pat_val, rfc_empresa=rfc_emp_val,
                nombre_razon_social=nom_razon_val, actividad=limpiar_basura_header(actividad_val),
                domicilio=limpiar_basura_header(domicilio_val), cp=limpiar_basura_header(cp_val),
                entidad=limpiar_basura_header(entidad_val), area_geografica=limpiar_basura_header(area_val),
                delegacion_imss=limpiar_basura_header(deleg_val), subdelegacion_imss=limpiar_basura_header(subdeleg_val),
                municipio_alcaldia=limpiar_basura_header(mun_alc_val), prima_rt=prima_val,
                periodo=periodo_final, tipo=tipo_importacion
            )

            current_worker_info = None; stop_workers = False
            for line in text_lines:
                l_clean = line.strip()
                if not l_clean: continue
                if "TOTAL DE COTIZACIONES" in l_clean.upper() or "TOTALES" in l_clean.upper() or re.search(r'([_-]\s?){15,}', l_clean):
                    current_worker_info = None; stop_workers = True; continue
                if stop_workers: continue

                nss_match = re.search(r'(\d{2}-?\d{2}-?\d{2}-?\d{4}-?\d)', l_clean)
                if nss_match:
                    nss_val = nss_match.group(1); current_worker_info = None 
                    remainder = l_clean.split(nss_val)[-1].strip()
                    m_rfc = re.search(r'([A-Z]{3,4}[0-9]{6}[A-Z0-9]{0,9})', remainder)
                    
                    if m_rfc:
                        rfc = m_rfc.group(1); nombre = remainder[:m_rfc.start()].strip()
                        post_rfc = remainder[m_rfc.end():].strip()
                        m_data_start = re.search(r'(\d{1,2})\s+([\d\.,]+)', post_rfc)
                        if m_data_start:
                            ubic = post_rfc[:m_data_start.start()].strip() or "-"; l_clean = post_rfc[m_data_start.start():].strip()
                        else:
                            ubic = post_rfc or "-"; l_clean = ""
                        if nombre and rfc:
                            current_worker_info = {'nss': nss_val, 'nombre': nombre, 'rfc': rfc, 'clave_u': ubic}
                            nss_encontrados.add(nss_val)
                    else:
                        parts = [p.strip() for p in re.split(r'\s+', remainder) if p.strip()]
                        if len(parts) >= 2:
                            nombre = parts[0]; rfc = parts[1]; ubic = " ".join(parts[2:]) if len(parts) > 2 else "-"
                            current_worker_info = {'nss': nss_val, 'nombre': nombre, 'rfc': rfc, 'clave_u': ubic}
                            nss_encontrados.add(nss_val); l_clean = ""
                    if not l_clean: continue

                if current_worker_info:
                    m_header = re.match(r'^([^0-9\s,]{2,})?\s*(\d{2}/\d{2}/\d{4})?\s*(.*)', l_clean, re.I)
                    clave_mov = m_header.group(1).strip().rstrip(',') if m_header and m_header.group(1) else '-'
                    fecha_mov = m_header.group(2) or '' if m_header else ''; resto_linea = m_header.group(3).strip() if m_header else l_clean
                    raw_tokens = re.findall(r'\d{2}/\d{2}/\d{4}|(?:FD|\$|%)\s*[\d\.,]+%?|[A-Z]{3}|[\d\.,]+%?|FD|%|\$', resto_linea)
                    raw_tokens = [t.strip() for t in raw_tokens if t.strip()]
                    
                    def merge_tokens_sua(items):
                        res = []; skip = False
                        for i in range(len(items)):
                            if skip: skip = False; continue
                            token = items[i]
                            if token in ['FD', '$', '%'] and (i + 1) < len(items):
                                next_t = items[i+1]
                                if re.match(r'^[\d\.,]+', next_t): res.append(f"{token} {next_t}"); skip = True; continue
                            res.append(token)
                        return res

                    tokens = merge_tokens_sua(raw_tokens); tokens_clean = [t.replace(',', '') for t in tokens]
                    
                    def clean_dec(val):
                        if not val or val == '-': return Decimal('0')
                        c = re.sub(r'[^\d.]', '', str(val)); return Decimal(c) if c else Decimal('0')

                    try:
                        num_idx = 0
                        if tokens_clean[num_idx] == 'FD': num_idx += 1
                        dias_val = int(float(clean_dec(tokens_clean[num_idx])))
                        tiene_sdi = len(tokens_clean) > (num_idx + 1) and re.match(r'^[^\d]*[\d\.]+[^\d]*$', tokens_clean[num_idx+1]) and float(clean_dec(tokens_clean[num_idx+1])) > 0
                        es_movimiento_datos = (dias_val <= 99 and tiene_sdi)
                        if es_movimiento_datos:
                            tokens = tokens[num_idx:]; tokens_clean = tokens_clean[num_idx:]
                    except: es_movimiento_datos = False

                    if (clave_mov.lower() in ['baja', 'reingreso', 'modificación', 'alta'] and fecha_mov != "") or es_movimiento_datos:
                        trabajador_data = {'importacion': importacion, 'nss': current_worker_info['nss'], 'nombre': current_worker_info['nombre'], 'rfc_curp': current_worker_info['rfc'], 'clave_ubicacion': current_worker_info['clave_u'], 'clave_mov': clave_mov, 'fecha_mov': fecha_mov, 'dias': 0, 'sdi': 0, 'licencias': 0, 'incapacidades': 0, 'ausentismos': 0, 'total_general': 0}
                        if es_movimiento_datos:
                            try:
                                trabajador_data.update({'dias': int(float(clean_dec(tokens_clean[0]))), 'sdi': clean_dec(tokens_clean[1]), 'licencias': int(float(clean_dec(tokens_clean[2]))), 'incapacidades': int(float(clean_dec(tokens_clean[3]))), 'ausentismos': int(float(clean_dec(tokens_clean[4])))})
                                if tipo_importacion == 'mensual':
                                    if len(tokens_clean) >= 19:
                                        trabajador_data.update({'cuota_fija': clean_dec(tokens_clean[5]), 'excedente_patronal': clean_dec(tokens_clean[6]), 'excedente_obrera': clean_dec(tokens_clean[7]), 'prestaciones_dinero_patronal': clean_dec(tokens_clean[8]), 'prestaciones_dinero_obrera': clean_dec(tokens_clean[9]), 'gastos_medicos_patronal': clean_dec(tokens_clean[10]), 'gastos_medicos_obrera': clean_dec(tokens_clean[11]), 'riesgo_trabajo_cuota': clean_dec(tokens_clean[12]), 'invalidez_vida_patronal': clean_dec(tokens_clean[13]), 'invalidez_vida_obrera': clean_dec(tokens_clean[14]), 'guarderias_ps': clean_dec(tokens_clean[15]), 'imss_patronal': clean_dec(tokens_clean[16]), 'imss_obrera': clean_dec(tokens_clean[17]), 'imss_subtotal': clean_dec(tokens_clean[18]), 'total_general': clean_dec(tokens_clean[18])})
                                else:
                                    pivot_idx = -1
                                    for idx, t in enumerate(tokens):
                                        if any(pref in t for pref in ['FD', '$', '%']) and re.search(r'\d', t): pivot_idx = idx; break
                                    if pivot_idx != -1:
                                        try:
                                            trabajador_data.update({'retiro': clean_dec(tokens_clean[pivot_idx - 5]), 'patronal': clean_dec(tokens_clean[pivot_idx - 4]), 'obrera': clean_dec(tokens_clean[pivot_idx - 3]), 'subtotal': clean_dec(tokens_clean[pivot_idx - 2])})
                                            ap_pat = clean_dec(tokens_clean[pivot_idx - 1]); amort = clean_dec(tokens_clean[pivot_idx + 1])
                                            trabajador_data.update({'aportacion_patronal': ap_pat, 'tipo_valor_infonavit': tokens[pivot_idx], 'amortizacion': amort, 'suma_infonavit': ap_pat + amort})
                                            if len(tokens) > pivot_idx + 2:
                                                for extra_idx in range(pivot_idx + 3, len(tokens)):
                                                    t_extra = tokens[extra_idx]
                                                    if re.match(r'^\d{8,11}$', t_extra): trabajador_data['cred_vivienda'] = t_extra
                                                    elif re.match(r'^[A-Z]{3}$', t_extra): trabajador_data['tipo_mov_credito'] = t_extra
                                                    elif re.match(r'^\d{2}/\d{2}/\d{4}$', t_extra): trabajador_data['fecha_mov_credito'] = t_extra
                                        except: pass
                                    else:
                                        try:
                                            if len(tokens_clean) >= 9: trabajador_data.update({'retiro': clean_dec(tokens_clean[5]), 'patronal': clean_dec(tokens_clean[6]), 'obrera': clean_dec(tokens_clean[7]), 'subtotal': clean_dec(tokens_clean[8])})
                                            if len(tokens_clean) >= 10: ap_pat = clean_dec(tokens_clean[9]); trabajador_data.update({'aportacion_patronal': ap_pat, 'suma_infonavit': ap_pat, 'amortizacion': Decimal('0'), 'tipo_valor_infonavit': '-'})
                                        except: pass
                                    trabajador_data['total_general'] = clean_dec(trabajador_data.get('subtotal', 0)) + clean_dec(trabajador_data.get('suma_infonavit', 0))
                            except: pass
                        TrabajadorSUA.objects.create(**trabajador_data); created_count += 1
                    else:
                        if not nss_match: current_worker_info = None

            if created_count == 0: raise Exception("No se detectaron trabajadores válidos.")
            unique_count = len(nss_encontrados)
            msg_val = f" Advertencia: Se detectaron {unique_count} trabajadores únicos pero el reporte indica un total de {total_reporte}." if total_reporte > 0 and unique_count != total_reporte else ""

        return JsonResponse({'success': True, 'message': f'Importación exitosa: {created_count} registros procesados.{msg_val}'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('sua', 'ver', json_response=True)
def obtener_registro_sua_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        imp = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        trabajadores = []
        totales = {'dias': 0, 'total_general': 0, 'retiro': 0, 'patronal_rcv': 0, 'obrera_rcv': 0, 'total_rcv': 0, 'ap_pat_inf': 0, 'tipo_val_inf': 0, 'amortiz': 0, 'total_inf': 0, 'cuota_fija': 0, 'exc_pat': 0, 'exc_obr': 0, 'pd_pat': 0, 'pd_obr': 0, 'gm_pat': 0, 'gm_obr': 0, 'rt': 0, 'iv_pat': 0, 'iv_obr': 0, 'gps': 0, 'imss_pat': 0, 'imss_obr': 0, 'imss_sub': 0}
        for t in imp.trabajadores.all().order_by('id'):
            t_dict = {'nss': t.nss, 'nombre': t.nombre, 'rfc': t.rfc_curp, 'clave_u': t.clave_ubicacion, 'clave_mov': t.clave_mov, 'fecha_mov': t.fecha_mov, 'dias': t.dias, 'sdi': str(t.sdi), 'lic': t.licencias, 'inc': t.incapacidades, 'aus': t.ausentismos, 'total_general': str(t.total_general)}
            if imp.tipo == 'mensual':
                t_dict.update({'cf': str(t.cuota_fija), 'exc_pat': str(t.excedente_patronal), 'exc_obr': str(t.excedente_obrera), 'pd_pat': str(t.prestaciones_dinero_patronal), 'pd_obr': str(t.prestaciones_dinero_obrera), 'gm_pat': str(t.gastos_medicos_patronal), 'gm_obr': str(t.gastos_medicos_obrera), 'rt': str(t.riesgo_trabajo_cuota), 'iv_pat': str(t.invalidez_vida_patronal), 'iv_obr': str(t.invalidez_vida_obrera), 'gps': str(t.guarderias_ps), 'imss_pat': str(t.imss_patronal), 'imss_obr': str(t.imss_obrera), 'imss_sub': str(t.imss_subtotal)})
                totales['cuota_fija'] += float(t.cuota_fija); totales['exc_pat'] += float(t.excedente_patronal); totales['exc_obr'] += float(t.excedente_obrera); totales['pd_pat'] += float(t.prestaciones_dinero_patronal); totales['pd_obr'] += float(t.prestaciones_dinero_obrera); totales['gm_pat'] += float(t.gastos_medicos_patronal); totales['gm_obr'] += float(t.gastos_medicos_obrera); totales['rt'] += float(t.riesgo_trabajo_cuota); totales['iv_pat'] += float(t.invalidez_vida_patronal); totales['iv_obr'] += float(t.invalidez_vida_obrera); totales['gps'] += float(t.guarderias_ps); totales['imss_pat'] += float(t.imss_patronal); totales['imss_obr'] += float(t.imss_obrera); totales['imss_sub'] += float(t.imss_subtotal)
            else:
                t_dict.update({'retiro': str(t.retiro), 'patronal_rcv': str(t.patronal), 'obrera_rcv': str(t.obrera), 'total_rcv': str(t.subtotal), 'ap_pat_inf': str(t.aportacion_patronal), 'tipo_val_inf': t.tipo_valor_infonavit or '-', 'amortiz': str(t.amortizacion), 'total_inf': str(t.suma_infonavit), 'cred_viv': t.cred_vivienda or '', 'tipo_mov_cred': t.tipo_mov_credito or '', 'fecha_mov_cred': t.fecha_mov_credito or ''})
                totales['retiro'] += float(t.retiro); totales['patronal_rcv'] += float(t.patronal); totales['obrera_rcv'] += float(t.obrera); totales['total_rcv'] += float(t.subtotal); totales['ap_pat_inf'] += float(t.aportacion_patronal); totales['amortiz'] += float(t.amortizacion); totales['total_inf'] += float(t.suma_infonavit)
                if t.tipo_valor_infonavit and t.tipo_valor_infonavit != '-':
                    v_l = re.sub(r'[^\d.]', '', t.tipo_valor_infonavit)
                    if v_l: totales['tipo_val_inf'] += float(v_l)
            totales['dias'] += t.dias; totales['total_general'] += float(t.total_general); trabajadores.append(t_dict)
        for k in totales: totales[k] = int(totales[k]) if k == 'dias' else "{:,.2f}".format(totales[k])
        data = {'empresa': {'razon_social': imp.nombre_razon_social, 'rfc': imp.rfc_empresa, 'reg_patronal': imp.registro_patronal, 'actividad': limpiar_basura_header(imp.actividad), 'domicilio': limpiar_basura_header(imp.domicilio), 'cp': limpiar_basura_header(imp.cp), 'entidad': limpiar_basura_header(imp.entidad), 'periodo': limpiar_basura_header(imp.periodo), 'tipo': imp.get_tipo_display(), 'tipo_raw': imp.tipo}, 'trabajadores': trabajadores, 'totales': totales}
        return JsonResponse({'success': True, 'data': data})
    except ImportacionSUA.DoesNotExist: return JsonResponse({'success': False, 'error': 'No se encontró la importación.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('sua', 'eliminar', json_response=True)
def eliminar_sua_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        imp = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        imp.delete(); return JsonResponse({'success': True, 'message': 'Registro eliminado correctamente.'})
    except ImportacionSUA.DoesNotExist: return JsonResponse({'success': False, 'error': 'No se encontró la importación.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_hr_permission('sua', 'ver')
def exportar_sua_excel(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        imp = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="SUA_{imp.periodo}_{imp.registro_patronal}.csv"'
        response.write(u'\ufeff'.encode('utf8')); writer = csv.writer(response)
        writer.writerow(['REPORTE DE INTEGRACIÓN SUA']); writer.writerow(['Empresa', imp.nombre_razon_social]); writer.writerow(['Registro Patronal', imp.registro_patronal]); writer.writerow(['Periodo', imp.periodo]); writer.writerow(['Tipo', imp.get_tipo_display()]); writer.writerow([])
        if imp.tipo == 'mensual': headers = ['NSS', 'Nombre', 'RFC/CURP', 'Ubicación', 'Movimiento', 'Fecha Mov.', 'Días', 'SDI', 'Lic.', 'Inc.', 'Aus.', 'C.F.', 'Exc. Pat.', 'Exc. Obr.', 'P.D. Pat.', 'P.D. Obr.', 'G.M.P. Pat.', 'G.M.P. Obr.', 'R.T.', 'I.V. Pat.', 'I.V. Obr.', 'G.P.S.', 'Patronal', 'Obrera', 'Subtotal']
        else: headers = ['NSS', 'Nombre', 'RFC/CURP', 'Ubicación', 'Movimiento', 'Fecha Mov.', 'Días', 'SDI', 'Lic.', 'Inc.', 'Aus.', 'Retiro', 'Patronal RCV', 'Obrera RCV', 'Suma RCV', 'Ap. Pat. Infonavit', '%/$ /FD', 'Amortización', 'Suma Infonavit', 'Total General', 'Créd. Vivienda', 'Tipo Mov. Crédito', 'Fecha Mov. Crédito']
        writer.writerow(headers)
        for t in imp.trabajadores.all().order_by('id'):
            if imp.tipo == 'mensual': writer.writerow([t.nss, t.nombre, t.rfc_curp, t.clave_ubicacion, t.clave_mov, t.fecha_mov, t.dias, t.sdi, t.licencias, t.incapacidades, t.ausentismos, t.cuota_fija, t.excedente_patronal, t.excedente_obrera, t.prestaciones_dinero_patronal, t.prestaciones_dinero_obrera, t.gastos_medicos_patronal, t.gastos_medicos_obrera, t.riesgo_trabajo_cuota, t.invalidez_vida_patronal, t.invalidez_vida_obrera, t.guarderias_ps, t.imss_patronal, t.imss_obrera, t.imss_subtotal])
            else: writer.writerow([t.nss, t.nombre, t.rfc_curp, t.clave_ubicacion, t.clave_mov, t.fecha_mov, t.dias, t.sdi, t.licencias, t.incapacidades, t.ausentismos, t.retiro, t.patronal, t.obrera, t.subtotal, t.aportacion_patronal, t.tipo_valor_infonavit, t.amortizacion, t.suma_infonavit, t.total_general, t.cred_vivienda, t.tipo_mov_credito, t.fecha_mov_credito])
        return response
    except ImportacionSUA.DoesNotExist: return HttpResponse("No se encontró la importación", status=404)

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'crear', json_response=True)
def alta_empleados_sua_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        importacion = ImportacionSUA.objects.get(id=id, empresa=empresa_actual)
        trabajadores = importacion.trabajadores.all(); sucursal_id = request.session.get('sucursal_id')
        creados = 0; actualizados = 0; vinculados_a_contrato = 0
        beneficiarios_map = {b.clave.strip().upper(): b for b in Beneficiario.objects.filter(empresa=empresa_actual) if b.clave}
        
        # Pre-cache de contratos vigentes para búsqueda rápida
        # Filtramos por empresa y estado vigente
        contratos_vigentes = list(Contrato.objects.filter(empresa=empresa_actual, estado='vigente'))

        rfc_reporte = re.sub(r'[^A-Z0-9]', '', (importacion.rfc_empresa or '').upper()).strip()[:13]
        rp_reporte = re.sub(r'[^A-Z0-9]', '', (importacion.registro_patronal or '').upper()).strip()
        nombre_reporte = (importacion.nombre_razon_social or '').strip()

        filtros_or = Q()
        if rfc_reporte and rfc_reporte != "POR_DEFINIR": filtros_or |= Q(rfc__iexact=rfc_reporte)
        if rp_reporte: filtros_or |= Q(registro_patronal__iexact=rp_reporte)
        if nombre_reporte: filtros_or |= Q(nombre_razon_social__icontains=nombre_reporte)
            
        contratista_obj = Contratista.objects.filter(Q(empresa=empresa_actual) & filtros_or).first()
        status_cont = "Existente"
        if not contratista_obj:
            contratista_obj = Contratista.objects.create(empresa=empresa_actual, sucursal_id=sucursal_id, registro_patronal=rp_reporte, nombre_razon_social=nombre_reporte, rfc=rfc_reporte or "POR_DEFINIR", calle=importacion.domicilio, cp=importacion.cp, entidad_federativa=importacion.entidad, correo=f"contacto@{rp_reporte or 'empresa'}.com")
            status_cont = "NUEVO REGISTRO"
        else:
            save_needed = False
            if (not contratista_obj.rfc or contratista_obj.rfc == "POR_DEFINIR") and rfc_reporte: contratista_obj.rfc = rfc_reporte; save_needed = True
            if not contratista_obj.registro_patronal and rp_reporte: contratista_obj.registro_patronal = rp_reporte; save_needed = True
            if save_needed: contratista_obj.save()

        with transaction.atomic():
            for t in trabajadores:
                nss_clean = re.sub(r'[^0-9]', '', t.nss).strip()[:11]
                curp_clean = re.sub(r'[^A-Z0-9]', '', (t.rfc_curp or '').upper()).strip()[:18]
                empleado = Empleado.objects.filter(Q(nss=nss_clean) | Q(curp=curp_clean), empresa=empresa_actual).first()
                beneficiario_obj = beneficiarios_map.get((t.clave_ubicacion or "").strip().upper())
                nombre_partes = t.nombre.strip().split(' '); paterno = ""; materno = ""; nombres = t.nombre
                if len(nombre_partes) >= 3: paterno = nombre_partes[0]; materno = nombre_partes[1]; nombres = " ".join(nombre_partes[2:])
                elif len(nombre_partes) == 2: paterno = nombre_partes[0]; nombres = nombre_partes[1]

                if not empleado:
                    audit_nota = f"Importado el día {importacion.fecha_importacion.strftime('%d/%m/%Y')} de la cédula {importacion.periodo} del contratista {importacion.nombre_razon_social}"
                    empleado = Empleado(empresa=empresa_actual, sucursal_id=sucursal_id, nss=nss_clean, curp=curp_clean, nombre=nombres, apellido_paterno=paterno, apellido_materno=materno, sdi=t.sdi, contratista=contratista_obj, beneficiario=beneficiario_obj, puesto="", departamento="General", clave_ubicacion=t.clave_ubicacion, notas=audit_nota, estado='activo')
                    empleado.save(); creados += 1
                else:
                    empleado.sdi = t.sdi
                    if beneficiario_obj: empleado.beneficiario = beneficiario_obj
                    if contratista_obj: empleado.contratista = contratista_obj
                    if t.clave_ubicacion: empleado.clave_ubicacion = t.clave_ubicacion
                    empleado.save(); actualizados += 1
                
                # --- VINCULACIÓN AUTOMÁTICA CON CONTRATO ---
                if beneficiario_obj:
                    # Buscamos contratos que coincidan con este beneficiario
                    # El ancla fuerte es el Beneficiario (vía clave de ubicación en el SUA)
                    for c_v in contratos_vigentes:
                        if c_v.beneficiario_id == beneficiario_obj.id:
                            # Verificamos que el contratista coincida por objeto o por RFC/Registro
                            # para evitar cruces erróneos si hay múltiples contratistas con el mismo beneficiario
                            match_contratista = (
                                c_v.contratista_id == contratista_obj.id or
                                (c_v.contratista and (c_v.contratista.rfc == rfc_reporte or c_v.contratista.registro_patronal == rp_reporte))
                            )
                            if match_contratista:
                                c_v.empleados.add(empleado)
                                vinculados_a_contrato += 1
                                break

        return JsonResponse({'success': True, 'message': f'Proceso completado: {creados} nuevos, {actualizados} actualizados. {vinculados_a_contrato} vinculaciones a contratos realizadas. Contratista: {contratista_obj.nombre_razon_social}'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
