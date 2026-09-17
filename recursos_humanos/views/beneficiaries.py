from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.contrib.auth.models import User
from datetime import datetime

from ..models import Beneficiario, DocumentacionBeneficiario
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission, user_has_hr_permission
from .utils import get_empresa_actual
from notificaciones.utils import crear_notificacion

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
    sucursal_id = request.GET.get('sucursal')
    if sucursal_id is None:
        sucursal_id = str(request.session.get('sucursal_id') or '')

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
    
    # Obtener valores únicos para los filtros desplegables de beneficiarios
    razones_sociales_unicas = Beneficiario.objects.filter(empresa=empresa_actual).exclude(nombre_razon_social='').values_list('nombre_razon_social', flat=True).distinct().order_by('nombre_razon_social')
    rfcs_unicos = Beneficiario.objects.filter(empresa=empresa_actual).exclude(rfc='').values_list('rfc', flat=True).distinct().order_by('rfc')
    reg_patronales_unicos = Beneficiario.objects.filter(empresa=empresa_actual).exclude(registro_patronal='').values_list('registro_patronal', flat=True).distinct().order_by('registro_patronal')

    # PAGINACIÓN
    paginator = Paginator(beneficiarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'recursos_humanos/lista_beneficiarios.html', {
        'page_obj': page_obj, 
        'sucursales': sucursales, 
        'empresa': empresa_actual, 
        'anios_lista': [2024, 2025, 2026],
        'razones_sociales_unicas': razones_sociales_unicas,
        'rfcs_unicos': rfcs_unicos,
        'reg_patronales_unicos': reg_patronales_unicos,
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
        usuario_portal = ''
        if ben.usuario_id:
            try:
                usuario_portal = ben.usuario.username.split('@')[0]
            except User.DoesNotExist:
                ben.usuario = None
                ben.save()
        data = {
            'id': ben.id, 'clave': ben.clave or '', 'rfc': ben.rfc, 'nombre_razon_social': ben.nombre_razon_social,
            'registro_patronal': ben.registro_patronal, 'calle': ben.calle, 'num_ext': ben.num_ext,
            'num_int': ben.num_int, 'entre_calle': ben.entre_calle, 'y_calle': ben.y_calle,
            'colonia': ben.colonia, 'cp': ben.cp, 'municipio_alcaldia': ben.municipio_alcaldia,
            'entidad_federativa': ben.entidad_federativa, 'correo': ben.correo, 'telefono': ben.telefono,
            'usuario_portal': usuario_portal
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
        usuario_portal = data.get('usuario_portal', '').strip()
        password_portal = data.get('password_portal', '').strip()

        user_obj = None
        if usuario_portal:
            if not password_portal:
                return JsonResponse({'success': False, 'error': 'La contraseña es obligatoria si se define un usuario de acceso.'})
            username_completo = f"{usuario_portal}@{empresa_actual.subdominio}"
            if User.objects.filter(username=username_completo).exists():
                return JsonResponse({'success': False, 'error': f'El usuario {username_completo} ya existe.'})
            user_obj = User.objects.create_user(username=username_completo, email=data.get('correo'), password=password_portal)

        nuevo = Beneficiario(
            empresa=empresa_actual, sucursal_id=sucursal_id, 
            clave=data.get('clave', ''),
            rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'), registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'), num_ext=data.get('num_ext'), num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'), y_calle=data.get('y_calle'), colonia=data.get('colonia'),
            cp=data.get('cp'), municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'), correo=data.get('correo'), telefono=data.get('telefono'),
            usuario=user_obj,
            creado_por=request.user
        )
        nuevo.save()
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'creó al beneficiario {nuevo.nombre_razon_social}',
            link='/recursos-humanos/beneficiarios/',
            propietario=request.user
        )
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
        usuario_portal = data.get('usuario_portal', '').strip()
        password_portal = data.get('password_portal', '').strip()

        # LOG DE DIAGNÓSTICO
        import json
        try:
            with open(r"c:\Users\luism\gemini-work\sistema_inventario\post_debug.json", "w", encoding="utf-8") as f:
                json.dump({k: data.get(k) for k in data.keys() if 'password' not in k}, f, indent=4)
        except Exception:
            pass

        if usuario_portal:
            username_completo = f"{usuario_portal}@{empresa_actual.subdominio}"
            existing_user = User.objects.filter(username=username_completo).exclude(id=ben.usuario_id).first() if ben.usuario_id else User.objects.filter(username=username_completo).first()
            if existing_user:
                return JsonResponse({'success': False, 'error': f'El usuario {username_completo} ya existe.'})
            
            user_obj = None
            if ben.usuario_id:
                try:
                    user_obj = ben.usuario
                except User.DoesNotExist:
                    pass
            
            if user_obj:
                user_obj.username = username_completo
                user_obj.email = data.get('correo')
                if password_portal:
                    user_obj.set_password(password_portal)
                user_obj.save()
            else:
                if not password_portal:
                    return JsonResponse({'success': False, 'error': 'La contraseña es obligatoria para un usuario nuevo.'})
                user_obj = User.objects.create_user(username=username_completo, email=data.get('correo'), password=password_portal)
                ben.usuario = user_obj
        else:
            if ben.usuario_id:
                try:
                    old_user = ben.usuario
                    old_user.delete()
                except User.DoesNotExist:
                    pass
                ben.usuario = None

        ben.clave = data.get('clave', '')
        ben.rfc = data.get('rfc', '').upper(); ben.nombre_razon_social = data.get('nombre_razon_social')
        ben.registro_patronal = data.get('registro_patronal'); ben.calle = data.get('calle')
        ben.num_ext = data.get('num_ext'); ben.num_int = data.get('num_int')
        ben.entre_calle = data.get('entre_calle'); ben.y_calle = data.get('y_calle')
        ben.colonia = data.get('colonia'); ben.cp = data.get('cp')
        ben.municipio_alcaldia = data.get('municipio_alcaldia'); ben.entidad_federativa = data.get('entidad_federativa')
        ben.correo = data.get('correo'); ben.telefono = data.get('telefono')
        ben.save()
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'editó al beneficiario {ben.nombre_razon_social}',
            link='/recursos-humanos/beneficiarios/',
            propietario=ben.creado_por or request.user
        )
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
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'eliminó al beneficiario {ben.nombre_razon_social}',
            link='/recursos-humanos/beneficiarios/',
            propietario=ben.creado_por or request.user
        )
        ben.delete()
        return JsonResponse({'success': True, 'message': 'Beneficiario eliminado correctamente.'})
    except Beneficiario.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Beneficiario no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

