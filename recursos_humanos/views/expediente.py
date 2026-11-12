import mimetypes
import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from preferencias.permissions import require_hr_permission, user_has_hr_permission
from recursos_humanos.models import (
    DocumentoRequeridoEmpleado,
    Empleado,
    ExpedienteDigitalEmpleado,
)
from .beneficiaries import optimizar_archivo
from .utils import get_empresa_actual

_ALLOWED_EXPEDIENTE_EXTS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
_MAX_EXPEDIENTE_BYTES = 15 * 1024 * 1024  # 15 MB

_STATUS_LABELS = {
    'pendiente': 'Sin subir',
    'revision': 'En Revisión',
    'aprobado': 'Aprobado',
    'rechazado': 'Rechazado',
}


def _construir_listado_expediente(empresa, empleado):
    """Combina el catálogo configurable de documentos de la empresa con los archivos subidos del empleado."""
    requeridos = list(
        DocumentoRequeridoEmpleado.objects.filter(empresa=empresa, activo=True).order_by('orden', 'id')
    )
    subidos_qs = (
        ExpedienteDigitalEmpleado.objects.filter(empresa=empresa, empleado=empleado)
        .select_related('documento_requerido')
        .order_by('documento_requerido__orden', 'id')
    )
    subidos_map = {exp.documento_requerido_id: exp for exp in subidos_qs}

    seen_req_ids = set()
    items = []

    def _serialize_item(req_doc, exp):
        estatus = exp.estatus if exp else 'pendiente'
        nombre_archivo = ''
        ver_url = ''
        fecha_subida = ''
        if exp:
            nombre_archivo = exp.nombre_archivo or (os.path.basename(exp.archivo.name) if exp.archivo else '')
            ver_url = reverse('ver_documento_expediente_empleado', args=[exp.id])
            fecha_subida = timezone.localtime(exp.fecha_subida).strftime('%d/%m/%Y %H:%M')
        return {
            'doc_req_id': req_doc.id,
            'nombre': req_doc.nombre,
            'obligatorio': req_doc.obligatorio,
            'orden': req_doc.orden,
            'activo': req_doc.activo,
            'subido': exp is not None,
            'exp_id': exp.id if exp else None,
            'nombre_archivo': nombre_archivo,
            'estatus': estatus,
            'estatus_display': _STATUS_LABELS.get(estatus, estatus),
            'comentario_rechazo': (exp.comentario_rechazo or '') if exp else '',
            'fecha_subida': fecha_subida,
            'ver_url': ver_url,
        }

    for req_doc in requeridos:
        seen_req_ids.add(req_doc.id)
        items.append(_serialize_item(req_doc, subidos_map.get(req_doc.id)))

    # Conservar documentos ya subidos aunque posteriormente se hayan marcado inactivos en catálogo
    for req_id, exp in subidos_map.items():
        if req_id not in seen_req_ids:
            items.append(_serialize_item(exp.documento_requerido, exp))

    resumen = {
        'total': len(items),
        'subidos': sum(1 for it in items if it['subido']),
        'aprobados': sum(1 for it in items if it['estatus'] == 'aprobado'),
        'rechazados': sum(1 for it in items if it['estatus'] == 'rechazado'),
        'pendientes': sum(1 for it in items if not it['subido']),
    }
    return items, resumen


def _procesar_subida_expediente(request, empresa, empleado, es_empleado_portal=False):
    """Valida, optimiza y guarda el documento subido para un empleado."""
    req_id = (request.POST.get('documento_requerido_id') or '').strip()
    if not req_id:
        return JsonResponse({'success': False, 'error': 'Documento requerido no especificado.'}, status=400)

    req_doc = get_object_or_404(DocumentoRequeridoEmpleado, id=req_id, empresa=empresa)
    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'success': False, 'error': 'Debes seleccionar un archivo.'}, status=400)

    if archivo.size > _MAX_EXPEDIENTE_BYTES:
        return JsonResponse({'success': False, 'error': 'El archivo excede el tamaño máximo permitido (15 MB).'}, status=400)

    nombre_original = os.path.basename(archivo.name or 'documento')
    _, ext = os.path.splitext(nombre_original.lower())
    if ext not in _ALLOWED_EXPEDIENTE_EXTS:
        return JsonResponse({
            'success': False,
            'error': 'Formato no permitido. Solo se aceptan PDF o imágenes (.pdf, .jpg, .jpeg, .png, .webp).',
        }, status=400)

    archivo_opt = optimizar_archivo(archivo)
    exp, created = ExpedienteDigitalEmpleado.objects.get_or_create(
        empresa=empresa,
        empleado=empleado,
        documento_requerido=req_doc,
        defaults={
            'archivo': archivo_opt,
            'nombre_archivo': nombre_original[:255],
            'estatus': 'revision',
            'subido_por': request.user,
        },
    )

    if not created:
        if es_empleado_portal and exp.estatus == 'aprobado':
            return JsonResponse({
                'success': False,
                'error': 'Este documento ya fue aprobado y no puede modificarse desde el portal.',
            }, status=403)
        if exp.archivo:
            try:
                if os.path.isfile(exp.archivo.path):
                    os.remove(exp.archivo.path)
            except Exception:
                pass
        exp.archivo = archivo_opt
        exp.nombre_archivo = nombre_original[:255]
        exp.estatus = 'revision'
        exp.comentario_rechazo = ''
        exp.subido_por = request.user
        exp.save()

    return JsonResponse({
        'success': True,
        'message': f'"{req_doc.nombre}" guardado correctamente en el expediente.',
        'exp_id': exp.id,
        'ver_url': reverse('ver_documento_expediente_empleado', args=[exp.id]),
    })


