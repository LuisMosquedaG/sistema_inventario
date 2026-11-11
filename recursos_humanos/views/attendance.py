import base64
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

from PIL import Image, ImageOps

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from preferencias.permissions import require_hr_permission, user_has_hr_permission
from ..models import AsistenciaEmpleado, Empleado
from .utils import get_empresa_actual


def _formatear_duracion(td):
    """Convierte un timedelta positivo a texto legible (ej. '8h 15m')."""
    if not td or td.total_seconds() <= 0:
        return '--'
    total_mins = int(td.total_seconds() // 60)
    horas = total_mins // 60
    minutos = total_mins % 60
    return f"{horas}h {minutos:02d}m"


def _agrupar_asistencias_por_dia(registros_qs):
    """Agrupa objetos AsistenciaEmpleado por fecha local y calcula tiempos por jornada."""
    dias_map = {}
    for reg in registros_qs.order_by('fecha', 'fecha_hora'):
        fecha_key = reg.fecha
        if fecha_key not in dias_map:
            dias_map[fecha_key] = {
                'fecha': fecha_key,
                'entrada_laboral': None,
                'salida_comer': None,
                'regreso_comer': None,
                'salida_laboral': None,
                'todos': [],
            }
        dia = dias_map[fecha_key]
        dia['todos'].append(reg)
        # Primer registro de entrada, y último de salida en caso de múltiples intentos
        if reg.tipo == 'entrada_laboral' and dia['entrada_laboral'] is None:
            dia['entrada_laboral'] = reg
        elif reg.tipo == 'salida_comer' and dia['salida_comer'] is None:
            dia['salida_comer'] = reg
        elif reg.tipo == 'regreso_comer':
            dia['regreso_comer'] = reg
        elif reg.tipo == 'salida_laboral':
            dia['salida_laboral'] = reg

    resumen_dias = []
    total_segundos_laborados = 0
    for fecha_key in sorted(dias_map.keys(), reverse=True):
        dia = dias_map[fecha_key]
        ent = dia['entrada_laboral']
        sal_com = dia['salida_comer']
        reg_com = dia['regreso_comer']
        sal = dia['salida_laboral']

        td_comida = None
        if sal_com and reg_com and reg_com.fecha_hora > sal_com.fecha_hora:
            td_comida = reg_com.fecha_hora - sal_com.fecha_hora

        td_bruto = None
        td_laborado = None
        if ent and sal and sal.fecha_hora > ent.fecha_hora:
            td_bruto = sal.fecha_hora - ent.fecha_hora
            td_laborado = td_bruto - td_comida if td_comida and td_bruto > td_comida else td_bruto
            total_segundos_laborados += int(td_laborado.total_seconds())

        dia['tiempo_comida'] = _formatear_duracion(td_comida)
        dia['tiempo_bruto'] = _formatear_duracion(td_bruto)
        dia['tiempo_laborado'] = _formatear_duracion(td_laborado)
        dia['segundos_brutos'] = int(td_bruto.total_seconds()) if td_bruto else 0
        dia['segundos_laborados'] = int(td_laborado.total_seconds()) if td_laborado else 0
        dia['columnas_checadas'] = [ent, sal_com, reg_com, sal]
        resumen_dias.append(dia)

    return resumen_dias, total_segundos_laborados


def _obtener_ip_cliente(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _optimizar_foto_asistencia(foto_file, nombre_base):
    """Redimensiona proporcionalmente (máx. 1080px) y comprime a JPEG progresivo sin perder nitidez."""
    if not foto_file:
        return foto_file
    try:
        foto_file.seek(0)
        img = Image.open(foto_file)
        img = ImageOps.exif_transpose(img)

        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            fondo = Image.new('RGB', img.size, (255, 255, 255))
            rgba = img.convert('RGBA')
            fondo.paste(rgba, mask=rgba.split()[3])
            img = fondo
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        max_dim = 1080
        if max(img.width, img.height) > max_dim:
            resample = getattr(Image, 'Resampling', Image).LANCZOS
            img.thumbnail((max_dim, max_dim), resample)

        target_max_bytes = 220 * 1024
        buffer = BytesIO()
        for calidad in (84, 78, 72, 66):
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=calidad, optimize=True, progressive=True)
            if buffer.tell() <= target_max_bytes:
                break

        base_sin_ext = nombre_base.rsplit('.', 1)[0]
        return ContentFile(buffer.getvalue(), name=f"{base_sin_ext}.jpg")
    except Exception:
        try:
            foto_file.seek(0)
        except Exception:
            pass
        return foto_file


def _decodificar_foto_base64(data_url, filename_prefix):
    if not data_url or ';base64,' not in data_url:
        return None
    header, b64_data = data_url.split(';base64,', 1)
    ext = 'jpg'
    if 'png' in header.lower():
        ext = 'png'
    elif 'webp' in header.lower():
        ext = 'webp'
    decoded = base64.b64decode(b64_data)
    return ContentFile(decoded, name=f"{filename_prefix}_{uuid.uuid4().hex[:8]}.{ext}")


def _obtener_estado_jornada(registros_hoy):
    """Determina estado actual de la jornada, siguiente acción sugerida y acciones permitidas."""
    ultimo_registro = registros_hoy[-1] if registros_hoy else None

    if not ultimo_registro:
        return (
            'sin_iniciar',
            'Sin iniciar jornada',
            'entrada_laboral',
            {'entrada_laboral'},
            ultimo_registro,
        )
    if ultimo_registro.tipo == 'entrada_laboral':
        return (
            'en_jornada',
            'En jornada laboral',
            'salida_comer',
            {'salida_comer', 'salida_laboral'},
            ultimo_registro,
        )
    if ultimo_registro.tipo == 'salida_comer':
        return (
            'en_comida',
            'En horario de comida',
            'regreso_comer',
            {'regreso_comer'},
            ultimo_registro,
        )
    if ultimo_registro.tipo == 'regreso_comer':
        return (
            'en_jornada',
            'En jornada laboral',
            'salida_laboral',
            {'salida_laboral'},
            ultimo_registro,
        )
    return (
        'finalizada',
        'Jornada finalizada',
        None,
        set(),
        ultimo_registro,
    )


def _mensaje_movimiento_no_permitido(estado_jornada, tipo):
    if estado_jornada == 'sin_iniciar':
        return 'Primero debes registrar tu Entrada Laboral antes de marcar comida o salida.'
    if estado_jornada == 'en_comida':
        return 'Estás en horario de comida. Primero debes registrar "Entrar de Comer".'
    if estado_jornada == 'finalizada':
        return 'Tu jornada laboral del día de hoy ya fue finalizada.'
    if tipo == 'entrada_laboral':
        return 'Ya registraste tu Entrada Laboral el día de hoy.'
    return 'Este movimiento no corresponde al estado actual de tu jornada.'


@login_required(login_url='/login/')
def portal_asistencias_empleado(request):
    """Vista móvil simplificada (Reloj Checador) exclusiva para empleados."""
    empleado = getattr(request.user, 'empleado', None)
    if not empleado:
        return redirect('dashboard_inicio')

    empresa = empleado.empresa
    hoy = timezone.localdate()
    registros_hoy = list(
        AsistenciaEmpleado.objects.filter(empleado=empleado, fecha=hoy).order_by('fecha_hora')
    )
    tipos_registrados = {r.tipo for r in registros_hoy}
    (
        estado_jornada,
        estado_texto,
        siguiente_sugerido,
        acciones_permitidas,
        ultimo_registro,
    ) = _obtener_estado_jornada(registros_hoy)

    hace_7_dias = hoy - timedelta(days=7)
    historial_qs = AsistenciaEmpleado.objects.filter(
        empleado=empleado,
        fecha__gte=hace_7_dias
    )
    resumen_reciente, _ = _agrupar_asistencias_por_dia(historial_qs)

    return render(request, 'recursos_humanos/portal_asistencias.html', {
        'empresa': empresa,
        'empleado': empleado,
        'hoy': hoy,
        'registros_hoy': registros_hoy,
        'tipos_registrados': tipos_registrados,
        'ultimo_registro': ultimo_registro,
        'estado_jornada': estado_jornada,
        'estado_texto': estado_texto,
        'siguiente_sugerido': siguiente_sugerido,
        'acciones_permitidas': acciones_permitidas,
        'resumen_reciente': resumen_reciente,
    })


@login_required(login_url='/login/')
@require_POST
def registrar_asistencia_ajax(request):
    """Endpoint AJAX móvil para guardar checada de asistencia (foto frontal en entrada/salida + GPS + hora servidor)."""
    empleado = getattr(request.user, 'empleado', None)
    if not empleado:
        return JsonResponse({'success': False, 'error': 'Tu usuario no está vinculado a un empleado.'}, status=403)

    if empleado.estado != 'activo':
        return JsonResponse({'success': False, 'error': 'Tu perfil de empleado no se encuentra activo.'}, status=403)

    tipo = (request.POST.get('tipo') or '').strip()
    tipos_validos = {k for k, _ in AsistenciaEmpleado.TIPO_REGISTRO_CHOICES}
    if tipo not in tipos_validos:
        return JsonResponse({'success': False, 'error': 'Tipo de registro de asistencia inválido.'}, status=400)

    ahora = timezone.now()
    fecha_local = timezone.localdate(ahora)

    registros_hoy = list(
        AsistenciaEmpleado.objects.filter(empleado=empleado, fecha=fecha_local).order_by('fecha_hora')
    )
    estado_jornada, _, _, acciones_permitidas, _ = _obtener_estado_jornada(registros_hoy)
    if tipo not in acciones_permitidas:
        return JsonResponse({
            'success': False,
            'error': _mensaje_movimiento_no_permitido(estado_jornada, tipo)
        }, status=400)

    # Validar GPS obligatorio
    lat_raw = (request.POST.get('latitud') or '').strip()
    lng_raw = (request.POST.get('longitud') or '').strip()
    prec_raw = (request.POST.get('precision_gps') or '').strip()

    if not lat_raw or not lng_raw:
        return JsonResponse({
            'success': False,
            'error': 'No se pudo obtener tu ubicación GPS. Activa la ubicación y otorga permiso al navegador.'
        }, status=400)

    try:
        latitud = Decimal(lat_raw).quantize(Decimal('0.0000001'))
        longitud = Decimal(lng_raw).quantize(Decimal('0.0000001'))
        if not (-90 <= latitud <= 90) or not (-180 <= longitud <= 180):
            raise ValueError('Coordenadas fuera de rango')
    except (InvalidOperation, ValueError):
        return JsonResponse({'success': False, 'error': 'Las coordenadas GPS recibidas no son válidas.'}, status=400)

    precision_gps = None
    if prec_raw:
        try:
            precision_gps = round(float(prec_raw), 1)
        except (TypeError, ValueError):
            precision_gps = None

    # Validar fotografía obligatoria para Entrada Laboral y Salida Laboral
    requiere_foto = tipo in ('entrada_laboral', 'salida_laboral')
    foto_file = request.FILES.get('foto')
    if not foto_file and request.POST.get('foto_base64'):
        try:
            foto_file = _decodificar_foto_base64(
                request.POST.get('foto_base64'),
                f"asistencia_{empleado.id}_{tipo}"
            )
        except Exception:
            foto_file = None

    if requiere_foto and not foto_file:
        return JsonResponse({
            'success': False,
            'error': 'La fotografía con cámara frontal es obligatoria para registrar tu entrada o salida laboral.'
        }, status=400)

    # Prevenir doble clic accidental en los últimos 30 segundos
    reciente = AsistenciaEmpleado.objects.filter(
        empleado=empleado,
        tipo=tipo,
        fecha_hora__gte=ahora - timedelta(seconds=30)
    ).exists()
    if reciente:
        return JsonResponse({
            'success': False,
            'error': 'Este registro ya acaba de guardarse hace unos segundos.'
        }, status=409)

    if foto_file:
        ext = foto_file.name.rsplit('.', 1)[-1].lower() if hasattr(foto_file, 'name') and '.' in foto_file.name else 'jpg'
        nombre_base = f"asistencia_{empleado.id}_{tipo}_{timezone.localtime(ahora).strftime('%Y%m%d_%H%M%S')}.{ext}"
        foto_file = _optimizar_foto_asistencia(foto_file, nombre_base)

    registro = AsistenciaEmpleado.objects.create(
        empresa=empleado.empresa,
        empleado=empleado,
        sucursal=empleado.sucursal,
        tipo=tipo,
        fecha=fecha_local,
        fecha_hora=ahora,
        latitud=latitud,
        longitud=longitud,
        precision_gps=precision_gps,
        foto=foto_file if requiere_foto else None,
        ip_address=_obtener_ip_cliente(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
    )

    hora_local = timezone.localtime(registro.fecha_hora)
    return JsonResponse({
        'success': True,
        'message': f'{registro.get_tipo_display()} registrada a las {hora_local.strftime("%H:%M:%S")}.',
        'registro': {
            'id': registro.id,
            'tipo': registro.tipo,
            'tipo_display': registro.get_tipo_display(),
            'fecha': hora_local.strftime('%d/%m/%Y'),
            'hora': hora_local.strftime('%H:%M:%S'),
            'latitud': str(registro.latitud),
            'longitud': str(registro.longitud),
            'precision_gps': registro.precision_gps,
            'foto_url': registro.foto.url if registro.foto else '',
        }
    })


@login_required(login_url='/login/')
@require_hr_permission('empleados', 'ver_asistencias')
def asistencias_empleado_detalle(request, id):
    """Vista administrativa de control de asistencias por empleado dentro de Obligaciones Patronales -> Empleados."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(
        Empleado.objects.select_related('sucursal', 'usuario', 'contratista', 'beneficiario'),
        id=id,
        empresa=empresa_actual
    )

    hoy = timezone.localdate()
    inicio_default = hoy.replace(day=1)

    fecha_inicio_str = (request.GET.get('fecha_inicio') or '').strip()
    fecha_fin_str = (request.GET.get('fecha_fin') or '').strip()

    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else inicio_default
    except ValueError:
        fecha_inicio = inicio_default

    try:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else hoy
    except ValueError:
        fecha_fin = hoy

    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    registros_qs = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin
    )

    resumen_dias, total_segundos = _agrupar_asistencias_por_dia(registros_qs)
    total_horas_str = _formatear_duracion(timedelta(seconds=total_segundos))

    # Exportación a Excel si se solicita
    if request.GET.get('export') == 'excel':
        if not user_has_hr_permission(request, 'empleados', 'exportar_excel_asistencias'):
            messages.error(request, 'No cuentas con permiso para exportar asistencias a Excel.')
            return redirect(f"{request.path}?fecha_inicio={fecha_inicio:%Y-%m-%d}&fecha_fin={fecha_fin:%Y-%m-%d}")
        return _exportar_asistencias_excel(empleado, resumen_dias, fecha_inicio, fecha_fin, total_horas_str)

    return render(request, 'recursos_humanos/asistencias_empleado.html', {
        'empresa': empresa_actual,
        'empleado': empleado,
        'resumen_dias': resumen_dias,
        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
        'total_dias': len(resumen_dias),
        'total_horas_str': total_horas_str,
        'total_registros': registros_qs.count(),
    })


def _exportar_asistencias_excel(empleado, resumen_dias, fecha_inicio, fecha_fin, total_horas_str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Asistencias"

    fill_brand = PatternFill(start_color="00B8B9", end_color="00B8B9", fill_type="solid")
    fill_sub = PatternFill(start_color="1A252F", end_color="1A252F", fill_type="solid")
    font_header = Font(bold=True, color="FFFFFF", size=10)
    font_title = Font(bold=True, size=13, color="1A252F")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1'),
    )

    nombre_emp = f"{empleado.nombre} {empleado.apellido_paterno} {empleado.apellido_materno}".strip()
    ws['A1'] = f"Control de Asistencias - {nombre_emp}"
    ws['A1'].font = font_title
    ws['A2'] = f"No. Empleado: {empleado.num_empleado or 'S/N'} | Periodo: {fecha_inicio:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} | Total Laborado: {total_horas_str}"
    ws['A2'].font = Font(size=10, color="475569")

    headers = [
        "Fecha",
        "Entrada Laboral",
        "Ubicación Entrada",
        "Salida a Comer",
        "Ubicación Salida Comer",
        "Regreso de Comer",
        "Ubicación Regreso Comer",
        "Salida Laboral",
        "Ubicación Salida",
        "Tiempo Comida",
        "Horas Brutas",
        "Horas Netas",
    ]
    ws.append([])
    ws.append(headers)
    header_row = 4
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.fill = fill_brand if col_idx not in (10, 11, 12) else fill_sub
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    def _fmt_hora(reg):
        return timezone.localtime(reg.fecha_hora).strftime("%H:%M:%S") if reg else "--"

    def _fmt_gps(reg):
        if reg and reg.latitud is not None and reg.longitud is not None:
            return f"{reg.latitud}, {reg.longitud}"
        return "--"

    for idx, dia in enumerate(resumen_dias, start=header_row + 1):
        row_vals = [
            dia['fecha'].strftime("%d/%m/%Y"),
            _fmt_hora(dia['entrada_laboral']),
            _fmt_gps(dia['entrada_laboral']),
            _fmt_hora(dia['salida_comer']),
            _fmt_gps(dia['salida_comer']),
            _fmt_hora(dia['regreso_comer']),
            _fmt_gps(dia['regreso_comer']),
            _fmt_hora(dia['salida_laboral']),
            _fmt_gps(dia['salida_laboral']),
            dia['tiempo_comida'],
            dia['tiempo_bruto'],
            dia['tiempo_laborado'],
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            c = ws.cell(row=idx, column=col_idx, value=val)
            c.border = thin_border
            c.alignment = Alignment(horizontal="center", vertical="center")

    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 22 if "Ubicación" in headers[col_idx - 1] else 16

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Asistencias_{empleado.num_empleado or empleado.id}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.xlsx"
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'eliminar_asistencia', json_response=True)
def eliminar_asistencia_dia_ajax(request, id):
    """Elimina los registros de asistencia de un día específico para que el empleado pueda volver a checar."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(Empleado, id=id, empresa=empresa_actual)

    fecha_str = (request.POST.get('fecha') or '').strip()
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Fecha inválida.'}, status=400)

    registros = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha=fecha_obj
    )
    if not registros.exists():
        return JsonResponse({'success': False, 'error': 'No se encontraron registros para la fecha indicada.'}, status=404)

    for reg in registros:
        if reg.foto:
            try:
                reg.foto.delete(save=False)
            except Exception:
                pass

    eliminados = registros.count()
    registros.delete()
    return JsonResponse({
        'success': True,
        'message': f'Se eliminaron {eliminados} registro(s) del {fecha_obj.strftime("%d/%m/%Y")}. El empleado ya puede volver a registrar su asistencia.'
    })


_TIPOS_ORDEN = ('entrada_laboral', 'salida_comer', 'regreso_comer', 'salida_laboral')


def _parsear_hora(hora_str):
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(hora_str, fmt).time()
        except ValueError:
            continue
    return None


def _parsear_coordenadas(lat_raw, lng_raw):
    lat_str = (lat_raw or '').strip()
    lng_str = (lng_raw or '').strip()
    if not lat_str and not lng_str:
        return None, None, None
    if not lat_str or not lng_str:
        return None, None, 'Debes indicar tanto latitud como longitud (o dejar ambas vacías).'
    try:
        lat = Decimal(lat_str).quantize(Decimal('0.0000001'))
        lng = Decimal(lng_str).quantize(Decimal('0.0000001'))
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return None, None, 'Coordenadas GPS fuera de rango válido.'
        return lat, lng, None
    except (InvalidOperation, ValueError):
        return None, None, 'Formato inválido en coordenadas GPS.'


@login_required(login_url='/login/')
@require_hr_permission('empleados', 'editar_asistencias', json_response=True)
def obtener_asistencia_dia_json(request, id):
    """Devuelve los registros editables de asistencia de un empleado para una fecha."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(Empleado, id=id, empresa=empresa_actual)

    fecha_str = (request.GET.get('fecha') or '').strip()
    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Fecha inválida.'}, status=400)

    registros = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha=fecha_obj
    ).order_by('fecha_hora')

    dias, _ = _agrupar_asistencias_por_dia(registros)
    dia = dias[0] if dias else None

    puede_ver_fotos = user_has_hr_permission(request, 'empleados', 'ver_fotos')
    movimientos = {}
    notas = ''
    for tipo in _TIPOS_ORDEN:
        reg = dia.get(tipo) if dia else None
        if reg:
            if not notas and reg.notas:
                notas = reg.notas
            movimientos[tipo] = {
                'hora': timezone.localtime(reg.fecha_hora).strftime('%H:%M:%S'),
                'latitud': str(reg.latitud) if reg.latitud is not None else '',
                'longitud': str(reg.longitud) if reg.longitud is not None else '',
                'foto_url': (reg.foto.url if reg.foto else '') if puede_ver_fotos else '',
            }
        else:
            movimientos[tipo] = {'hora': '', 'latitud': '', 'longitud': '', 'foto_url': ''}

    return JsonResponse({
        'success': True,
        'data': {
            'fecha': fecha_obj.strftime('%Y-%m-%d'),
            'notas': notas,
            'movimientos': movimientos,
        }
    })


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar_asistencias', json_response=True)
def editar_asistencia_dia_ajax(request, id):
    """Actualiza horarios, fecha, GPS, notas y fotografías de las checadas de un día."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(Empleado, id=id, empresa=empresa_actual)

    fecha_orig_str = (request.POST.get('fecha_original') or '').strip()
    fecha_dest_str = (request.POST.get('fecha') or fecha_orig_str).strip()
    try:
        fecha_original = datetime.strptime(fecha_orig_str, '%Y-%m-%d').date()
        fecha_destino = datetime.strptime(fecha_dest_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'La fecha indicada no es válida.'}, status=400)

    if fecha_destino != fecha_original and AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual, empleado=empleado, fecha=fecha_destino
    ).exists():
        return JsonResponse({
            'success': False,
            'error': f'Ya existen registros de asistencia en la fecha {fecha_destino.strftime("%d/%m/%Y")}.'
        }, status=400)

    notas = (request.POST.get('notas') or '').strip()
    tz_actual = timezone.get_current_timezone()

    registros_orig = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha=fecha_original
    ).order_by('fecha_hora')
    dias, _ = _agrupar_asistencias_por_dia(registros_orig)
    dia_orig = dias[0] if dias else {}

    al_menos_uno = False
    parsed_movimientos = {}
    for tipo in _TIPOS_ORDEN:
        hora_raw = (request.POST.get(f'{tipo}_hora') or '').strip()
        if not hora_raw:
            parsed_movimientos[tipo] = None
            continue

        al_menos_uno = True
        hora_obj = _parsear_hora(hora_raw)
        if not hora_obj:
            return JsonResponse({'success': False, 'error': f'Hora inválida en {tipo.replace("_", " ")}.'}, status=400)

        lat, lng, gps_err = _parsear_coordenadas(
            request.POST.get(f'{tipo}_latitud'),
            request.POST.get(f'{tipo}_longitud'),
        )
        if gps_err:
            return JsonResponse({'success': False, 'error': gps_err}, status=400)

        parsed_movimientos[tipo] = (hora_obj, lat, lng)

    if not al_menos_uno:
        return JsonResponse({
            'success': False,
            'error': 'Captura al menos un horario (para borrar el día completo usa el botón Eliminar).'
        }, status=400)

    try:
        with transaction.atomic():
            for tipo in _TIPOS_ORDEN:
                datos_mov = parsed_movimientos[tipo]
                reg_existente = dia_orig.get(tipo)

                if datos_mov is None:
                    # Eliminar todas las ocurrencias de este tipo en la fecha original si se dejó vacío
                    extras = registros_orig.filter(tipo=tipo)
                    for r in extras:
                        if r.foto:
                            r.foto.delete(save=False)
                    extras.delete()
                    continue

                hora_obj, lat, lng = datos_mov
                aware_dt = timezone.make_aware(datetime.combine(fecha_destino, hora_obj), tz_actual)

                if reg_existente:
                    reg = reg_existente
                    reg.fecha = fecha_destino
                    reg.fecha_hora = aware_dt
                    reg.latitud = lat
                    reg.longitud = lng
                    reg.notas = notas
                else:
                    reg = AsistenciaEmpleado(
                        empresa=empresa_actual,
                        empleado=empleado,
                        sucursal=empleado.sucursal,
                        tipo=tipo,
                        fecha=fecha_destino,
                        fecha_hora=aware_dt,
                        latitud=lat,
                        longitud=lng,
                        notas=notas,
                    )

                if tipo in ('entrada_laboral', 'salida_laboral'):
                    foto_nueva = request.FILES.get(f'{tipo}_foto')
                    eliminar_foto = request.POST.get(f'{tipo}_eliminar_foto') in ('1', 'true', 'on')
                    if foto_nueva:
                        if reg.foto:
                            reg.foto.delete(save=False)
                        ext = foto_nueva.name.rsplit('.', 1)[-1].lower() if '.' in foto_nueva.name else 'jpg'
                        nombre_base = f"asistencia_{empleado.id}_{tipo}_{fecha_destino:%Y%m%d}_{hora_obj:%H%M%S}.{ext}"
                        reg.foto = _optimizar_foto_asistencia(foto_nueva, nombre_base)
                    elif eliminar_foto and reg.foto:
                        reg.foto.delete(save=False)
                        reg.foto = None

                reg.save()

                # Si movemos de fecha, aseguramos actualizar notas/fecha en otros duplicados de ese tipo o mantener limpio
                if reg_existente:
                    registros_orig.filter(tipo=tipo).exclude(id=reg.id).delete()

        return JsonResponse({
            'success': True,
            'message': f'Asistencia del {fecha_destino.strftime("%d/%m/%Y")} actualizada correctamente.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