import os
import io
from PIL import Image
from django.core.files.base import ContentFile

def optimizar_archivo(archivo_original):
    """
    Optimiza el archivo subido para ahorrar espacio en disco sin perder calidad perceptible.
    - Imágenes: Convierte a WEBP con calidad 85.
    """
    nombre, extension = os.path.splitext(archivo_original.name)
    extension = extension.lower()
    
    if extension in ['.jpg', '.jpeg', '.png', '.bmp']:
        try:
            img = Image.open(archivo_original)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')
                
            output = io.BytesIO()
            img.save(output, format='WEBP', quality=85, optimize=True)
            output.seek(0)
            return ContentFile(output.read(), name=f"{nombre}.webp")
        except Exception:
            return archivo_original
    
    return archivo_original

@login_required(login_url='/login/')
def obtener_documentacion_json(request, id):
    empresa_actual = get_empresa_actual(request)
    is_self = hasattr(request.user, 'beneficiario') and request.user.beneficiario.id == id
    if not is_self:
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion') and not user_has_hr_permission(request, 'beneficiarios', 'ver'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)
        
    ben = get_object_or_404(Beneficiario, id=id, empresa=empresa_actual)
    
    try:
        anio = int(request.GET.get('anio') or datetime.now().year)
    except ValueError:
        anio = datetime.now().year
        
    docs_existentes = DocumentacionBeneficiario.objects.filter(beneficiario=ben, anio=anio)
    
    catalogo = DocumentacionBeneficiario.CATALOGO_DOCUMENTOS
    
    meses_nombres = [
        ('Ene', 'Enero'), ('Feb', 'Febrero'), ('Mar', 'Marzo'), ('Abr', 'Abril'),
        ('May', 'Mayo'), ('Jun', 'Junio'), ('Jul', 'Julio'), ('Ago', 'Agosto'),
        ('Sep', 'Septiembre'), ('Oct', 'Octubre'), ('Nov', 'Noviembre'), ('Dic', 'Diciembre')
    ]
    
    bimestres_nombres = [
        ('1er Bim', '1er Bimestre (Ene - Feb)'),
        ('2do Bim', '2do Bimestre (Mar - Abr)'),
        ('3er Bim', '3er Bimestre (May - Jun)'),
        ('4to Bim', '4to Bimestre (Jul - Ago)'),
        ('5to Bim', '5to Bimestre (Sep - Oct)'),
        ('6to Bim', '6to Bimestre (Nov - Dic)')
    ]
    
    cuatrimestres_nombres = [
        ('1er Cuatrimestre', '1er Cuatrimestre (Ene - Abr)'),
        ('2do Cuatrimestre', '2do Cuatrimestre (May - Ago)'),
        ('3er Cuatrimestre', '3er Cuatrimestre (Sep - Dic)')
    ]
    
    matrix = []
    totales_resumen = {
        'aprobados': 0,
        'revision': 0,
        'rechazados': 0,
        'vacio': 0,
        'total_requeridos': 0
    }
    
    for item in catalogo:
        code = item['codigo']
        nombre = item['nombre']
        periodo = item['periodo']
        badge = item['badge']
        num_periodos = item['num_periodos']
        
        periodos_list = []
        for p in range(1, num_periodos + 1):
            totales_resumen['total_requeridos'] += 1
            if periodo == 'mensual':
                colspan = 1
                short_lbl = meses_nombres[p - 1][0]
                full_lbl = meses_nombres[p - 1][1]
            elif periodo == 'bimestral':
                colspan = 2
                short_lbl = bimestres_nombres[p - 1][0]
                full_lbl = bimestres_nombres[p - 1][1]
            elif periodo == 'cuatrimestral':
                colspan = 4
                short_lbl = cuatrimestres_nombres[p - 1][0]
                full_lbl = cuatrimestres_nombres[p - 1][1]
            else: # unica_ocasion
                colspan = 12
                short_lbl = 'Única ocasión'
                full_lbl = 'Documento de Única Ocasión'
                
            doc = docs_existentes.filter(Q(nombre_documento=code) | (Q(nombre_documento='REPSE') if code == 'REPSE_VIGENTE' else Q(pk__isnull=True)), mes=p).first()
            if doc:
                if doc.estatus == 'aprobado':
                    totales_resumen['aprobados'] += 1
                elif doc.estatus == 'revision':
                    totales_resumen['revision'] += 1
                elif doc.estatus == 'rechazado':
                    totales_resumen['rechazados'] += 1
            else:
                totales_resumen['vacio'] += 1
                
            from django.urls import reverse
            periodos_list.append({
                'num': p,
                'colspan': colspan,
                'short_label': short_lbl,
                'label': full_lbl,
                'id': doc.id if doc else None,
                'url': reverse('descargar_documento_beneficiario', args=[doc.id]) if doc else None,
                'nombre_archivo': doc.archivo.name.split('/')[-1] if doc else None,
                'estatus': doc.estatus if doc else None,
                'estatus_display': doc.get_estatus_display() if doc else None,
                'comentario_rechazo': (doc.comentario_rechazo or '') if doc else ''
            })
            
        matrix.append({
            'codigo': code,
            'nombre': nombre,
            'periodo': periodo,
            'formato': item.get('formato', 'pdf'),
            'badge': badge,
            'num_periodos': num_periodos,
            'periodos': periodos_list
        })
        
    return JsonResponse({
        'success': True,
        'beneficiario': ben.nombre_razon_social,
        'anio': anio,
        'matrix': matrix,
        'resumen': totales_resumen
    })