@login_required(login_url='/login/')
def portal_expediente_empleado(request):
    """Submódulo en el portal del trabajador para consultar y subir su expediente digital."""
    if not hasattr(request.user, 'empleado'):
        return redirect('dashboard_inicio')

    empleado = request.user.empleado
    empresa_actual = empleado.empresa or get_empresa_actual(request)
    items, resumen = _construir_listado_expediente(empresa_actual, empleado)

    return render(request, 'recursos_humanos/portal_expediente_empleado.html', {
        'empresa': empresa_actual,
        'empleado': empleado,
        'items_expediente': items,
        'resumen_expediente': resumen,
    })


@login_required(login_url='/login/')
@require_POST
def portal_subir_documento_expediente_ajax(request):
    """Permite al empleado logueado subir o actualizar un documento en su expediente digital."""
    if not hasattr(request.user, 'empleado'):
        return JsonResponse({'success': False, 'error': 'Acceso exclusivo para empleados.'}, status=403)

    empleado = request.user.empleado
    empresa_actual = empleado.empresa or get_empresa_actual(request)
    return _procesar_subida_expediente(request, empresa_actual, empleado, es_empleado_portal=True)


@login_required(login_url='/login/')
def ver_documento_expediente_empleado(request, doc_id):
    """Sirve de forma segura un documento del expediente digital para visualización o descarga."""
    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(ExpedienteDigitalEmpleado.objects.select_related('empleado'), id=doc_id)

    if hasattr(request.user, 'empleado') and not request.user.is_staff and not request.user.is_superuser:
        if doc.empleado_id != request.user.empleado.id:
            raise PermissionDenied('Acceso denegado: este documento no pertenece a tu expediente.')
    else:
        if doc.empresa != empresa_actual:
            raise PermissionDenied('Acceso denegado: este documento no pertenece a tu empresa.')
        if not user_has_hr_permission(request, 'empleados', 'ver'):
            raise PermissionDenied('Acceso denegado: no cuentas con permisos en Empleados.')

    if not doc.archivo or not os.path.isfile(doc.archivo.path):
        raise Http404('El archivo físico no fue encontrado en el servidor.')

    mime_type, _ = mimetypes.guess_type(doc.archivo.path)
    descargar = request.GET.get('download') == '1'
    response = FileResponse(
        open(doc.archivo.path, 'rb'),
        content_type=mime_type or 'application/octet-stream',
        as_attachment=descargar,
        filename=doc.nombre_archivo or os.path.basename(doc.archivo.path),
    )
    return response


@login_required(login_url='/login/')
@require_hr_permission('empleados', 'ver')
def obtener_expediente_empleado_json(request, id):
    """Retorna el listado configurado y documentos cargados del empleado para el modal administrativo."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(Empleado, id=id, empresa=empresa_actual)
    items, resumen = _construir_listado_expediente(empresa_actual, empleado)
    nombre_completo = f"{empleado.nombre} {empleado.apellido_paterno} {empleado.apellido_materno}".strip()

    return JsonResponse({
        'success': True,
        'empleado': {
            'id': empleado.id,
            'nombre': nombre_completo,
            'num_empleado': empleado.num_empleado or 'S/N',
            'curp': empleado.curp or '--',
        },
        'items': items,
        'resumen': resumen,
    })


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar')
def subir_documento_expediente_admin_ajax(request, id):
    """Permite al personal de RH subir o reemplazar un documento en el expediente de un empleado."""
    empresa_actual = get_empresa_actual(request)
    empleado = get_object_or_404(Empleado, id=id, empresa=empresa_actual)
    return _procesar_subida_expediente(request, empresa_actual, empleado, es_empleado_portal=False)


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar')
def rechazar_documento_expediente_ajax(request, doc_id):
    """Marca un documento del expediente del empleado como rechazado con un motivo."""
    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(ExpedienteDigitalEmpleado, id=doc_id, empresa=empresa_actual)
    motivo = ' '.join((request.POST.get('motivo') or request.POST.get('comentario_rechazo') or '').split())
    if not motivo:
        return JsonResponse({'success': False, 'error': 'Indica el motivo de rechazo para que el trabajador pueda corregirlo.'}, status=400)

    doc.estatus = 'rechazado'
    doc.comentario_rechazo = motivo
    doc.save(update_fields=['estatus', 'comentario_rechazo'])
    return JsonResponse({'success': True, 'message': 'Documento marcado como rechazado.'})


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'editar')
def aprobar_documento_expediente_ajax(request, doc_id):
    """Marca un documento del expediente del empleado como aprobado."""
    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(ExpedienteDigitalEmpleado, id=doc_id, empresa=empresa_actual)
    doc.estatus = 'aprobado'
    doc.comentario_rechazo = ''
    doc.save(update_fields=['estatus', 'comentario_rechazo'])
    return JsonResponse({'success': True, 'message': 'Documento aprobado correctamente.'})


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('empleados', 'eliminar')
def eliminar_documento_expediente_ajax(request, doc_id):
    """Elimina un documento cargado del expediente digital del empleado."""
    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(ExpedienteDigitalEmpleado, id=doc_id, empresa=empresa_actual)
    doc.delete()
    return JsonResponse({'success': True, 'message': 'Documento eliminado del expediente.'})
