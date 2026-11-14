import base64
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

from PIL import Image, ImageOps

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from preferencias.permissions import require_hr_permission, user_has_hr_permission
from ..models import AsistenciaEmpleado, ConfiguracionJornadaLaboral, Contratista, Empleado
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
    registros = (
        registros_qs.order_by('fecha', 'fecha_hora')
        if hasattr(registros_qs, 'order_by')
        else sorted(registros_qs, key=lambda r: (r.fecha, r.fecha_hora))
    )
    for reg in registros:
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

    # Emparejar turnos nocturnos guardados con fechas distintas (ej. entrada noche día N y salida mañana día N+1)
    fechas_ordenadas = sorted(dias_map.keys())
    for fecha_k in fechas_ordenadas:
        dia_actual = dias_map.get(fecha_k)
        if not dia_actual:
            continue
        ent = dia_actual['entrada_laboral']
        if ent and dia_actual['salida_laboral'] is None and timezone.localtime(ent.fecha_hora).hour >= 18:
            next_day = fecha_k + timedelta(days=1)
            dia_siguiente = dias_map.get(next_day)
            if dia_siguiente and dia_siguiente['salida_laboral']:
                sal_candidata = dia_siguiente['salida_laboral']
                if ent.fecha_hora < sal_candidata.fecha_hora <= ent.fecha_hora + timedelta(hours=18):
                    dia_actual['salida_laboral'] = sal_candidata
                    dia_actual['todos'].append(sal_candidata)
                    if dia_siguiente['regreso_comer'] and not dia_actual['regreso_comer']:
                        dia_actual['regreso_comer'] = dia_siguiente['regreso_comer']
                        dia_actual['todos'].append(dia_siguiente['regreso_comer'])
                    if dia_siguiente['salida_comer'] and not dia_actual['salida_comer']:
                        dia_actual['salida_comer'] = dia_siguiente['salida_comer']
                        dia_actual['todos'].append(dia_siguiente['salida_comer'])

                    dia_siguiente['salida_laboral'] = None
                    if sal_candidata in dia_siguiente['todos']:
                        dia_siguiente['todos'].remove(sal_candidata)
                    if not dia_siguiente['entrada_laboral'] and not dia_siguiente['todos']:
                        del dias_map[next_day]

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

        ips_orden = []
        ips_detalle = []
        dispositivos_orden = []
        dispositivos_detalle = []
        tokens_orden = []
        for reg in dia['todos']:
            ip_val = (getattr(reg, 'ip_address', None) or '').strip()
            if ip_val:
                if ip_val not in ips_orden:
                    ips_orden.append(ip_val)
                tipo_lbl = reg.get_tipo_display() if hasattr(reg, 'get_tipo_display') else reg.tipo
                ips_detalle.append(f"{tipo_lbl}: {ip_val}")

            disp_val = (getattr(reg, 'dispositivo_nombre', None) or '').strip()
            tok_val = (getattr(reg, 'dispositivo_token', None) or '').strip()
            if disp_val:
                if disp_val not in dispositivos_orden:
                    dispositivos_orden.append(disp_val)
                tipo_lbl = reg.get_tipo_display() if hasattr(reg, 'get_tipo_display') else reg.tipo
                dispositivos_detalle.append(f"{tipo_lbl}: {disp_val}")
            if tok_val and tok_val not in tokens_orden:
                tokens_orden.append(tok_val)

        ip_principal = (getattr(ent, 'ip_address', None) or '').strip() if ent else ''
        if not ip_principal and ips_orden:
            ip_principal = ips_orden[0]

        dispositivo_principal = (getattr(ent, 'dispositivo_nombre', None) or '').strip() if ent else ''
        if not dispositivo_principal and dispositivos_orden:
            dispositivo_principal = dispositivos_orden[0]

        token_principal = (getattr(ent, 'dispositivo_token', None) or '').strip() if ent else ''
        if not token_principal and tokens_orden:
            token_principal = tokens_orden[0]
        token_corto = token_principal[:8].upper() if token_principal else ''

        es_turno_nocturno = False
        if ent and sal and timezone.localtime(sal.fecha_hora).date() > timezone.localtime(ent.fecha_hora).date():
            es_turno_nocturno = True
        elif ent and timezone.localtime(ent.fecha_hora).hour >= 18:
            es_turno_nocturno = True

        dia['es_turno_nocturno'] = es_turno_nocturno
        dia['tiempo_comida'] = _formatear_duracion(td_comida)
        dia['tiempo_bruto'] = _formatear_duracion(td_bruto)
        dia['tiempo_laborado'] = _formatear_duracion(td_laborado)
        dia['segundos_brutos'] = int(td_bruto.total_seconds()) if td_bruto else 0
        dia['segundos_laborados'] = int(td_laborado.total_seconds()) if td_laborado else 0
        dia['columnas_checadas'] = [ent, sal_com, reg_com, sal]
        dia['ip_principal'] = ip_principal
        dia['ips_extra_count'] = max(0, len(ips_orden) - 1)
        dia['ips_tooltip'] = ' | '.join(ips_detalle) if ips_detalle else 'Sin IP registrada'
        dia['ips_excel'] = ips_orden[0] if len(ips_orden) == 1 else (' | '.join(ips_detalle) if ips_detalle else '--')
        dia['dispositivo_principal'] = dispositivo_principal
        dia['dispositivo_token_corto'] = token_corto
        dia['dispositivos_tooltip'] = ' | '.join(dispositivos_detalle) if dispositivos_detalle else 'Sin dispositivo vinculado'
        dia['dispositivo_excel'] = dispositivos_orden[0] if len(dispositivos_orden) == 1 else (' | '.join(dispositivos_detalle) if dispositivos_detalle else '--')
        resumen_dias.append(dia)

    return resumen_dias, total_segundos_laborados


