from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from preferencias.permissions import require_hr_permission
from ..models import Empleado, TipoTurno
from .utils import get_empresa_actual


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar', json_response=True)
def guardar_tipo_turno_ajax(request):
    """Crea o edita un Tipo de Turno para la empresa."""
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'}, status=400)

    data = request.POST
    turno_id = (data.get('turno_id') or '').strip()
    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return JsonResponse({'success': False, 'error': 'El nombre del turno es obligatorio.'}, status=400)

    try:
        if turno_id:
            turno = get_object_or_404(TipoTurno, id=turno_id, empresa=empresa_actual)
        else:
            turno = TipoTurno(empresa=empresa_actual)

        turno.nombre = nombre
        turno.descripcion = (data.get('descripcion') or '').strip()
        turno.activo = data.get('activo') in ('true', '1', 'on', True)

        # 1. Horario
        turno.hora_entrada = data.get('hora_entrada') or '08:00'
        turno.hora_salida_comida = data.get('hora_salida_comida') or None
        turno.hora_regreso_comida = data.get('hora_regreso_comida') or None
        turno.hora_salida = data.get('hora_salida') or '17:00'

        # 2. Configuración de jornada
        turno.jornada_diaria_horas = Decimal(str(data.get('jornada_diaria_horas') or '8.00'))
        turno.jornada_semanal_horas = (turno.jornada_diaria_horas * Decimal('6.00')).quantize(Decimal('0.01'))
        turno.inicio_semana = int(data.get('inicio_semana') or 0)
        turno.tiempo_comida_minutos = int(data.get('tiempo_comida_minutos') or 60)
        turno.comida_computable = data.get('comida_computable') in ('true', '1', 'on', True)

        # 3. Horas extraordinarias
        turno.horas_dobles = Decimal(str(data.get('horas_dobles') or '9.00'))
        turno.horas_triples_adicionales = Decimal(str(data.get('horas_triples_adicionales') or '4.00'))
        turno.maximo_horas_extras_diario = Decimal(str(data.get('maximo_horas_extras_diario') or '1.00'))
        turno.maximo_dias_horas_extras = int(data.get('maximo_dias_horas_extras') or 1)

        # 4. Control de asistencia
        turno.tolerancia_entrada_minutos = int(data.get('tolerancia_entrada_minutos') or 10)
        turno.tolerancia_salida_minutos = int(data.get('tolerancia_salida_minutos') or 0)

        turno.save()
        return JsonResponse({
            'success': True,
            'message': f'Tipo de turno "{turno.nombre}" guardado correctamente.',
            'turno': {
                'id': turno.id,
                'nombre': turno.nombre,
                'hora_entrada': turno.hora_entrada.strftime('%H:%M') if hasattr(turno.hora_entrada, 'strftime') else str(turno.hora_entrada),
                'hora_salida': turno.hora_salida.strftime('%H:%M') if hasattr(turno.hora_salida, 'strftime') else str(turno.hora_salida),
                'jornada_diaria': float(turno.jornada_diaria_horas),
                'jornada_semanal': float(turno.jornada_semanal_horas),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al guardar el turno: {str(e)}'}, status=500)


@login_required(login_url='/login/')
@require_GET
@require_hr_permission('empleados', 'ver', json_response=True)
def obtener_tipo_turno_json(request, id):
    """Retorna los datos de un tipo de turno en JSON para rellenar el modal."""
    empresa_actual = get_empresa_actual(request)
    turno = get_object_or_404(TipoTurno, id=id, empresa=empresa_actual)
    return JsonResponse({
        'success': True,
        'id': turno.id,
        'nombre': turno.nombre,
        'descripcion': turno.descripcion or '',
        'activo': turno.activo,
        'hora_entrada': turno.hora_entrada.strftime('%H:%M') if hasattr(turno.hora_entrada, 'strftime') else str(turno.hora_entrada),
        'hora_salida_comida': turno.hora_salida_comida.strftime('%H:%M') if turno.hora_salida_comida and hasattr(turno.hora_salida_comida, 'strftime') else (str(turno.hora_salida_comida) if turno.hora_salida_comida else ''),
        'hora_regreso_comida': turno.hora_regreso_comida.strftime('%H:%M') if turno.hora_regreso_comida and hasattr(turno.hora_regreso_comida, 'strftime') else (str(turno.hora_regreso_comida) if turno.hora_regreso_comida else ''),
        'hora_salida': turno.hora_salida.strftime('%H:%M') if hasattr(turno.hora_salida, 'strftime') else str(turno.hora_salida),
        'jornada_diaria_horas': str(turno.jornada_diaria_horas),
        'jornada_semanal_horas': str(turno.jornada_semanal_horas),
        'inicio_semana': turno.inicio_semana,
        'tiempo_comida_minutos': turno.tiempo_comida_minutos,
        'comida_computable': turno.comida_computable,
        'horas_dobles': str(turno.horas_dobles),
        'horas_triples_adicionales': str(turno.horas_triples_adicionales),
        'maximo_horas_extras_diario': str(turno.maximo_horas_extras_diario),
        'maximo_dias_horas_extras': turno.maximo_dias_horas_extras,
        'tolerancia_entrada_minutos': turno.tolerancia_entrada_minutos,
        'tolerancia_salida_minutos': turno.tolerancia_salida_minutos,
    })


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'eliminar', json_response=True)
def eliminar_tipo_turno_ajax(request, id):
    """Elimina un tipo de turno y desasocia a los empleados vinculados."""
    empresa_actual = get_empresa_actual(request)
    turno = get_object_or_404(TipoTurno, id=id, empresa=empresa_actual)
    nombre = turno.nombre
    Empleado.objects.filter(empresa=empresa_actual, tipo_turno=turno).update(tipo_turno=None)
    turno.delete()
    return JsonResponse({'success': True, 'message': f'Tipo de turno "{nombre}" eliminado correctamente.'})