@login_required(login_url='/login/')
@require_POST
def subir_documento_ajax(request, id):
    import os
    empresa_actual = get_empresa_actual(request)
    if hasattr(request.user, 'beneficiario') and request.user.beneficiario.id == id:
        ben = request.user.beneficiario
    else:
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion_subir') and not user_has_hr_permission(request, 'beneficiarios', 'documentacion'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para subir documentos.'}, status=403)
        ben = get_object_or_404(Beneficiario, id=id, empresa=empresa_actual)
    
    try:
        nombre_documento = request.POST.get('codigo') or request.POST.get('nombre_documento')
        mes = int(request.POST.get('mes'))
        anio = int(request.POST.get('anio'))
        archivo = request.FILES.get('archivo')
        
        if not archivo:
            return JsonResponse({'success': False, 'error': 'No se seleccionó ningún archivo.'})
            
        dict_catalogo = {d['codigo']: d for d in DocumentacionBeneficiario.CATALOGO_DOCUMENTOS}
        doc_meta = dict_catalogo.get(nombre_documento, {})
        nombre_doc_humano = doc_meta.get('nombre', nombre_documento)
        formato_esperado = doc_meta.get('formato', 'pdf')
        
        # Validar extensión según formato
        filename_lower = archivo.name.lower()
        if formato_esperado == 'pdf':
            if not filename_lower.endswith('.pdf'):
                return JsonResponse({'success': False, 'error': f'Formato no permitido. El documento "{nombre_doc_humano}" solo acepta archivos en formato PDF (.pdf).'})
        elif formato_esperado == 'excel':
            if not any(filename_lower.endswith(ext) for ext in ['.xlsx', '.xls', '.csv']):
                return JsonResponse({'success': False, 'error': f'Formato no permitido. El documento "{nombre_doc_humano}" solo acepta archivos de Excel (.xlsx, .xls) o CSV (.csv).'})
        elif formato_esperado == 'zip':
            if not any(filename_lower.endswith(ext) for ext in ['.zip', '.rar', '.7z']):
                return JsonResponse({'success': False, 'error': f'Formato no permitido. El documento "{nombre_doc_humano}" solo acepta archivos comprimidos (.zip).'})
                
        # Optimización y compresión transparente
        archivo = optimizar_archivo(archivo)

        # Si ya existe para ese mes/anio/tipo, lo actualizamos
        doc, created = DocumentacionBeneficiario.objects.get_or_create(
            empresa=empresa_actual,
            beneficiario=ben,
            nombre_documento=nombre_documento,
            mes=mes,
            anio=anio,
            defaults={'archivo': archivo, 'estatus': 'revision'}
        )
        
        if not created:
            if doc.estatus == 'aprobado' and hasattr(request.user, 'beneficiario'):
                return JsonResponse({'success': False, 'error': 'No puedes modificar un documento que ya ha sido aprobado.'})
            if doc.archivo:
                try:
                    if os.path.exists(doc.archivo.path):
                        os.remove(doc.archivo.path)
                except Exception:
                    pass
            doc.archivo = archivo
            doc.estatus = 'revision'
            doc.comentario_rechazo = ''
            doc.save()
            
        return JsonResponse({'success': True, 'message': 'Archivo subido correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
def eliminar_documento_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(DocumentacionBeneficiario, id=id, empresa=empresa_actual)
    
    if hasattr(request.user, 'beneficiario'):
        if doc.beneficiario != request.user.beneficiario:
            return JsonResponse({'success': False, 'error': 'Acceso denegado: no tienes permisos sobre este documento.'}, status=403)
        if doc.estatus == 'aprobado':
            return JsonResponse({'success': False, 'error': 'No puedes eliminar un documento que ya ha sido aprobado.'}, status=403)
    else:
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion_eliminar') and not user_has_hr_permission(request, 'beneficiarios', 'eliminar') and not user_has_hr_permission(request, 'beneficiarios', 'documentacion'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permisos para eliminar este documento.'}, status=403)

    try:
        doc.delete()
        return JsonResponse({'success': True, 'message': 'Archivo eliminado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
def portal_beneficiarios(request):
    if not hasattr(request.user, 'beneficiario'):
        return redirect('dashboard_inicio')
        
    empresa_actual = get_empresa_actual(request)
    ben = request.user.beneficiario
    
    anio = int(request.GET.get('anio', datetime.now().year))
    
    anios_disponibles = list(DocumentacionBeneficiario.objects.filter(
        beneficiario=ben
    ).values_list('anio', flat=True).distinct().order_by('-anio'))
    
    if anio not in anios_disponibles:
        anios_disponibles.append(anio)
        anios_disponibles.sort(reverse=True)
        
    contexto = {
        'beneficiario': ben,
        'anio_seleccionado': anio,
        'anios_disponibles': anios_disponibles,
        'empresa': empresa_actual,
    }
    return render(request, 'recursos_humanos/portal_beneficiarios.html', contexto)

@login_required(login_url='/login/')
def descargar_documento_beneficiario(request, doc_id):
    from django.core.exceptions import PermissionDenied
    from django.http import FileResponse, Http404
    import os

    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(DocumentacionBeneficiario, id=doc_id)

    # 1. Verificar que el documento pertenezca a la empresa actual
    if doc.empresa != empresa_actual:
        raise PermissionDenied("Acceso denegado: este documento no pertenece a tu empresa.")

    # 2. Si el usuario logueado es un Beneficiario, verificar que sea SU propio documento
    if hasattr(request.user, 'beneficiario'):
        if doc.beneficiario != request.user.beneficiario:
            raise PermissionDenied("Acceso denegado: no tienes permisos para descargar este documento.")
    else:
        # Si es administrativo, validar que tenga permisos para descargar documentos
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion_descargar') and not user_has_hr_permission(request, 'beneficiarios', 'documentacion') and not user_has_hr_permission(request, 'beneficiarios', 'ver'):
            raise PermissionDenied("Acceso denegado: no tienes permisos de Recursos Humanos.")

    # 3. Validar existencia del archivo físico
    if not doc.archivo or not os.path.exists(doc.archivo.path):
        raise Http404("El archivo físico no fue encontrado en el servidor.")

    # 4. Servir el archivo de manera segura
    return FileResponse(open(doc.archivo.path, 'rb'), as_attachment=True)

@login_required(login_url='/login/')
@require_POST
def cambiar_estatus_documento_ajax(request, doc_id):
    nuevo_estatus = request.POST.get('status') or request.POST.get('estatus')
    if nuevo_estatus == 'aprobado':
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion_aprobar') and not user_has_hr_permission(request, 'beneficiarios', 'editar') and not user_has_hr_permission(request, 'beneficiarios', 'documentacion'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para aprobar documentos.'}, status=403)
    elif nuevo_estatus == 'rechazado':
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion_rechazar') and not user_has_hr_permission(request, 'beneficiarios', 'editar') and not user_has_hr_permission(request, 'beneficiarios', 'documentacion'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para rechazar documentos.'}, status=403)
    else:
        if not user_has_hr_permission(request, 'beneficiarios', 'documentacion') and not user_has_hr_permission(request, 'beneficiarios', 'editar'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para modificar este documento.'}, status=403)

    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(DocumentacionBeneficiario, id=doc_id, empresa=empresa_actual)
    
    try:
        comentario = request.POST.get('comentario_rechazo', '').strip()
        
        if nuevo_estatus not in ['aprobado', 'rechazado', 'revision']:
            return JsonResponse({'success': False, 'error': 'Estatus inválido.'})
            
        doc.estatus = nuevo_estatus
        if nuevo_estatus == 'rechazado':
            doc.comentario_rechazo = comentario
        else:
            doc.comentario_rechazo = ''
        doc.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Documento marcado como {doc.get_estatus_display()} correctamente.',
            'estatus': doc.estatus,
            'estatus_display': doc.get_estatus_display()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