def _device_signer():
    return signing.Signer(salt='asistencia-device-v1')


def _cookie_dispositivo_name(empleado_id):
    return f"att_dev_{empleado_id}"


def _firmar_token_dispositivo(empleado_id, token_uuid):
    return _device_signer().sign(f"{empleado_id}:{token_uuid}")


def _leer_token_dispositivo_request(request, empleado):
    candidatos = [
        request.COOKIES.get(_cookie_dispositivo_name(empleado.id)),
        (request.POST.get('device_token') or '').strip(),
    ]
    signer = _device_signer()
    prefijo = f"{empleado.id}:"
    for raw in candidatos:
        if not raw:
            continue
        try:
            valor = signer.unsign(raw)
        except signing.BadSignature:
            continue
        if valor.startswith(prefijo):
            token = valor[len(prefijo):].strip()
            if token:
                return token
    return None


def _resumir_dispositivo(dispositivo_nombre_raw, user_agent):
    limpio = ' '.join((dispositivo_nombre_raw or '').split())[:150]
    if limpio:
        return limpio
    ua = (user_agent or '').lower()
    if 'iphone' in ua:
        os_name = 'iPhone'
    elif 'ipad' in ua:
        os_name = 'iPad'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'windows' in ua:
        os_name = 'Windows'
    elif 'mac os' in ua or 'macintosh' in ua:
        os_name = 'Mac'
    else:
        os_name = 'Navegador'

    if 'edg' in ua:
        browser = 'Edge'
    elif 'opr/' in ua or 'opera' in ua:
        browser = 'Opera'
    elif 'crios' in ua or ('chrome' in ua and 'chromium' not in ua):
        browser = 'Chrome'
    elif 'fxios' in ua or 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua:
        browser = 'Safari'
    else:
        browser = ''

    return f"{os_name} • {browser}" if browser else os_name


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


_MAX_TURNO_ABIERTO_HORAS = 24


def _obtener_jornada_activa(empleado, ahora=None):
    """Retorna (fecha_jornada, registros_jornada) soportando turnos diurnos y turnos nocturnos
    que inician en la tarde/noche y concluyen a la mañana siguiente.
    """
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)

    # 1. Buscar la última entrada laboral registrada dentro del umbral de apertura (máx 24h)
    limite_apertura = ahora - timedelta(hours=_MAX_TURNO_ABIERTO_HORAS)
    ultima_entrada = AsistenciaEmpleado.objects.filter(
        empleado=empleado,
        tipo='entrada_laboral',
        fecha_hora__gte=limite_apertura
    ).order_by('-fecha_hora').first()

    if ultima_entrada:
        # Verificar si esta entrada ya tuvo su salida laboral posterior
        salida_cierre = AsistenciaEmpleado.objects.filter(
            empleado=empleado,
            tipo='salida_laboral',
            fecha_hora__gt=ultima_entrada.fecha_hora
        ).order_by('fecha_hora').first()

        if not salida_cierre:
            # JORNADA ACTIVA EN CURSO (nocturna o diurna sin cerrar)
            registros_abiertos = list(
                AsistenciaEmpleado.objects.filter(
                    empleado=empleado,
                    fecha_hora__gte=ultima_entrada.fecha_hora
                ).order_by('fecha_hora')
            )
            fecha_jornada = timezone.localdate(ultima_entrada.fecha_hora)
            return fecha_jornada, registros_abiertos
        else:
            # La jornada ya fue cerrada con salida_laboral.
            # Si se cerró hace menos de 2 horas (ej. al marcar salida matutina),
            # mostramos el resumen de la jornada recién finalizada.
            if (ahora - salida_cierre.fecha_hora) <= timedelta(hours=2):
                registros_cerrados = list(
                    AsistenciaEmpleado.objects.filter(
                        empleado=empleado,
                        fecha_hora__gte=ultima_entrada.fecha_hora,
                        fecha_hora__lte=salida_cierre.fecha_hora
                    ).order_by('fecha_hora')
                )
                fecha_jornada = timezone.localdate(ultima_entrada.fecha_hora)
                return fecha_jornada, registros_cerrados

    # 2. Si no hay jornada abierta ni recién finalizada, retornar registros del día de hoy
    registros_hoy = list(
        AsistenciaEmpleado.objects.filter(empleado=empleado, fecha=hoy).order_by('fecha_hora')
    )
    return hoy, registros_hoy


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
            'salida_laboral',
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
    # salida_laboral:
    # La jornada finalizó, pero permitimos 'entrada_laboral' para iniciar el siguiente turno (ej. noche siguiente)
    hora_cierre = timezone.localtime(ultimo_registro.fecha_hora).strftime('%H:%M')
    return (
        'finalizada',
        f'Jornada finalizada ({hora_cierre})',
        'entrada_laboral',
        {'entrada_laboral'},
        ultimo_registro,
    )


