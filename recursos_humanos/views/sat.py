from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from datetime import datetime

from ..models import Contratista, FielContratista, SolicitudDescargaSAT
from .utils import get_empresa_actual
from ..security_utils import get_master_key, cifrar_archivos_fiel
from ..sat_service import SATService
from preferencias.permissions import require_hr_permission

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def diagnostico_fiel_ajax(request):
    """Extrae información de un certificado .cer para diagnóstico."""
    archivo_cer = request.FILES.get('archivo_cer')
    if not archivo_cer:
        return JsonResponse({'success': False, 'error': 'No se proporcionó el archivo .cer'})
    
    res = SATService.obtener_info_certificado(archivo_cer.read())
    return JsonResponse(res)

@login_required(login_url='/login/')
@require_POST
@transaction.atomic
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def solicitar_descarga_sat_ajax(request):
    """Envía una solicitud real al Web Service del SAT."""
    empresa_actual = get_empresa_actual(request)
    data = request.POST
    contratista_id = data.get('contratista_id')
    password_fiel = data.get('password_fiel')
    fecha_inicio_str = data.get('fecha_inicio')
    fecha_fin_str = data.get('fecha_fin')
    estatus = data.get('estatus', 'vigente')

    if not contratista_id or not password_fiel:
        return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios (Contratista o Contraseña).'})

    contratista = get_object_or_404(Contratista, id=contratista_id, empresa=empresa_actual)
    
    archivo_cer = request.FILES.get('archivo_cer')
    archivo_key = request.FILES.get('archivo_key')
    master_key = get_master_key()
    
    if archivo_cer and archivo_key:
        try:
            cer_content = archivo_cer.read()
            info_cert = SATService.obtener_info_certificado(cer_content)
            if not info_cert['success']:
                return JsonResponse({'status': 'error', 'message': f"El archivo .cer no es válido: {info_cert['error']}"})
            
            if not info_cert['es_fiel']:
                return JsonResponse({'status': 'error', 'message': "El certificado subido es de SELLOS (CSD). Para este trámite se requiere la e.firma (FIEL)."})

            rfc_cert = info_cert['rfc'].upper().strip()
            rfc_cont = contratista.rfc.upper().strip()
            if rfc_cert != rfc_cont:
                return JsonResponse({
                    'status': 'error', 
                    'message': f"El RFC del certificado ({rfc_cert}) no coincide con el RFC del contratista seleccionado ({rfc_cont})."
                })

            cer_cifrado, key_cifrado, data_key_cifrada = cifrar_archivos_fiel(
                cer_content, 
                archivo_key.read(), 
                master_key
            )
            FielContratista.objects.update_or_create(
                contratista=contratista,
                defaults={
                    'certificado_cifrado': cer_cifrado,
                    'llave_privada_cifrada': key_cifrado,
                    'data_key_cifrada': data_key_cifrada,
                    'rfc_fiel': info_cert['rfc']
                }
            )
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error al procesar archivos FIEL: {str(e)}'})

    try:
        sat_service = SATService(contratista)
        f_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        f_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        id_solicitud = sat_service.solicitar_descarga(password_fiel, f_inicio, f_fin, estatus)

        if not id_solicitud:
            return JsonResponse({'status': 'error', 'message': 'El SAT no devolvió un ID de solicitud.'})

        SolicitudDescargaSAT.objects.create(
            empresa=empresa_actual,
            contratista=contratista,
            usuario=request.user,
            id_solicitud=id_solicitud,
            fecha_inicio=f_inicio.date(),
            fecha_fin=f_fin.date(),
            estatus_cfdi=estatus,
            estado='solicitada'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Solicitud enviada al SAT exitosamente. ID: {id_solicitud}'
        })
    except Exception as e:
        import traceback
        err_detail = str(e) or f"Excepción de tipo {type(e).__name__} sin mensaje."
        print(f"--- ERROR SAT ---\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': f'Error del SAT o Servidor: {err_detail}'})

@login_required(login_url='/login/')
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def verificar_fiel_contratista_ajax(request, contratista_id):
    empresa_actual = get_empresa_actual(request)
    contratista = get_object_or_404(Contratista, id=contratista_id, empresa=empresa_actual)
    fiel = FielContratista.objects.filter(contratista=contratista).first()
    return JsonResponse({
        'tiene_fiel': fiel is not None,
        'rfc': fiel.rfc_fiel if fiel else contratista.rfc,
        'nombre': contratista.nombre_razon_social
    })

@login_required(login_url='/login/')
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def listar_solicitudes_sat_ajax(request):
    empresa_actual = get_empresa_actual(request)
    solicitudes = SolicitudDescargaSAT.objects.filter(empresa=empresa_actual).select_related('usuario').order_by('-fecha_creacion')[:10]
    data = []
    for s in solicitudes:
        usuario_str = s.usuario.username.split('@')[0] if s.usuario else "Sistema"
        estatus_display = s.get_estatus_cfdi_display() if hasattr(s, 'get_estatus_cfdi_display') else (s.estatus_cfdi or 'vigente')
        data.append({
            'id': s.id,
            'id_solicitud': s.id_solicitud,
            'periodo': f"{s.fecha_inicio} al {s.fecha_fin}",
            'estado': s.estado,
            'estatus_cfdi': estatus_display,
            'fecha': s.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'usuario': usuario_str
        })
    return JsonResponse({'solicitudes': data})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def verificar_estatus_sat_ajax(request, solicitud_id):
    empresa_actual = get_empresa_actual(request)
    solicitud = get_object_or_404(SolicitudDescargaSAT, id=solicitud_id, empresa=empresa_actual)
    password = request.POST.get('password_fiel')
    if not password: return JsonResponse({'status': 'error', 'message': 'Se requiere la contraseña de la FIEL.'})
    try:
        sat_service = SATService(solicitud.contratista)
        res = sat_service.verificar_estatus(solicitud.id_solicitud, password)
        estado_map = {'1': 'solicitada', '2': 'en_proceso', '3': 'terminada', '4': 'error'}
        solicitud.estado = estado_map.get(str(res['estado']), 'en_proceso'); solicitud.save()
        return JsonResponse({'status': 'success', 'nuevo_estado': solicitud.estado})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def integrar_xml_sat_ajax(request, solicitud_id):
    empresa_actual = get_empresa_actual(request)
    solicitud = get_object_or_404(SolicitudDescargaSAT, id=solicitud_id, empresa=empresa_actual)
    password = request.POST.get('password_fiel')
    if solicitud.estado != 'terminada': return JsonResponse({'status': 'error', 'message': 'Solicitud no terminada en el SAT.'})
    try:
        sat_service = SATService(solicitud.contratista)
        res = sat_service.verificar_estatus(solicitud.id_solicitud, password)
        paquetes = res.get('paquetes', [])
        if not paquetes: return JsonResponse({'status': 'error', 'message': 'No se encontraron paquetes para descargar.'})
        count, archivos_encontrados = sat_service.descargar_e_integrar(solicitud.id_solicitud, paquetes, password, empresa_actual, request.session.get('sucursal_id'), estatus_cfdi=solicitud.estatus_cfdi)
        if count > 0:
            solicitud.estado = 'procesada'; solicitud.save()
            return JsonResponse({'status': 'success', 'message': f'Integración exitosa. Se procesaron {count} XMLs de nómina reales.'})
        else:
            lista_archivos = ", ".join(archivos_encontrados[:5]) + ("..." if len(archivos_encontrados) > 5 else "")
            return JsonResponse({'status': 'success', 'message': f'Se procesaron 0 XMLs de nómina. Archivos encontrados: {lista_archivos}. Verifique que el periodo contenga CFDI de Nómina.'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('nomina', 'xml_sat', json_response=True)
def cargar_xml_directo_ajax(request):
    """Procesa y carga archivos XML o un lote en ZIP directamente en el sistema."""
    import zipfile
    import io

    empresa_actual = get_empresa_actual(request)
    estatus_cfdi = request.POST.get('estatus', 'vigente')
    sucursal_id_str = request.POST.get('sucursal')
    sucursal_id = int(sucursal_id_str) if (sucursal_id_str and sucursal_id_str.isdigit()) else None

    archivos = request.FILES.getlist('archivos')
    if not archivos:
        return JsonResponse({'status': 'error', 'message': 'No se seleccionaron archivos para cargar.'})

    count = 0
    errores = []

    for f in archivos:
        filename = f.name.lower()
        if filename.endswith('.zip'):
            try:
                zip_data = f.read()
                with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                    for xml_name in z.namelist():
                        if xml_name.lower().endswith('.xml') and not xml_name.endswith('/'):
                            try:
                                with z.open(xml_name) as xml_file:
                                    if SATService._parsear_y_guardar_xml(
                                        xml_file.read(),
                                        empresa_actual,
                                        sucursal_id,
                                        estatus_cfdi=estatus_cfdi
                                    ):
                                        count += 1
                            except Exception as parse_err:
                                errores.append(f"Error en {xml_name}: {str(parse_err)}")
            except Exception as zip_err:
                errores.append(f"Error al procesar el archivo ZIP {f.name}: {str(zip_err)}")
        elif filename.endswith('.xml'):
            try:
                xml_data = f.read()
                if SATService._parsear_y_guardar_xml(
                    xml_data,
                    empresa_actual,
                    sucursal_id,
                    estatus_cfdi=estatus_cfdi
                ):
                    count += 1
                else:
                    errores.append(f"El archivo {f.name} no es un CFDI de nómina válido o no tiene nodo de Nómina.")
            except Exception as xml_err:
                errores.append(f"Error al procesar el archivo XML {f.name}: {str(xml_err)}")
        else:
            errores.append(f"El archivo {f.name} tiene un formato no admitido. Use solo .xml o .zip")

    if count > 0:
        msg = f"Se cargaron e integraron con éxito {count} recibo(s) de nómina."
        if errores:
            msg += f" Ocurrieron algunos errores: {', '.join(errores[:3])}"
            if len(errores) > 3:
                msg += " ..."
        return JsonResponse({'status': 'success', 'message': msg})
    else:
        err_msg = "No se pudo procesar ningún archivo de nómina."
        if errores:
            err_msg += f" Detalles: {', '.join(errores[:3])}"
            if len(errores) > 3:
                err_msg += " ..."
        return JsonResponse({'status': 'error', 'message': err_msg})
