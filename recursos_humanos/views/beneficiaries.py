from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q, Count

from ..models import Beneficiario
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver')
def lista_beneficiarios(request):
    empresa_actual = get_empresa_actual(request)
    beneficiarios = Beneficiario.objects.filter(empresa=empresa_actual).annotate(total_empleados=Count('empleado')).order_by('nombre_razon_social')
    
    q = request.GET.get('q', '')
    f_razon = request.GET.get('razon_social', '')
    f_rfc = request.GET.get('rfc', '')
    f_clave = request.GET.get('clave', '')
    f_cont = request.GET.get('contacto', '')
    f_rp = request.GET.get('reg_patronal', '')
    sucursal_id = request.GET.get('sucursal', '')

    if q:
        beneficiarios = beneficiarios.filter(
            Q(nombre_razon_social__icontains=q) | 
            Q(rfc__icontains=q) | 
            Q(correo__icontains=q) |
            Q(clave__icontains=q)
        )
    
    if f_razon:
        beneficiarios = beneficiarios.filter(nombre_razon_social__icontains=f_razon)
    if f_rfc:
        beneficiarios = beneficiarios.filter(rfc__icontains=f_rfc)
    if f_clave:
        beneficiarios = beneficiarios.filter(clave__icontains=f_clave)
    if f_cont:
        beneficiarios = beneficiarios.filter(Q(correo__icontains=f_cont) | Q(telefono__icontains=f_cont))
    if f_rp:
        beneficiarios = beneficiarios.filter(registro_patronal__icontains=f_rp)
    if sucursal_id:
        beneficiarios = beneficiarios.filter(sucursal_id=sucursal_id)

    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    
    # PAGINACIÓN
    paginator = Paginator(beneficiarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'recursos_humanos/lista_beneficiarios.html', {
        'page_obj': page_obj, 
        'sucursales': sucursales, 
        'empresa': empresa_actual, 
        'filtros': {
            'q': q, 
            'razon_social': f_razon, 
            'rfc': f_rfc, 
            'clave': f_clave, 
            'contacto': f_cont, 
            'reg_patronal': f_rp, 
            'sucursal': sucursal_id
        }
    })

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver', json_response=True)
def obtener_beneficiario_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        data = {
            'id': ben.id, 'clave': ben.clave or '', 'rfc': ben.rfc, 'nombre_razon_social': ben.nombre_razon_social,
            'registro_patronal': ben.registro_patronal, 'calle': ben.calle, 'num_ext': ben.num_ext,
            'num_int': ben.num_int, 'entre_calle': ben.entre_calle, 'y_calle': ben.y_calle,
            'colonia': ben.colonia, 'cp': ben.cp, 'municipio_alcaldia': ben.municipio_alcaldia,
            'entidad_federativa': ben.entidad_federativa, 'correo': ben.correo, 'telefono': ben.telefono,
        }
        return JsonResponse({'success': True, 'data': data})
    except Beneficiario.DoesNotExist: return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'crear', json_response=True)
def crear_beneficiario_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual: return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)
    try:
        data = request.POST; sucursal_id = request.session.get('sucursal_id')
        nuevo = Beneficiario(
            empresa=empresa_actual, sucursal_id=sucursal_id, 
            clave=data.get('clave', ''),
            rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'), registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'), num_ext=data.get('num_ext'), num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'), y_calle=data.get('y_calle'), colonia=data.get('colonia'),
            cp=data.get('cp'), municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'), correo=data.get('correo'), telefono=data.get('telefono'),
        )
        nuevo.save()
        return JsonResponse({'success': True, 'message': 'Beneficiario registrado correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'editar', json_response=True)
def editar_beneficiario_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        data = request.POST
        ben.clave = data.get('clave', '')
        ben.rfc = data.get('rfc', '').upper(); ben.nombre_razon_social = data.get('nombre_razon_social')
        ben.registro_patronal = data.get('registro_patronal'); ben.calle = data.get('calle')
        ben.num_ext = data.get('num_ext'); ben.num_int = data.get('num_int')
        ben.entre_calle = data.get('entre_calle'); ben.y_calle = data.get('y_calle')
        ben.colonia = data.get('colonia'); ben.cp = data.get('cp')
        ben.municipio_alcaldia = data.get('municipio_alcaldia'); ben.entidad_federativa = data.get('entidad_federativa')
        ben.correo = data.get('correo'); ben.telefono = data.get('telefono')
        ben.save()
        return JsonResponse({'success': True, 'message': 'Beneficiario actualizado correctamente.'})
    except Beneficiario.DoesNotExist: return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('beneficiarios', 'eliminar', json_response=True)
def eliminar_beneficiario_ajax(request, id):
    """Eliminar un beneficiario."""
    empresa_actual = get_empresa_actual(request)
    try:
        ben = Beneficiario.objects.get(id=id, empresa=empresa_actual)
        ben.delete()
        return JsonResponse({'success': True, 'message': 'Beneficiario eliminado correctamente.'})
    except Beneficiario.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