def _mensaje_movimiento_no_permitido(estado_jornada, tipo):
    if estado_jornada == 'sin_iniciar':
        return 'Primero debes registrar tu Entrada Laboral antes de marcar comida o salida.'
    if estado_jornada == 'en_comida':
        return 'Estás en horario de comida. Primero debes registrar "Entrar de Comer".'
    if estado_jornada == 'finalizada' and tipo != 'entrada_laboral':
        return 'Tu jornada anterior ya fue finalizada. Registra Entrada Laboral para comenzar un nuevo turno.'
    if tipo == 'entrada_laboral' and estado_jornada in ('en_jornada', 'en_comida'):
        return 'Ya te encuentras dentro de una jornada laboral activa. Marca tu salida para concluirla.'
    return 'Este movimiento no corresponde al estado actual de tu jornada.'


@login_required(login_url='/login/')
def portal_asistencias_empleado(request):
    """Vista móvil simplificada (Reloj Checador) exclusiva para empleados."""
    empleado = getattr(request.user, 'empleado', None)
    if not empleado:
        return redirect('dashboard_inicio')

    empresa = empleado.empresa
    hoy = timezone.localdate()
    fecha_jornada, registros_hoy = _obtener_jornada_activa(empleado)
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
        'fecha_jornada': fecha_jornada,
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
    fecha_local, registros_hoy = _obtener_jornada_activa(empleado, ahora)
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

    user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:255]
    dispositivo_nombre = _resumir_dispositivo(request.POST.get('dispositivo_nombre'), user_agent)
    token_presentado = _leer_token_dispositivo_request(request, empleado)

    if empleado.dispositivo_token:
        if token_presentado != empleado.dispositivo_token:
            return JsonResponse({
                'success': False,
                'error': 'Este teléfono no está vinculado a tu cuenta. Si cambiaste de celular o usas otro navegador, solicita a Recursos Humanos desvincular tu dispositivo anterior.'
            }, status=403)
        token_final = empleado.dispositivo_token
        if dispositivo_nombre and dispositivo_nombre != empleado.dispositivo_nombre:
            empleado.dispositivo_nombre = dispositivo_nombre
            empleado.save(update_fields=['dispositivo_nombre'])
    else:
        token_final = uuid.uuid4().hex
        empleado.dispositivo_token = token_final
        empleado.dispositivo_nombre = dispositivo_nombre
        empleado.dispositivo_vinculado_en = ahora
        empleado.save(update_fields=['dispositivo_token', 'dispositivo_nombre', 'dispositivo_vinculado_en'])

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
        user_agent=user_agent,
        dispositivo_token=token_final,
        dispositivo_nombre=dispositivo_nombre,
    )

    signed_device_token = _firmar_token_dispositivo(empleado.id, token_final)
    hora_local = timezone.localtime(registro.fecha_hora)
    resp = JsonResponse({
        'success': True,
        'message': f'{registro.get_tipo_display()} registrada a las {hora_local.strftime("%H:%M:%S")}.',
        'signed_device_token': signed_device_token,
        'dispositivo_nombre': dispositivo_nombre,
        'dispositivo_token_corto': token_final[:8].upper(),
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
    resp.set_cookie(
        _cookie_dispositivo_name(empleado.id),
        signed_device_token,
        max_age=60 * 60 * 24 * 365 * 5,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure(),
    )
    return resp


def _parsear_rango_fechas(request):
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
    return fecha_inicio, fecha_fin


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

    fecha_inicio, fecha_fin = _parsear_rango_fechas(request)

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
        config_jornada = ConfiguracionJornadaLaboral.para_empresa(empresa_actual)
        _aplicar_calculo_jornada_dias(resumen_dias, config_jornada, tipo_turno=empleado.tipo_turno)
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


_ASISTENCIA_EXCEL_HEADERS_EMPRESA = [
    # 1. Datos del empleado (Negrito / Charcoal)
    "No. Empleado",
    "Nombre del Trabajador",
    "CURP",
    "RFC",
    "Puesto",
    "Departamento",
    # 2. Datos de registro y checadas (Azulito / Teal)
    "Dispositivo",
    "ID Dispositivo",
    "IP Registrada",
    "Fecha de Entrada",
    "Entrada Laboral",
    "Ubicación Entrada",
    "Salida a Comer",
    "Ubicación Salida Comer",
    "Regreso de Comer",
    "Ubicación Regreso Comer",
    "Fecha de Salida",
    "Salida Laboral",
    "Ubicación Salida",
    "Tipo de Turno",
    # 3. Horas y estatus (Negrito / Charcoal)
    "Tiempo Comida",
    "Horas Brutas",
    "Horas Netas",
    "Horas Ordinarias",
    "Horas Extras Dobles",
    "Horas Extras Triples",
    "Horas Excedentes",
    "Diferencia",
    "Cumplimiento",
    "Estatus",
]

_ASISTENCIA_EXCEL_HEADERS_BASE = _ASISTENCIA_EXCEL_HEADERS_EMPRESA[6:]

_ASISTENCIA_DARK_HEADERS = {
    "No. Empleado",
    "Nombre del Trabajador",
    "CURP",
    "RFC",
    "Puesto",
    "Departamento",
    "Tiempo Comida",
    "Horas Brutas",
    "Horas Netas",
    "Horas Ordinarias",
    "Horas Extras Dobles",
    "Horas Extras Triples",
    "Horas Excedentes",
    "Diferencia",
    "Cumplimiento",
    "Estatus",
}


def _fmt_horas_jornada(segundos):
    if not segundos or segundos <= 0:
        return '0h 00m'
    return _formatear_duracion(timedelta(seconds=segundos))


def _periodo_key_jornada(fecha_dia, periodo, dia_inicio):
    if periodo == 'diario':
        return fecha_dia
    if periodo == 'quincenal':
        return (fecha_dia.year, fecha_dia.month, 1 if fecha_dia.day <= 15 else 2)
    if periodo == 'mensual':
        return (fecha_dia.year, fecha_dia.month)
    # Semanal anclado en dia_inicio_semana (0=Lunes .. 6=Domingo)
    delta = (fecha_dia.weekday() - dia_inicio) % 7
    return fecha_dia - timedelta(days=delta)


def _aplicar_calculo_jornada_dias(resumen_dias, config_jornada, tipo_turno=None):
    """Clasifica las horas netas de cada día en ordinarias, extras dobles, extras triples y excedentes,
    calculando además la diferencia contra horario programado, cumplimiento porcentual y estatus de la jornada.
    Si el empleado tiene un tipo_turno asignado, se usan sus parámetros específicos; de lo contrario,
    se toman los globales de config_jornada.
    """
    if not resumen_dias:
        return resumen_dias

    if tipo_turno:
        ord_semanal_sec = max(0, int(round(float(tipo_turno.jornada_semanal_horas or 48) * 3600)))
        jornada_diaria_sec = max(0, int(round(float(tipo_turno.jornada_diaria_horas or 8) * 3600)))
        dob_limit_sec = max(0, int(round(float(tipo_turno.horas_dobles or 9) * 3600)))
        tri_limit_sec = max(0, int(round(float(tipo_turno.horas_triples_adicionales or 4) * 3600)))
        max_extra_dia_sec = max(0, int(round(float(tipo_turno.maximo_horas_extras_diario or 1) * 3600)))
        max_dias_extra = max(0, int(tipo_turno.maximo_dias_horas_extras or 1))
        tolerancia_sec = max(0, int(tipo_turno.tolerancia_entrada_minutos or 0) * 60)
        periodo = 'semanal'
        dia_inicio = int(tipo_turno.inicio_semana or 0) % 7
        turno_nombre = tipo_turno.nombre
    else:
        ord_semanal_sec = max(0, int(round(float(config_jornada.horas_ordinarias_semanales or 48) * 3600))) if config_jornada else 48 * 3600
        jornada_diaria_sec = int(round(ord_semanal_sec / 6)) if ord_semanal_sec > 0 else 8 * 3600
        dob_limit_sec = max(0, int(round(float(config_jornada.limite_horas_extras_dobles or 9) * 3600))) if config_jornada else 9 * 3600
        tri_limit_sec = max(0, int(round(float(config_jornada.limite_horas_extras_triples or 4) * 3600))) if config_jornada else 4 * 3600
        max_extra_dia_sec = max(0, int(round(float(config_jornada.maximo_horas_extras_dia or 5) * 3600))) if config_jornada else 5 * 3600
        max_dias_extra = max(0, int(config_jornada.maximo_dias_horas_extras or 5)) if config_jornada else 5
        tolerancia_sec = max(0, int(config_jornada.minutos_tolerancia or 10) * 60) if config_jornada else 10 * 60
        periodo = (config_jornada.periodo_acumulacion or 'semanal').lower() if config_jornada else 'semanal'
        dia_inicio = int(config_jornada.dia_inicio_semana or 0) % 7 if config_jornada else 0
        turno_nombre = 'General'

    if periodo == 'diario':
        period_ord_limit = ord_semanal_sec if ord_semanal_sec <= 86400 else (ord_semanal_sec // 6)
        period_factor = 1
    elif periodo == 'quincenal':
        period_ord_limit = ord_semanal_sec * 2
        period_factor = 2
    elif periodo == 'mensual':
        period_ord_limit = ord_semanal_sec * 4
        period_factor = 4
    else:
        period_ord_limit = ord_semanal_sec
        period_factor = 1

    period_dob_limit = dob_limit_sec * period_factor
    period_tri_limit = tri_limit_sec * period_factor

    estado_periodos = {}
    for dia in sorted(resumen_dias, key=lambda d: d['fecha']):
        key = _periodo_key_jornada(dia['fecha'], periodo, dia_inicio)
        st = estado_periodos.setdefault(key, {
            'ord_usado': 0,
            'dob_usado': 0,
            'tri_usado': 0,
            'dias_con_extra': 0,
        })

        net_sec = max(0, int(dia.get('segundos_laborados') or 0))
        ord_disp = max(0, period_ord_limit - st['ord_usado'])
        ord_sec = min(net_sec, ord_disp)
        st['ord_usado'] += ord_sec

        rem_sec = net_sec - ord_sec
        if 0 < rem_sec <= tolerancia_sec:
            rem_sec = 0

        dob_sec = 0
        tri_sec = 0
        exc_sec = 0

        if rem_sec > 0:
            if max_dias_extra > 0 and st['dias_con_extra'] >= max_dias_extra:
                exc_sec = rem_sec
            else:
                st['dias_con_extra'] += 1
                clasificable_sec = min(rem_sec, max_extra_dia_sec) if max_extra_dia_sec > 0 else rem_sec
                exc_sec = rem_sec - clasificable_sec

                dob_disp = max(0, period_dob_limit - st['dob_usado'])
                dob_sec = min(clasificable_sec, dob_disp)
                st['dob_usado'] += dob_sec

                rem_clas = clasificable_sec - dob_sec
                tri_disp = max(0, period_tri_limit - st['tri_usado'])
                tri_sec = min(rem_clas, tri_disp)
                st['tri_usado'] += tri_sec

                exc_sec += (rem_clas - tri_sec)

        dia['segundos_ordinarios'] = ord_sec
        dia['segundos_extras_dobles'] = dob_sec
        dia['segundos_extras_triples'] = tri_sec
        dia['segundos_excedentes'] = exc_sec
        dia['horas_ordinarias'] = _fmt_horas_jornada(ord_sec)
        dia['horas_extras_dobles'] = _fmt_horas_jornada(dob_sec)
        dia['horas_extras_triples'] = _fmt_horas_jornada(tri_sec)
        dia['horas_excedentes'] = _fmt_horas_jornada(exc_sec)

        # Nombre del turno
        if dia.get('es_turno_nocturno') and 'nocturno' not in turno_nombre.lower():
            dia['tipo_turno_nombre'] = f"{turno_nombre} (Nocturno)"
        else:
            dia['tipo_turno_nombre'] = turno_nombre

        # 1. Diferencia "Tiempo trabajado contra programado"
        programado_sec = jornada_diaria_sec
        diff_sec = net_sec - programado_sec
        if net_sec == 0:
            if programado_sec > 0:
                dia['diferencia_tiempo'] = f"-{_formatear_duracion(timedelta(seconds=programado_sec))}"
            else:
                dia['diferencia_tiempo'] = "0h 00m"
        elif abs(diff_sec) < 60:
            dia['diferencia_tiempo'] = "0h 00m"
        elif diff_sec > 0:
            dia['diferencia_tiempo'] = f"+{_formatear_duracion(timedelta(seconds=diff_sec))}"
        else:
            dia['diferencia_tiempo'] = f"-{_formatear_duracion(timedelta(seconds=abs(diff_sec)))}"

        # 2. Cumplimiento "porcentaje de jornada"
        if programado_sec > 0:
            porc = round((net_sec / programado_sec) * 100, 1)
            dia['cumplimiento_porcentaje'] = f"{porc:.1f}%"
        else:
            dia['cumplimiento_porcentaje'] = "100.0%" if net_sec > 0 else "0.0%"

        # 3. Estatus "normal, excedida o incompleta"
        tiene_entrada = bool(dia.get('entrada_laboral'))
        tiene_salida = bool(dia.get('salida_laboral'))

        if tiene_entrada and not tiene_salida:
            dia['estatus_jornada'] = "Incompleta"
        elif net_sec == 0:
            dia['estatus_jornada'] = "Incompleta"
        elif net_sec > (programado_sec + tolerancia_sec) or (dob_sec + tri_sec + exc_sec > 0):
            dia['estatus_jornada'] = "Excedida"
        elif net_sec < (programado_sec - tolerancia_sec):
            dia['estatus_jornada'] = "Incompleta"
        else:
            dia['estatus_jornada'] = "Normal"

    return resumen_dias

    return resumen_dias


def _fmt_hora_excel(reg):
    return timezone.localtime(reg.fecha_hora).strftime("%H:%M:%S") if reg else "--"


def _fmt_gps_excel(reg):
    if reg and reg.latitud is not None and reg.longitud is not None:
        return f"{reg.latitud}, {reg.longitud}"
    return "--"


def _fila_dia_asistencia_excel(dia, emp=None):
    fecha_salida = "--"
    if dia.get('salida_laboral'):
        fecha_salida = timezone.localtime(dia['salida_laboral'].fecha_hora).strftime("%d/%m/%Y")

    turno_nombre = dia.get('tipo_turno_nombre')
    if not turno_nombre:
        if emp and getattr(emp, 'tipo_turno', None):
            turno_nombre = emp.tipo_turno.nombre
        else:
            turno_nombre = "General"
    if dia.get('es_turno_nocturno') and 'nocturno' not in turno_nombre.lower():
        turno_nombre = f"{turno_nombre} (Nocturno)"

    return [
        dia.get('dispositivo_excel', '--'),
        dia.get('dispositivo_token_corto') or '--',
        dia.get('ips_excel', '--'),
        dia['fecha'].strftime("%d/%m/%Y"),
        _fmt_hora_excel(dia.get('entrada_laboral')),
        _fmt_gps_excel(dia.get('entrada_laboral')),
        _fmt_hora_excel(dia.get('salida_comer')),
        _fmt_gps_excel(dia.get('salida_comer')),
        _fmt_hora_excel(dia.get('regreso_comer')),
        _fmt_gps_excel(dia.get('regreso_comer')),
        fecha_salida,
        _fmt_hora_excel(dia.get('salida_laboral')),
        _fmt_gps_excel(dia.get('salida_laboral')),
        turno_nombre,
        dia.get('tiempo_comida', '--'),
        dia.get('tiempo_bruto', '--'),
        dia.get('tiempo_laborado', '--'),
        dia.get('horas_ordinarias', '0h 00m'),
        dia.get('horas_extras_dobles', '0h 00m'),
        dia.get('horas_extras_triples', '0h 00m'),
        dia.get('horas_excedentes', '0h 00m'),
        dia.get('diferencia_tiempo', '0h 00m'),
        dia.get('cumplimiento_porcentaje', '0.0%'),
        dia.get('estatus_jornada', 'Normal'),
    ]


def _render_libro_asistencias_excel(titulo, subtitulo, headers, filas, filename, dark_headers=None, empty_message=None):
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
    dark_set = set(dark_headers if dark_headers is not None else _ASISTENCIA_DARK_HEADERS)

    ws['A1'] = titulo
    ws['A1'].font = font_title
    ws['A2'] = subtitulo
    ws['A2'].font = Font(size=10, color="475569")

    ws.append([])
    ws.append(headers)
    header_row = 4
    for col_idx, header_name in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.fill = fill_sub if header_name in dark_set else fill_brand
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    wrap_cols = {idx for idx, h in enumerate(headers, start=1) if h in ("IP Registrada", "Nombre del Trabajador")}
    left_cols = {idx for idx, h in enumerate(headers, start=1) if h in ("Nombre del Trabajador", "Puesto", "Departamento")}

    if filas:
        for row_idx, row_vals in enumerate(filas, start=header_row + 1):
            for col_idx, val in enumerate(row_vals, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.border = thin_border
                c.alignment = Alignment(
                    horizontal="left" if col_idx in left_cols else "center",
                    vertical="center",
                    wrap_text=(col_idx in wrap_cols),
                )
    elif empty_message:
        ws.merge_cells(start_row=header_row + 1, start_column=1, end_row=header_row + 1, end_column=len(headers))
        c = ws.cell(row=header_row + 1, column=1, value=empty_message)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.font = Font(italic=True, color="64748B")

    for col_idx, header_name in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        if header_name == "Dispositivo":
            max_len = max((len(str(row[col_idx - 1] or '')) for row in filas), default=len(header_name))
            ws.column_dimensions[col_letter].width = max(35, min(80, max_len + 4))
        elif header_name == "Nombre del Trabajador":
            ws.column_dimensions[col_letter].width = 30
        elif header_name in ("CURP", "RFC"):
            ws.column_dimensions[col_letter].width = 20
        elif header_name in ("Puesto", "Departamento", "Tipo de Turno"):
            ws.column_dimensions[col_letter].width = 22
        elif "Ubicación" in header_name or header_name == "IP Registrada":
            ws.column_dimensions[col_letter].width = 24
        elif header_name in ("Fecha de Entrada", "Fecha de Salida", "Entrada Laboral", "Salida Laboral", "Salida a Comer", "Regreso de Comer"):
            ws.column_dimensions[col_letter].width = 18
        elif header_name in ("Horas Extras Dobles", "Horas Extras Triples"):
            ws.column_dimensions[col_letter].width = 20
        else:
            ws.column_dimensions[col_letter].width = max(16, len(header_name) + 3)

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


def _exportar_asistencias_excel(empleado, resumen_dias, fecha_inicio, fecha_fin, total_horas_str):
    nombre_emp = f"{empleado.nombre} {empleado.apellido_paterno} {empleado.apellido_materno}".strip()
    titulo = f"Control de Asistencias - {nombre_emp}"
    subtitulo = (
        f"No. Empleado: {empleado.num_empleado or 'S/N'} | Puesto: {empleado.puesto or '--'} | "
        f"Depto: {empleado.departamento or '--'} | Periodo: {fecha_inicio:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} | "
        f"Total Laborado: {total_horas_str}"
    )
    prefijo = [
        empleado.num_empleado or '--',
        nombre_emp or '--',
        empleado.curp or '--',
        empleado.rfc or '--',
        empleado.puesto or '--',
        empleado.departamento or '--',
    ]
    filas = [prefijo + _fila_dia_asistencia_excel(dia, emp=empleado) for dia in resumen_dias]
    filename = f"Asistencias_{empleado.num_empleado or empleado.id}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.xlsx"
    return _render_libro_asistencias_excel(
        titulo,
        subtitulo,
        _ASISTENCIA_EXCEL_HEADERS_EMPRESA,
        filas,
        filename,
        dark_headers=_ASISTENCIA_DARK_HEADERS,
        empty_message="No se encontraron registros de asistencia para este empleado en el periodo seleccionado."
    )


def _exportar_asistencias_contratista_workbook(titulo, subtitulo, filename, empleados_con_dias):
    filas = []
    for emp, resumen_dias in empleados_con_dias:
        nombre_emp = f"{emp.nombre} {emp.apellido_paterno} {emp.apellido_materno}".strip()
        prefijo = [
            emp.num_empleado or '--',
            nombre_emp or '--',
            emp.curp or '--',
            emp.rfc or '--',
            emp.puesto or '--',
            emp.departamento or '--',
        ]
        for dia in resumen_dias:
            filas.append(prefijo + _fila_dia_asistencia_excel(dia, emp=emp))

    return _render_libro_asistencias_excel(
        titulo,
        subtitulo,
        _ASISTENCIA_EXCEL_HEADERS_EMPRESA,
        filas,
        filename,
        dark_headers=_ASISTENCIA_DARK_HEADERS,
        empty_message="No se encontraron registros de asistencia para los trabajadores en el periodo seleccionado.",
    )


@login_required(login_url='/login/')
@require_hr_permission('empleados', 'exportar_excel_asistencias')
def exportar_asistencias_contratista_excel(request):
    """Exporta a Excel las asistencias por contratista, por empleado o de toda la empresa."""
    empresa_actual = get_empresa_actual(request)
    contratista_id = (request.GET.get('contratista_id') or '').strip()
    empleado_id = (request.GET.get('empleado_id') or '').strip()
    fecha_inicio, fecha_fin = _parsear_rango_fechas(request)

    contratista = None
    empleado_unico = None

    if empleado_id:
        empleados = list(
            Empleado.objects.filter(empresa=empresa_actual, id=empleado_id)
            .select_related('tipo_turno', 'contratista')
        )
        if not empleados:
            messages.error(request, 'No se encontró el empleado seleccionado.')
            return redirect('lista_empleados')
        empleado_unico = empleados[0]
    elif contratista_id and contratista_id != 'todos':
        contratista = get_object_or_404(Contratista, id=contratista_id, empresa=empresa_actual)
        empleados = list(
            Empleado.objects.filter(empresa=empresa_actual, contratista=contratista)
            .select_related('tipo_turno', 'contratista')
            .order_by('apellido_paterno', 'apellido_materno', 'nombre')
        )
    else:
        # Toda la empresa
        empleados = list(
            Empleado.objects.filter(empresa=empresa_actual)
            .select_related('tipo_turno', 'contratista')
            .order_by('apellido_paterno', 'apellido_materno', 'nombre')
        )

    registros_qs = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado__in=empleados,
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
    ).order_by('empleado_id', 'fecha', 'fecha_hora')

    regs_por_empleado = defaultdict(list)
    for reg in registros_qs:
        regs_por_empleado[reg.empleado_id].append(reg)

    config_jornada = ConfiguracionJornadaLaboral.para_empresa(empresa_actual)
    empleados_con_dias = []
    total_segundos_global = 0
    for emp in empleados:
        resumen_dias, total_seg_emp = _agrupar_asistencias_por_dia(regs_por_empleado.get(emp.id, []))
        _aplicar_calculo_jornada_dias(resumen_dias, config_jornada, tipo_turno=emp.tipo_turno)
        total_segundos_global += total_seg_emp
        empleados_con_dias.append((emp, resumen_dias))

    total_horas_str = _formatear_duracion(timedelta(seconds=total_segundos_global))

    if empleado_unico:
        nombre_emp = f"{empleado_unico.nombre} {empleado_unico.apellido_paterno} {empleado_unico.apellido_materno}".strip()
        titulo = f"Reporte de Asistencias - {nombre_emp}"
        subtitulo = (
            f"No. Empleado: {empleado_unico.num_empleado or 'S/N'} | Puesto: {empleado_unico.puesto or '--'} | "
            f"Depto: {empleado_unico.departamento or '--'} | Periodo: {fecha_inicio:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} | "
            f"Total Laborado: {total_horas_str}"
        )
        filename = f"Asistencias_Empleado_{empleado_unico.num_empleado or empleado_unico.id}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.xlsx"
    elif contratista:
        titulo = f"Reporte de Asistencias por Contratista - {contratista.nombre_razon_social}"
        subtitulo = (
            f"RFC: {contratista.rfc or 'S/N'} | Trabajadores asignados: {len(empleados_con_dias)} | "
            f"Periodo: {fecha_inicio:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} | Total Laborado: {total_horas_str}"
        )
        filename = f"Asistencias_Contratista_{contratista.id}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.xlsx"
    else:
        titulo = f"Reporte General de Asistencias - {empresa_actual.nombre}"
        subtitulo = (
            f"Empresa: {empresa_actual.nombre} | Total Trabajadores: {len(empleados_con_dias)} | "
            f"Periodo: {fecha_inicio:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} | Total Laborado: {total_horas_str}"
        )
        filename = f"Asistencias_Empresa_{empresa_actual.id}_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}.xlsx"

    return _exportar_asistencias_contratista_workbook(
        titulo,
        subtitulo,
        filename,
        empleados_con_dias,
    )


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

    # Buscamos la jornada con _agrupar_asistencias_por_dia por si abarca registros del día siguiente (turno nocturno)
    registros_qs = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha__in=[fecha_obj, fecha_obj + timedelta(days=1)]
    ).order_by('fecha', 'fecha_hora')

    dias, _ = _agrupar_asistencias_por_dia(registros_qs)
    dia = next((d for d in dias if d['fecha'] == fecha_obj), None)

    if not dia or not dia.get('todos'):
        registros_directos = AsistenciaEmpleado.objects.filter(
            empresa=empresa_actual,
            empleado=empleado,
            fecha=fecha_obj
        )
        if not registros_directos.exists():
            return JsonResponse({'success': False, 'error': 'No se encontraron registros para la fecha indicada.'}, status=404)
        registros_a_eliminar = list(registros_directos)
    else:
        registros_a_eliminar = dia['todos']

    eliminados = len(registros_a_eliminar)
    for reg in registros_a_eliminar:
        if reg.foto:
            try:
                reg.foto.delete(save=False)
            except Exception:
                pass
        reg.delete()

    return JsonResponse({
        'success': True,
        'message': f'Se eliminaron {eliminados} registro(s) de la jornada del {fecha_obj.strftime("%d/%m/%Y")}. El empleado ya puede volver a registrar su asistencia.'
    })


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar_asistencias', json_response=True)
def desvincular_dispositivo_empleado_ajax(request, id):
    """Desvincula el token de teléfono autorizado del empleado para permitirle vincular uno nuevo."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(Empleado, id=id, empresa=empresa_actual)

    if not empleado.dispositivo_token:
        return JsonResponse({'success': False, 'error': 'Este empleado no tiene ningún teléfono vinculado actualmente.'}, status=400)

    empleado.dispositivo_token = None
    empleado.dispositivo_nombre = None
    empleado.dispositivo_vinculado_en = None
    empleado.save(update_fields=['dispositivo_token', 'dispositivo_nombre', 'dispositivo_vinculado_en'])

    return JsonResponse({
        'success': True,
        'message': 'Teléfono desvinculado correctamente. El próximo registro de asistencia vinculará el nuevo equipo.'
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

    # Buscamos registros de la fecha indicada y del día siguiente para capturar turnos nocturnos
    registros = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha__in=[fecha_obj, fecha_obj + timedelta(days=1)]
    ).order_by('fecha', 'fecha_hora')

    dias, _ = _agrupar_asistencias_por_dia(registros)
    dia = next((d for d in dias if d['fecha'] == fecha_obj), None)
    if not dia and dias:
        dia = dias[0]

    puede_ver_fotos = user_has_hr_permission(request, 'empleados', 'ver_fotos')
    movimientos = {}
    notas = ''
    for tipo in _TIPOS_ORDEN:
        reg = dia.get(tipo) if dia else None
        if reg:
            if not notas and reg.notas:
                notas = reg.notas
            loc_dt = timezone.localtime(reg.fecha_hora)
            es_dia_sig = loc_dt.date() > fecha_obj
            movimientos[tipo] = {
                'fecha': loc_dt.strftime('%Y-%m-%d'),
                'hora': loc_dt.strftime('%H:%M:%S'),
                'es_dia_siguiente': es_dia_sig,
                'latitud': str(reg.latitud) if reg.latitud is not None else '',
                'longitud': str(reg.longitud) if reg.longitud is not None else '',
                'foto_url': (reg.foto.url if reg.foto else '') if puede_ver_fotos else '',
            }
        else:
            movimientos[tipo] = {
                'fecha': fecha_obj.strftime('%Y-%m-%d'),
                'hora': '',
                'es_dia_siguiente': False,
                'latitud': '',
                'longitud': '',
                'foto_url': '',
            }

    return JsonResponse({
        'success': True,
        'data': {
            'fecha': fecha_obj.strftime('%Y-%m-%d'),
            'es_turno_nocturno': dia.get('es_turno_nocturno', False) if dia else False,
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

    registros_orig_qs = AsistenciaEmpleado.objects.filter(
        empresa=empresa_actual,
        empleado=empleado,
        fecha__in=[fecha_original, fecha_original + timedelta(days=1)]
    ).order_by('fecha', 'fecha_hora')
    dias, _ = _agrupar_asistencias_por_dia(registros_orig_qs)
    dia_orig = next((d for d in dias if d['fecha'] == fecha_original), {})

    al_menos_uno = False
    parsed_movimientos = {}
    for tipo in _TIPOS_ORDEN:
        hora_raw = (request.POST.get(f'{tipo}_hora') or '').strip()
        fecha_raw = (request.POST.get(f'{tipo}_fecha') or '').strip()
        if not hora_raw:
            parsed_movimientos[tipo] = None
            continue

        al_menos_uno = True
        hora_obj = _parsear_hora(hora_raw)
        if not hora_obj:
            return JsonResponse({'success': False, 'error': f'Hora inválida en {tipo.replace("_", " ")}.'}, status=400)

        fecha_mov = None
        if fecha_raw:
            try:
                fecha_mov = datetime.strptime(fecha_raw, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': f'Fecha inválida en {tipo.replace("_", " ")}.'}, status=400)

        lat, lng, gps_err = _parsear_coordenadas(
            request.POST.get(f'{tipo}_latitud'),
            request.POST.get(f'{tipo}_longitud'),
        )
        if gps_err:
            return JsonResponse({'success': False, 'error': gps_err}, status=400)

        parsed_movimientos[tipo] = {
            'hora': hora_obj,
            'fecha': fecha_mov,
            'lat': lat,
            'lng': lng,
        }

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
                    if reg_existente:
                        if reg_existente.foto:
                            reg_existente.foto.delete(save=False)
                        reg_existente.delete()
                    AsistenciaEmpleado.objects.filter(
                        empresa=empresa_actual,
                        empleado=empleado,
                        fecha=fecha_original,
                        tipo=tipo
                    ).delete()
                    continue

                hora_obj = datos_mov['hora']
                fecha_mov = datos_mov['fecha']
                lat = datos_mov['lat']
                lng = datos_mov['lng']

                if fecha_mov:
                    fecha_dt_real = fecha_mov
                else:
                    entrada_mov = parsed_movimientos.get('entrada_laboral')
                    fecha_dt_real = fecha_destino
                    if tipo != 'entrada_laboral' and entrada_mov and hora_obj < entrada_mov['hora']:
                        fecha_dt_real = fecha_destino + timedelta(days=1)

                aware_dt = timezone.make_aware(datetime.combine(fecha_dt_real, hora_obj), tz_actual)

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

                if reg_existente:
                    registros_orig_qs.filter(tipo=tipo).exclude(id=reg.id).delete()

        return JsonResponse({
            'success': True,
            'message': f'Asistencia del {fecha_destino.strftime("%d/%m/%Y")} actualizada correctamente.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al guardar la asistencia: {str(e)}'}, status=500)
