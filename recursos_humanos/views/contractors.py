from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q, Count
from decimal import Decimal, ROUND_HALF_UP
import openpyxl
import re
import csv
from datetime import datetime
from django.urls import reverse

from ..models import Empleado, Contrato, Contratista, Beneficiario, ImportacionSUA, TrabajadorSUA, ProveedorRH, DocumentacionProveedor
from preferencias.models import Sucursal
from preferencias.permissions import require_hr_permission
from .utils import get_empresa_actual
from notificaciones.utils import crear_notificacion

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'ver')
def lista_contratistas(request):
    empresa_actual = get_empresa_actual(request)
    tipo_vista = request.GET.get('tipo', 'contratista')
    if tipo_vista not in ['contratista', 'proveedor']:
        tipo_vista = 'contratista'
        
    q = request.GET.get('q', '')
    f_razon = request.GET.get('razon_social', '')
    f_rfc = request.GET.get('rfc', '')
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')
    
    if tipo_vista == 'proveedor':
        from preferencias.permissions import user_has_hr_permission
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'ver'):
            from django.contrib import messages
            messages.error(request, 'No cuentas con permiso para ver los proveedores de contratistas.')
            return redirect('lista_contratistas')
            
        contratista_id = request.GET.get('contratista_id')
        if not contratista_id:
            return redirect('lista_contratistas')
        contratista_seleccionado = get_object_or_404(Contratista, id=contratista_id, empresa=empresa_actual)
        proveedores = ProveedorRH.objects.filter(empresa=empresa_actual, contratista=contratista_seleccionado).order_by('nombre_razon_social')
        
        if q:
            proveedores = proveedores.filter(
                Q(nombre_razon_social__icontains=q) |
                Q(rfc__icontains=q) |
                Q(clave__icontains=q)
            )
        if f_razon:
            proveedores = proveedores.filter(nombre_razon_social__icontains=f_razon)
        if f_rfc:
            proveedores = proveedores.filter(rfc__icontains=f_rfc)
            
        razones_sociales_unicas = ProveedorRH.objects.filter(empresa=empresa_actual, contratista=contratista_seleccionado).exclude(nombre_razon_social='').values_list('nombre_razon_social', flat=True).distinct().order_by('nombre_razon_social')
        rfcs_unicos = ProveedorRH.objects.filter(empresa=empresa_actual, contratista=contratista_seleccionado).exclude(rfc='').values_list('rfc', flat=True).distinct().order_by('rfc')
        
        paginator = Paginator(proveedores, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        return render(request, 'recursos_humanos/lista_contratistas.html', {
            'page_obj': page_obj,
            'sucursales': sucursales,
            'empresa': empresa_actual,
            'razones_sociales_unicas': razones_sociales_unicas,
            'rfcs_unicos': rfcs_unicos,
            'tipo_vista': 'proveedor',
            'contratista_seleccionado': contratista_seleccionado,
            'anios_lista': [2024, 2025, 2026],
            'filtros': {
                'q': q,
                'razon_social': f_razon,
                'rfc': f_rfc,
            }
        })
    else:
        contratistas = Contratista.objects.filter(empresa=empresa_actual).annotate(total_colaboradores=Count('empleado')).order_by('nombre_razon_social')
        f_rp = request.GET.get('reg_patronal', '')
        sucursal_id = request.GET.get('sucursal')
        if sucursal_id is None:
            sucursal_id = str(request.session.get('sucursal_id') or '')
            
        if q:
            contratistas = contratistas.filter(
                Q(nombre_razon_social__icontains=q) |
                Q(rfc__icontains=q) |
                Q(representante_legal__icontains=q) |
                Q(correo__icontains=q) |
                Q(clave__icontains=q)
            )
        if f_razon:
            contratistas = contratistas.filter(nombre_razon_social__icontains=f_razon)
        if f_rfc:
            contratistas = contratistas.filter(rfc__icontains=f_rfc)
        if f_rp:
            contratistas = contratistas.filter(registro_patronal__icontains=f_rp)
        if sucursal_id:
            contratistas = contratistas.filter(sucursal_id=sucursal_id)
            
        razones_sociales_unicas = Contratista.objects.filter(empresa=empresa_actual).exclude(nombre_razon_social='').values_list('nombre_razon_social', flat=True).distinct().order_by('nombre_razon_social')
        rfcs_unicos = Contratista.objects.filter(empresa=empresa_actual).exclude(rfc='').values_list('rfc', flat=True).distinct().order_by('rfc')
        reg_patronales_unicos = Contratista.objects.filter(empresa=empresa_actual).exclude(registro_patronal='').values_list('registro_patronal', flat=True).distinct().order_by('registro_patronal')
        
        paginator = Paginator(contratistas, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        return render(request, 'recursos_humanos/lista_contratistas.html', {
            'page_obj': page_obj,
            'sucursales': sucursales,
            'empresa': empresa_actual,
            'razones_sociales_unicas': razones_sociales_unicas,
            'rfcs_unicos': rfcs_unicos,
            'reg_patronales_unicos': reg_patronales_unicos,
            'tipo_vista': 'contratista',
            'anios_lista': [2024, 2025, 2026],
            'filtros': {
                'q': q,
                'razon_social': f_razon,
                'rfc': f_rfc,
                'reg_patronal': f_rp,
                'sucursal': sucursal_id
            }
        })

@login_required(login_url='/login/')
@require_hr_permission('beneficiarios', 'ver', json_response=True)
def obtener_contratista_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        cont = Contratista.objects.get(id=id, empresa=empresa_actual)
        
        # Obtener configuración SMTP si existe
        smtp_data = {}
        try:
            smtp_config = cont.config_smtp
            smtp_data = {
                'smtp_host': smtp_config.smtp_host or '',
                'smtp_port': smtp_config.smtp_port or 587,
                'smtp_user': smtp_config.smtp_user or '',
                'use_tls': smtp_config.use_tls,
                'use_ssl': smtp_config.use_ssl,
                'email_remitente': smtp_config.email_remitente or '',
                'nombre_remitente': smtp_config.nombre_remitente or '',
                'email_notificacion_1': smtp_config.email_notificacion_1 or '',
                'email_notificacion_2': smtp_config.email_notificacion_2 or '',
                'email_notificacion_3': smtp_config.email_notificacion_3 or '',
            }
        except Exception:
            smtp_data = {
                'smtp_host': '',
                'smtp_port': 587,
                'smtp_user': '',
                'use_tls': True,
                'use_ssl': False,
                'email_remitente': '',
                'nombre_remitente': '',
                'email_notificacion_1': '',
                'email_notificacion_2': '',
                'email_notificacion_3': '',
            }

        data = {
            'id': cont.id, 'clave': cont.clave or '', 'rfc': cont.rfc, 'nombre_razon_social': cont.nombre_razon_social,
            'regimen': cont.regimen or '',
            'correo': cont.correo, 'telefono': cont.telefono, 'registro_patronal': cont.registro_patronal,
            'calle': cont.calle, 'num_ext': cont.num_ext, 'num_int': cont.num_int,
            'entre_calle': cont.entre_calle, 'y_calle': cont.y_calle, 'colonia': cont.colonia,
            'cp': cont.cp, 'municipio_alcaldia': cont.municipio_alcaldia,
            'entidad_federativa': cont.entidad_federativa, 'representante_legal': cont.representante_legal,
            'administrador_unico': cont.administrador_unico, 'num_escritura': cont.num_escritura,
            'nombre_notario_publico': cont.nombre_notario_publico, 'num_notario_publico': cont.num_notario_publico,
            'fecha_escritura_publica': cont.fecha_escritura_publica.isoformat() if cont.fecha_escritura_publica else '',
            'folio_mercantil': cont.folio_mercantil, 'numero_stps': cont.numero_stps,
            **smtp_data
        }
        return JsonResponse({'success': True, 'data': data})
    except Contratista.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratistas', 'crear', json_response=True)
def crear_contratista_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual: return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)
    try:
        data = request.POST
        sucursal_id = request.session.get('sucursal_id')
        nuevo = Contratista(
            empresa=empresa_actual, sucursal_id=sucursal_id, 
            clave=data.get('clave', ''),
            rfc=data.get('rfc', '').upper(),
            nombre_razon_social=data.get('nombre_razon_social'), 
            regimen=data.get('regimen'),
            correo=data.get('correo'),
            telefono=data.get('telefono'), registro_patronal=data.get('registro_patronal'),
            calle=data.get('calle'), num_ext=data.get('num_ext'), num_int=data.get('num_int'),
            entre_calle=data.get('entre_calle'), y_calle=data.get('y_calle'), colonia=data.get('colonia'),
            cp=data.get('cp'), municipio_alcaldia=data.get('municipio_alcaldia'),
            entidad_federativa=data.get('entidad_federativa'), representante_legal=data.get('representante_legal'),
            administrador_unico=data.get('administrador_unico'), num_escritura=data.get('num_escritura'),
            nombre_notario_publico=data.get('nombre_notario_publico'), num_notario_publico=data.get('num_notario_publico'),
            fecha_escritura_publica=data.get('fecha_escritura_publica') or None, folio_mercantil=data.get('folio_mercantil'),
            numero_stps=data.get('numero_stps'),
            creado_por=request.user,
        )
        nuevo.save()
        
        # Guardar configuración SMTP y/o correos de notificación si se proporcionan
        smtp_host = data.get('smtp_host', '').strip()
        email_notif_1 = data.get('email_notificacion_1', '').strip()
        email_notif_2 = data.get('email_notificacion_2', '').strip()
        email_notif_3 = data.get('email_notificacion_3', '').strip()
        
        if smtp_host or email_notif_1 or email_notif_2 or email_notif_3:
            from recursos_humanos.models import ContratistaCorreoSMTP
            use_ssl = data.get('use_ssl') == 'true' or data.get('use_ssl') == 'on' or data.get('use_ssl') == True
            use_tls = False if use_ssl else (data.get('use_tls') == 'true' or data.get('use_tls') == 'on' or data.get('use_tls') == True or data.get('use_tls') is None)
            
            smtp_port_raw = data.get('smtp_port', '587')
            smtp_port = int(smtp_port_raw) if smtp_port_raw.isdigit() else 587
            
            if smtp_port == 465:
                use_ssl = True
                use_tls = False
            elif smtp_port in [587, 25] and use_ssl:
                use_ssl = False
                use_tls = True

            ContratistaCorreoSMTP.objects.create(
                contratista=nuevo,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=data.get('smtp_user', '').strip(),
                smtp_password=data.get('smtp_password', ''),
                use_tls=use_tls,
                use_ssl=use_ssl,
                email_remitente=data.get('email_remitente', '').strip(),
                nombre_remitente=data.get('nombre_remitente', '').strip(),
                email_notificacion_1=email_notif_1,
                email_notificacion_2=email_notif_2,
                email_notificacion_3=email_notif_3,
            )
            
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'creó al contratista {nuevo.nombre_razon_social}',
            link='/recursos-humanos/contratistas/',
            propietario=request.user
        )
        return JsonResponse({'success': True, 'message': 'Contratista registrado correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratistas', 'editar', json_response=True)
def editar_contratista_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        cont = Contratista.objects.get(id=id, empresa=empresa_actual)
        data = request.POST
        cont.clave = data.get('clave', '')
        cont.rfc = data.get('rfc', '').upper()
        cont.nombre_razon_social = data.get('nombre_razon_social')
        cont.regimen = data.get('regimen')
        cont.correo = data.get('correo'); cont.telefono = data.get('telefono')
        cont.registro_patronal = data.get('registro_patronal'); cont.calle = data.get('calle')
        cont.num_ext = data.get('num_ext'); cont.num_int = data.get('num_int')
        cont.entre_calle = data.get('entre_calle'); cont.y_calle = data.get('y_calle')
        cont.colonia = data.get('colonia'); cont.cp = data.get('cp')
        cont.municipio_alcaldia = data.get('municipio_alcaldia'); cont.entidad_federativa = data.get('entidad_federativa')
        cont.representante_legal = data.get('representante_legal'); cont.administrador_unico = data.get('administrador_unico')
        cont.num_escritura = data.get('num_escritura'); cont.nombre_notario_publico = data.get('nombre_notario_publico')
        cont.num_notario_publico = data.get('num_notario_publico'); cont.fecha_escritura_publica = data.get('fecha_escritura_publica') or None
        cont.folio_mercantil = data.get('folio_mercantil'); cont.numero_stps = data.get('numero_stps')
        cont.save()
        
        # Guardar o actualizar configuración SMTP y correos de notificación
        smtp_host = data.get('smtp_host', '').strip()
        email_notif_1 = data.get('email_notificacion_1', '').strip()
        email_notif_2 = data.get('email_notificacion_2', '').strip()
        email_notif_3 = data.get('email_notificacion_3', '').strip()
        
        from recursos_humanos.models import ContratistaCorreoSMTP
        if smtp_host or email_notif_1 or email_notif_2 or email_notif_3:
            use_ssl = data.get('use_ssl') == 'true' or data.get('use_ssl') == 'on' or data.get('use_ssl') == True
            use_tls = False if use_ssl else (data.get('use_tls') == 'true' or data.get('use_tls') == 'on' or data.get('use_tls') == True or data.get('use_tls') is None)
            
            smtp_port_raw = data.get('smtp_port', '587')
            smtp_port = int(smtp_port_raw) if smtp_port_raw.isdigit() else 587
            
            if smtp_port == 465:
                use_ssl = True
                use_tls = False
            elif smtp_port in [587, 25] and use_ssl:
                use_ssl = False
                use_tls = True
            
            smtp_config, creado = ContratistaCorreoSMTP.objects.get_or_create(
                contratista=cont,
                defaults={
                    'smtp_host': smtp_host,
                    'smtp_port': smtp_port,
                    'smtp_user': data.get('smtp_user', '').strip(),
                    'smtp_password': data.get('smtp_password', ''),
                    'use_tls': use_tls,
                    'use_ssl': use_ssl,
                    'email_remitente': data.get('email_remitente', '').strip(),
                    'nombre_remitente': data.get('nombre_remitente', '').strip(),
                    'email_notificacion_1': email_notif_1,
                    'email_notificacion_2': email_notif_2,
                    'email_notificacion_3': email_notif_3,
                }
            )
            if not creado:
                smtp_config.smtp_host = smtp_host
                smtp_config.smtp_port = smtp_port
                smtp_config.smtp_user = data.get('smtp_user', '').strip()
                
                # Si la contraseña no se envía vacía, se actualiza
                smtp_pass_input = data.get('smtp_password', '')
                if smtp_pass_input:
                    smtp_config.smtp_password = smtp_pass_input
                    
                smtp_config.use_tls = use_tls
                smtp_config.use_ssl = use_ssl
                smtp_config.email_remitente = data.get('email_remitente', '').strip()
                smtp_config.nombre_remitente = data.get('nombre_remitente', '').strip()
                smtp_config.email_notificacion_1 = email_notif_1
                smtp_config.email_notificacion_2 = email_notif_2
                smtp_config.email_notificacion_3 = email_notif_3
                smtp_config.save()
        else:
            # Si todos los campos están vacíos, eliminamos la configuración SMTP si existe
            ContratistaCorreoSMTP.objects.filter(contratista=cont).delete()
            
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'editó al contratista {cont.nombre_razon_social}',
            link='/recursos-humanos/contratistas/',
            propietario=cont.creado_por or request.user
        )
        return JsonResponse({'success': True, 'message': 'Contratista actualizado correctamente.'})
    except Contratista.DoesNotExist: return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@require_hr_permission('contratistas', 'eliminar', json_response=True)
def eliminar_contratista_ajax(request, id):
    """Eliminar un contratista."""
    empresa_actual = get_empresa_actual(request)
    try:
        cont = Contratista.objects.get(id=id, empresa=empresa_actual)
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'eliminó al contratista {cont.nombre_razon_social}',
            link='/recursos-humanos/contratistas/',
            propietario=cont.creado_por or request.user
        )
        cont.delete()
        return JsonResponse({'success': True, 'message': 'Contratista eliminado correctamente.'})
    except Contratista.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Contratista no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='/login/')
@require_POST
@transaction.atomic
@require_hr_permission('contratistas', 'importador', json_response=True)
def importar_contratistas_ajax(request):
    """Cargador de contratistas desde Excel."""
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'status': 'error', 'message': 'Empresa no encontrada.'})
    
    file = request.FILES.get('archivo')
    if not file:
        return JsonResponse({'status': 'error', 'message': 'No se proporcionó ningún archivo.'})
    
    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        sheet = wb.active
        
        # Buscar en qué fila se encuentran los encabezados reales (ej. "Registro Federal de Contribuyente")
        header_row_idx = 1
        for r_idx, row_cells in enumerate(sheet.iter_rows(max_row=10), 1):
            row_vals = [str(cell.value).strip().lower() if cell.value else "" for cell in row_cells]
            if any(h in row_vals for h in ["registro federal de contribuyente", "rfc", "nombre denominacion o razon social", "cuatrimestre que declara"]):
                header_row_idx = r_idx
                break
        
        # Obtener y normalizar encabezados
        headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[header_row_idx]]
        headers_norm = [h.strip().lower() for h in headers]
        
        def get_val(row, header_name, default=None):
            try:
                idx = headers_norm.index(header_name.strip().lower())
                val = row[idx].value
                return val if val is not None else default
            except (ValueError, IndexError):
                return default

        def to_date(val):
            if isinstance(val, datetime): return val.date()
            if isinstance(val, str):
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%dT%H:%M:%S'):
                    try: return datetime.strptime(val.strip(), fmt).date()
                    except: pass
            return None

        sucursal_id = request.session.get('sucursal_id')
        contractors_created = 0
        contractors_updated = 0
        
        for row in sheet.iter_rows(min_row=header_row_idx + 1):
            rfc = str(get_val(row, 'Registro Federal de Contribuyente', '')).strip().upper()
            if not rfc:
                continue

            obj, created = Contratista.objects.update_or_create(
                empresa=empresa_actual,
                rfc=rfc,
                defaults={
                    'sucursal_id': sucursal_id,
                    'nombre_razon_social': str(get_val(row, 'Nombre denominacion o razon social', '')).strip(),
                    'correo': str(get_val(row, 'Correo electronico', '')).strip(),
                    'telefono': str(get_val(row, 'Telefono (numero extension)', '')).strip(),
                    'registro_patronal': str(get_val(row, 'Registro patronal', '')).strip(),
                    'calle': str(get_val(row, 'Calle', '')).strip(),
                    'num_ext': str(get_val(row, 'Numero exterior', '')).strip(),
                    'num_int': str(get_val(row, 'Numero interior', '')).strip(),
                    'entre_calle': str(get_val(row, 'Entre calle', '')).strip(),
                    'y_calle': str(get_val(row, 'Y calle', '')).strip(),
                    'colonia': str(get_val(row, 'Colonia', '')).strip(),
                    'cp': str(get_val(row, 'Codigo Postal', '')).strip(),
                    'municipio_alcaldia': str(get_val(row, 'Municipio o Alcaldia', '')).strip(),
                    'entidad_federativa': str(get_val(row, 'Entidad Federativa', '')).strip(),
                    'representante_legal': str(get_val(row, 'Representante legal', '')).strip(),
                    'administrador_unico': str(get_val(row, 'Administrador Unico', '')).strip(),
                    'num_escritura': str(get_val(row, 'Numero de escritura', '')).strip(),
                    'nombre_notario_publico': str(get_val(row, 'Nombre del Notario Publico', '')).strip(),
                    'num_notario_publico': str(get_val(row, 'Numero de Notario Publico', '')).strip(),
                    'fecha_escritura_publica': to_date(get_val(row, 'Fecha de escritura publica')),
                    'folio_mercantil': str(get_val(row, 'Folio mercantil', '')).strip(),
                    'numero_stps': str(get_val(row, 'Numero de registro ante la Secretaria de Trabajo y Prevision Social', '')).strip(),
                }
            )
            if created:
                contractors_created += 1
            else:
                contractors_updated += 1

        total_count = contractors_created + contractors_updated
        if total_count > 0:
            crear_notificacion(
                empresa=empresa_actual,
                actor=request.user,
                mensaje=f'importó de forma masiva {total_count} contratistas (nuevos: {contractors_created}, actualizados: {contractors_updated})',
                link='/recursos-humanos/contratistas/',
                propietario=request.user
            )

        return JsonResponse({
            'status': 'success', 
            'message': f'Proceso completado. Se registraron/actualizaron {total_count} contratistas.'
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al procesar el archivo: {str(e)}'})

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'reporte_contratos')
def exportar_sisub_contratos(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        contratista = get_object_or_404(Contratista, id=id, empresa=empresa_actual)
        cuatrimestre = request.GET.get('cuatrimestre', '1')
        anio = request.GET.get('anio', '')
        formato = request.GET.get('formato', 'excel')

        import datetime
        try:
            cuat_num = int(cuatrimestre)
            anio_num = int(anio) if anio else datetime.date.today().year
        except ValueError:
            cuat_num = 1
            anio_num = datetime.date.today().year

        if cuat_num == 1:
            cuat_start = datetime.date(anio_num, 1, 1)
            cuat_end = datetime.date(anio_num, 4, 30)
        elif cuat_num == 2:
            cuat_start = datetime.date(anio_num, 5, 1)
            cuat_end = datetime.date(anio_num, 8, 31)
        else:
            cuat_start = datetime.date(anio_num, 9, 1)
            cuat_end = datetime.date(anio_num, 12, 31)

        contratos = Contrato.objects.filter(
            contratista=contratista,
            empresa=empresa_actual,
            fecha_inicio__lte=cuat_end
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=cuat_start)
        ).select_related('beneficiario').prefetch_related('empleados').order_by('folio')

        headers = ['Cuatrimestre', 'Año', 'RFC Sujeto', 'Folio', 'Tipo', 'Objeto', 'Monto', 'Vigencia', 'Inicio', 'Termino', 'Trabajadores', 'RFC Ben', 'Nombre Ben', 'RegPat Ben', 'Calle', 'Ext', 'Int', 'Entre', 'Y', 'Colonia', 'CP', 'Mun', 'Edo', 'Email', 'Tel']
        
        data_rows = []
        for con in contratos:
            ben = con.beneficiario
            t_display = con.get_tipo_contrato_display()
            if con.tipo_contrato == '01':
                t_display = "Contrato de trabajo por tiempo indeterminado"
            elif t_display and ' - ' in t_display:
                t_display = t_display.split(' - ', 1)[1]
                
            data_rows.append([
                cuatrimestre, anio, contratista.rfc, con.folio, t_display, 
                con.objeto_contrato, con.monto_contrato, 
                con.vigencia_contrato.strftime('%d/%m/%Y') if con.vigencia_contrato else '',
                con.fecha_inicio.strftime('%d/%m/%Y') if con.fecha_inicio else '', 
                con.fecha_fin.strftime('%d/%m/%Y') if con.fecha_fin else '', 
                con.empleados.count(), 
                ben.rfc if ben else '', ben.nombre_razon_social if ben else '', ben.registro_patronal if ben else '', 
                ben.calle if ben else '', ben.num_ext if ben else '', ben.num_int if ben else '', 
                ben.entre_calle if ben else '', ben.y_calle if ben else '', ben.colonia if ben else '', 
                ben.cp if ben else '', ben.municipio_alcaldia if ben else '', ben.entidad_federativa if ben else '', 
                ben.correo if ben else '', ben.telefono if ben else ''
            ])

        rfc_clean = re.sub(r'[^A-Z0-9]', '', contratista.rfc.upper())
        
        if formato == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="SISUB_CONTRATOS_{rfc_clean}.csv"'
            response.write(u'\ufeff'.encode('utf8'))
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(data_rows)
            return response
        else:
            from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "SISUB Contratos"
            fill_main = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
            fill_sec = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
            fill_head = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
            border = Border(left=Side(style='thin', color="B2B2B2"), right=Side(style='thin', color="B2B2B2"), top=Side(style='thin', color="B2B2B2"), bottom=Side(style='thin', color="B2B2B2"))
            center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=25)
            c1 = ws.cell(row=1, column=1, value="b-Contratos de servicio (cliente)"); c1.alignment = center_align; c1.font = Font(bold=True, color="FFFFFF", size=12); c1.fill = fill_main; c1.border = border
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2); ws.cell(row=2, column=1, value="periodo")
            ws.merge_cells(start_row=2, start_column=3, end_row=2, end_column=11); ws.cell(row=2, column=3, value="a-Datos generales del contrato")
            ws.merge_cells(start_row=2, start_column=12, end_row=2, end_column=14); ws.cell(row=2, column=12, value="b-Identificacion del beneficiario")
            ws.merge_cells(start_row=2, start_column=15, end_row=2, end_column=25); ws.cell(row=2, column=15, value="c-Domicilio fiscal del beneficiario")
            for c in range(1, 26): cell = ws.cell(row=2, column=c); cell.fill = fill_sec; cell.font = Font(bold=True); cell.border = border; cell.alignment = center_align
            for i, h in enumerate(headers, 1): cell = ws.cell(row=3, column=i, value=h); cell.fill = fill_head; cell.font = Font(bold=True); cell.border = border; cell.alignment = center_align
            for row_data in data_rows:
                ws.append(row_data)
                for cell in ws[ws.max_row]: cell.border = border; cell.alignment = Alignment(vertical="center")
            for i in range(1, 26): ws.column_dimensions[get_column_letter(i)].width = 18
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="SISUB_CONTRATOS_{rfc_clean}.xlsx"'; wb.save(response)
            return response
    except Exception as e: return HttpResponse(f"Error al generar reporte: {str(e)}", status=500)

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'reporte_informacion')
def exportar_icsoe(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        contratista = Contratista.objects.get(id=id, empresa=empresa_actual)
        cuat = request.GET.get('cuatrimestre', '1'); anio = request.GET.get('anio', '')
        formato = request.GET.get('formato', 'excel')
        if not anio: return HttpResponse("Año requerido", status=400)
        
        periodos_busqueda = {'1': ['FEBRERO', 'ABRIL'], '2': ['JUNIO', 'AGOSTO'], '3': ['OCTUBRE', 'DICIEMBRE']}.get(cuat, [])
        rfc_input_clean = re.sub(r'[^A-Z0-9]', '', contratista.rfc.upper())
        importaciones_qs = ImportacionSUA.objects.filter(empresa=empresa_actual, tipo='bimestral')
        
        importaciones_validas = []
        for imp in importaciones_qs:
            if anio not in imp.periodo: continue
            if not any(mes in imp.periodo.upper() for mes in periodos_busqueda): continue
            rfc_rep_clean = re.sub(r'[^A-Z0-9]', '', (imp.rfc_empresa or '').upper())
            if rfc_input_clean == rfc_rep_clean or rfc_input_clean in rfc_rep_clean or rfc_rep_clean in rfc_input_clean:
                importaciones_validas.append(imp)
        
        contratos = Contrato.objects.filter(contratista=contratista, empresa=empresa_actual)
        beneficiarios_ids = contratos.values_list('beneficiario_id', flat=True).distinct()
        beneficiarios = Beneficiario.objects.filter(id__in=beneficiarios_ids, empresa=empresa_actual)
        claves_beneficiarios = set((b.clave or '').strip().upper() for b in beneficiarios if b.clave)

        total_sin_credito = total_con_credito = total_amortizaciones = Decimal('0')
        for imp in importaciones_validas:
            for t in imp.trabajadores.all():
                clave_t = (t.clave_ubicacion or '').strip().upper()
                if clave_t in claves_beneficiarios:
                    val_inf = (t.tipo_valor_infonavit or '').strip()
                    if not val_inf or val_inf == '-': total_sin_credito += t.aportacion_patronal
                    else: total_con_credito += t.aportacion_patronal
                    total_amortizaciones += t.amortizacion

        total_sin_credito_red = total_sin_credito.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        total_con_credito_red = total_con_credito.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        total_amortizaciones_red = total_amortizaciones.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        headers = ["cuatrimestre que declara", "anio que se declara", "Registro Federal de Contribuyente", "Nombre denominacion o razon social", "Correo electronico", "Telefono (numero extension)", "Registro patronal", "Calle", "Numero exterior", "Numero interior", "Entre calle", "Y calle", "Colonia", "Codigo Postal", "Municipio o Alcaldia", "Entidad Federativa", "Representante legal", "Administrador Unico", "Numero de escritura", "Nombre del Notario Publico", "Numero de Notario Publico", "Fecha de escritura publica", "Folio mercantil", "Aportacion sin credito de los trabajadores del contrato", "Aportacion con credito de los trabajadores del contrato", "Amortizacion de los trabajadores del contrato", "Numero de registro ante la Secretaria de Trabajo y Prevision Social"]
        
        data_row = [
            cuat, anio, contratista.rfc, contratista.nombre_razon_social, 
            contratista.correo, contratista.telefono, contratista.registro_patronal, 
            contratista.calle, contratista.num_ext, contratista.num_int, contratista.entre_calle, 
            contratista.y_calle, contratista.colonia, contratista.cp, contratista.municipio_alcaldia, 
            contratista.entidad_federativa, contratista.representante_legal, contratista.administrador_unico, 
            contratista.num_escritura, contratista.nombre_notario_publico, contratista.num_notario_publico, 
            contratista.fecha_escritura_publica.strftime('%d/%m/%Y') if contratista.fecha_escritura_publica else '', 
            contratista.folio_mercantil, 
            total_sin_credito_red, total_con_credito_red, total_amortizaciones_red, 
            contratista.numero_stps
        ]

        if formato == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="SUJETO_OBLIGADO_SISUB_{rfc_input_clean}_{anio}_C{cuat}.csv"'
            response.write(u'\ufeff'.encode('utf8'))
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerow(data_row)
            return response
        else:
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sujeto Obligado (SISUB)"
            fill_brand = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
            fill_gray = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
            fill_light = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
            border = Border(left=Side(style='thin', color="B2B2B2"), right=Side(style='thin', color="B2B2B2"), top=Side(style='thin', color="B2B2B2"), bottom=Side(style='thin', color="B2B2B2"))
            ws.merge_cells('A1:AA1'); c1 = ws['A1']; c1.value = "a-Datos Generales"; c1.fill = fill_brand; c1.font = Font(bold=True, color="FFFFFF"); c1.alignment = Alignment(horizontal="center"); c1.border = border
            subgrupos = [("Periodo", 2), ("b-Datos de identificacion", 5), ("c-Domicilio fiscal", 9), ("d-Datos actuales de la escritura publica", 7), ("g-Aportacion y Amortizacion", 3), ("a-Registro en STPS", 1)]
            curr_col = 1
            for nombre, span in subgrupos:
                start_cell = get_column_letter(curr_col) + "2"; end_cell = get_column_letter(curr_col + span - 1) + "2"
                if span > 1: ws.merge_cells(f"{start_cell}:{end_cell}")
                cell = ws[start_cell]; cell.value = nombre; cell.fill = fill_gray; cell.font = Font(bold=True); cell.alignment = Alignment(horizontal="center"); cell.border = border
                for c in range(curr_col, curr_col + span): ws.cell(row=2, column=c).border = border
                curr_col += span
            for i, h in enumerate(headers, 1): cell = ws.cell(row=3, column=i, value=h); cell.fill = fill_light; cell.font = Font(bold=True); cell.border = border; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); ws.column_dimensions[get_column_letter(i)].width = 20
            ws.append(data_row)
            for col_idx in [24, 25, 26]: ws.cell(row=4, column=col_idx).number_format = '"$"#,##0.00'
            for col_idx in range(1, 28): ws.cell(row=4, column=col_idx).border = border
            ws.merge_cells('A1:AA1'); c1 = ws['A1']; c1.alignment = Alignment(horizontal="center")
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="SUJETO_OBLIGADO_SISUB_{rfc_input_clean}_{anio}_C{cuat}.xlsx"'; wb.save(response)
            return response
    except Exception as e: return HttpResponse(str(e), status=500)

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'reporte_carga_trabajadores')
def exportar_carga_trabajadores(request, id):
    empresa_actual = get_empresa_actual(request)
    contratista = get_object_or_404(Contratista, id=id, empresa=empresa_actual)

    cuat = int(request.GET.get('cuatrimestre', 1))
    anio = request.GET.get('anio', datetime.now().year)
    formato = request.GET.get('formato', 'excel')
    beneficiario_id = request.GET.get('beneficiario_id', 'todos')

    cuat_meses_map = {
        1: [1, 2, 3, 4],
        2: [5, 6, 7, 8],
        3: [9, 10, 11, 12],
    }
    meses_filtro = cuat_meses_map.get(cuat, [1, 2, 3, 4])
    
    import datetime as dt
    anio_int = int(anio)
    if cuat == 1:
        cuat_start = dt.date(anio_int, 1, 1)
        cuat_end = dt.date(anio_int, 4, 30)
    elif cuat == 2:
        cuat_start = dt.date(anio_int, 5, 1)
        cuat_end = dt.date(anio_int, 8, 31)
    else:
        cuat_start = dt.date(anio_int, 9, 1)
        cuat_end = dt.date(anio_int, 12, 31)
    
    # RFC limpio para búsqueda
    rfc_clean_input = re.sub(r'[^A-Z0-9]', '', contratista.rfc.upper())

    # Buscar Importaciones SUA
    importaciones_validas = []
    for mes in meses_filtro:
        nombre_mes = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][mes]
        
        # Filtramos por empresa, mes y año de forma independiente para mayor flexibilidad (ej: "Enero-2024" o "Enero 2024")
        imps = ImportacionSUA.objects.filter(
            empresa=empresa_actual, 
            periodo__icontains=nombre_mes
        ).filter(
            periodo__icontains=str(anio)
        )
        for imp in imps:
            rfc_imp_clean = re.sub(r'[^A-Z0-9]', '', (imp.rfc_empresa or '').upper())
            if rfc_clean_input == rfc_imp_clean or rfc_clean_input in rfc_imp_clean or rfc_imp_clean in rfc_clean_input:
                importaciones_validas.append(imp)

    # Obtener Trabajadores de estas importaciones
    trabajadores_data = {} # NSS -> {nss, curp, sbc}
    
    for imp in importaciones_validas:
        trabajadores_sua = TrabajadorSUA.objects.filter(importacion=imp)
        for ts in trabajadores_sua:
            nss_raw = (ts.nss or "").strip()
            nss_clean = re.sub(r'[^0-9]', '', nss_raw)
            if not nss_clean: continue
            
            # Validar si el trabajador tiene un beneficiario asignado en el modelo Empleado
            # Buscamos por NSS
            empleado = Empleado.objects.filter(empresa=empresa_actual, nss=nss_clean).first()
            
            # Si no se encuentra por NSS, intentamos por CURP si está disponible
            if not empleado and ts.rfc_curp:
                curp_ts = re.sub(r'[^A-Z0-9]', '', ts.rfc_curp.upper())[:18]
                if len(curp_ts) == 18:
                    empleado = Empleado.objects.filter(empresa=empresa_actual, curp=curp_ts).first()
            
            if empleado:
                # Obtener beneficiario(s) asociado(s) al empleado
                beneficiarios_del_empleado = set()
                
                # a. De su perfil de Empleado
                if empleado.beneficiario_id:
                    beneficiarios_del_empleado.add(empleado.beneficiario_id)
                
                # b. De sus contratos activos con este contratista en este cuatrimestre
                contratos_emp = Contrato.objects.filter(
                    empleados=empleado,
                    contratista=contratista,
                    empresa=empresa_actual,
                    fecha_inicio__lte=cuat_end
                ).filter(
                    Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=cuat_start)
                )
                for con in contratos_emp:
                    if con.beneficiario_id:
                        beneficiarios_del_empleado.add(con.beneficiario_id)
                
                # Si no tiene ningún beneficiario asociado, no se puede reportar para ICSOE
                if not beneficiarios_del_empleado:
                    continue
                
                # Filtrar por beneficiario si se seleccionó uno específico
                if beneficiario_id and beneficiario_id != 'todos':
                    try:
                        ben_id_int = int(beneficiario_id)
                        if ben_id_int not in beneficiarios_del_empleado:
                            continue
                    except ValueError:
                        continue

                # Extraer CURP: priorizar Empleado, luego ts.rfc_curp
                curp_final = empleado.curp
                if not curp_final and ts.rfc_curp:
                    curp_final = re.sub(r'[^A-Z0-9]', '', ts.rfc_curp.upper())[:18]
                
                # NSS debe tener 11 dígitos
                nss_display = nss_clean.zfill(11)[:11]
                
                # Tomamos el SBC (SDI en el modelo TrabajadorSUA)
                sbc_val = float(ts.sdi or 0)
                
                # Si ya existe, actualizamos el SBC solo si el nuevo valor es > 0 
                # para evitar que un valor en cero sobreescriba el último sueldo válido.
                if nss_display in trabajadores_data:
                    if sbc_val > 0:
                        trabajadores_data[nss_display]['sbc'] = sbc_val
                else:
                    trabajadores_data[nss_display] = {
                        'nss': nss_display,
                        'curp': curp_final[:18] if curp_final else "",
                        'sbc': sbc_val
                    }

    # Obtener sufijo para nombre de archivo si se filtra por beneficiario
    filename_suffix = ""
    if beneficiario_id and beneficiario_id != 'todos':
        try:
            ben = Beneficiario.objects.get(id=beneficiario_id, empresa=empresa_actual)
            filename_suffix = f"_{re.sub(r'[^A-Z0-9]', '', ben.rfc.upper())}"
        except Beneficiario.DoesNotExist:
            pass

    # Generar Reporte
    if formato == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Carga_Trabajadores_ICSOE_{contratista.rfc}{filename_suffix}_{anio}_C{cuat}.csv"'
        response.write(u'\ufeff'.encode('utf-8'))
        
        writer = csv.writer(response)
        writer.writerow(['NSS(11 dígitos)', 'CURP(18 caracteres)', 'Salario base de cotización(numérico con 2 decimales)'])
        
        for nss in sorted(trabajadores_data.keys()):
            d = trabajadores_data[nss]
            writer.writerow([d['nss'], d['curp'], f"{d['sbc']:.2f}"])
        
        return response
    else:
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Carga trabajadores (ICSOE)"
        
        headers = ['NSS(11 dígitos)', 'CURP(18 caracteres)', 'Salario base de cotización(numérico con 2 decimales)']
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=i, value=h)
            cell.font = Font(bold=True)
        
        row_num = 2
        for nss in sorted(trabajadores_data.keys()):
            d = trabajadores_data[nss]
            ws.cell(row=row_num, column=1, value=d['nss'])
            ws.cell(row=row_num, column=2, value=d['curp'])
            ws.cell(row=row_num, column=3, value=d['sbc']).number_format = '0.00'
            row_num += 1
            
        for i in range(1, 4):
            ws.column_dimensions[get_column_letter(i)].width = 30
            
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="Carga_Trabajadores_ICSOE_{contratista.rfc}{filename_suffix}_{anio}_C{cuat}.xlsx"'
        wb.save(response)
        return response


@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'ver', json_response=True)
def obtener_beneficiarios_contratista_json(request, id):
    empresa_actual = get_empresa_actual(request)
    contratista = get_object_or_404(Contratista, id=id, empresa=empresa_actual)
    
    # Obtener beneficiarios vinculados por contratos a este contratista
    beneficiarios = Beneficiario.objects.filter(
        contrato__contratista=contratista,
        empresa=empresa_actual
    ).distinct().order_by('nombre_razon_social')
    
    data = [
        {
            'id': b.id,
            'nombre_razon_social': b.nombre_razon_social,
            'rfc': b.rfc
        }
        for b in beneficiarios
    ]
    return JsonResponse({'success': True, 'beneficiarios': data})


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('proveedores_contratistas', 'crear', json_response=True)
def crear_proveedor_rh_ajax(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual: return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)
    try:
        data = request.POST
        contratista_id = data.get('contratista_id')
        if not contratista_id:
            return JsonResponse({'success': False, 'error': 'No se especificó el contratista.'})
        contratista_obj = get_object_or_404(Contratista, id=contratista_id, empresa=empresa_actual)
        
        rfc_val = data.get('rfc', '').upper()
        if ProveedorRH.objects.filter(rfc=rfc_val, empresa=empresa_actual, contratista=contratista_obj).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe un proveedor con este RFC asignado a este contratista.'})
            
        usuario_portal = data.get('usuario_portal', '').strip()
        password_portal = data.get('password_portal', '').strip()
        user_obj = None
        if usuario_portal:
            if not password_portal:
                return JsonResponse({'success': False, 'error': 'La contraseña es obligatoria si se define un usuario de acceso.'})
            username_completo = f"{usuario_portal}@{empresa_actual.subdominio}"
            if User.objects.filter(username=username_completo).exists():
                return JsonResponse({'success': False, 'error': f'El usuario {username_completo} ya existe.'})
            user_obj = User.objects.create_user(username=username_completo, email=data.get('contacto_email'), password=password_portal)

        nuevo = ProveedorRH(
            empresa=empresa_actual,
            contratista=contratista_obj,
            clave=data.get('clave', ''),
            rfc=rfc_val,
            nombre_razon_social=data.get('razon_social'),
            correo=data.get('contacto_email'),
            telefono=data.get('contacto_telefono'),
            calle=data.get('calle'),
            num_ext=data.get('num_ext'),
            num_int=data.get('num_int'),
            colonia=data.get('colonia'),
            cp=data.get('cp'),
            municipio_alcaldia=data.get('municipio_alcaldia'),
            numero_stps=data.get('numero_stps', '').strip() or None,
            registro_patronal=data.get('registro_patronal', '').strip() or None,
            entidad_federativa=data.get('entidad_federativa', '').strip() or None,
            fecha_vigencia=data.get('fecha_vigencia', '').strip() or None,
            estatus=data.get('estatus', 'activo') or 'activo',
            usuario=user_obj,
            creado_por=request.user,
        )
        nuevo.save()
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'creó al proveedor {nuevo.nombre_razon_social}',
            link=f'/recursos-humanos/contratistas/?tipo=proveedor&contratista_id={contratista_obj.id}',
            propietario=request.user
        )
        return JsonResponse({'success': True, 'message': 'Proveedor registrado correctamente.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='/login/')
@require_hr_permission('proveedores_contratistas', 'ver', json_response=True)
def obtener_proveedor_rh_json(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        p = ProveedorRH.objects.get(id=id, empresa=empresa_actual)
        usuario_portal = ''
        if p.usuario:
            usuario_portal = p.usuario.username.split('@')[0]

        data = {
            'id': p.id,
            'clave': p.clave or '',
            'rfc': p.rfc,
            'razon_social': p.nombre_razon_social,
            'contacto_email': p.correo or '',
            'contacto_telefono': p.telefono or '',
            'calle': p.calle or '',
            'num_ext': p.num_ext or '',
            'num_int': p.num_int or '',
            'colonia': p.colonia or '',
            'cp': p.cp or '',
            'municipio_alcaldia': p.municipio_alcaldia or '',
            'domicilio': p.domicilio or '',
            'usuario_portal': usuario_portal,
            'numero_stps': p.numero_stps or '',
            'registro_patronal': p.registro_patronal or '',
            'entidad_federativa': p.entidad_federativa or '',
            'fecha_vigencia': p.fecha_vigencia.strftime('%Y-%m-%d') if p.fecha_vigencia else '',
            'estado_vigencia': p.estado_vigencia,
            'estatus': p.estatus,
        }
        return JsonResponse({'success': True, 'data': data})
    except ProveedorRH.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Proveedor no encontrado.'})


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('proveedores_contratistas', 'editar', json_response=True)
def editar_proveedor_rh_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        p = ProveedorRH.objects.get(id=id, empresa=empresa_actual)
        data = request.POST
        rfc_val = data.get('rfc', '').upper()
        if ProveedorRH.objects.filter(rfc=rfc_val, empresa=empresa_actual, contratista=p.contratista).exclude(id=p.id).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe otro proveedor con este RFC asignado a este contratista.'})
        
        usuario_portal = data.get('usuario_portal', '').strip()
        password_portal = data.get('password_portal', '').strip()
        
        if usuario_portal:
            username_completo = f"{usuario_portal}@{empresa_actual.subdominio}"
            existing_user = User.objects.filter(username=username_completo).exclude(id=p.usuario_id).first() if p.usuario_id else User.objects.filter(username=username_completo).first()
            if existing_user:
                return JsonResponse({'success': False, 'error': f'El usuario {username_completo} ya existe.'})
            
            user_obj = None
            if p.usuario_id:
                try:
                    user_obj = p.usuario
                except User.DoesNotExist:
                    pass
            
            if user_obj:
                user_obj.username = username_completo
                user_obj.email = data.get('contacto_email')
                if password_portal:
                    user_obj.set_password(password_portal)
                user_obj.save()
            else:
                if not password_portal:
                    return JsonResponse({'success': False, 'error': 'La contraseña es obligatoria para un usuario nuevo.'})
                user_obj = User.objects.create_user(username=username_completo, email=data.get('contacto_email'), password=password_portal)
                p.usuario = user_obj
        else:
            if p.usuario_id:
                try:
                    old_user = p.usuario
                    old_user.delete()
                except User.DoesNotExist:
                    pass
                p.usuario = None

        p.clave = data.get('clave', '')
        p.rfc = data.get('rfc', '').upper()
        p.nombre_razon_social = data.get('razon_social')
        p.correo = data.get('contacto_email')
        p.telefono = data.get('contacto_telefono')
        p.calle = data.get('calle')
        p.num_ext = data.get('num_ext')
        p.num_int = data.get('num_int')
        p.colonia = data.get('colonia')
        p.cp = data.get('cp')
        p.municipio_alcaldia = data.get('municipio_alcaldia')
        p.numero_stps = data.get('numero_stps', '').strip() or None
        p.registro_patronal = data.get('registro_patronal', '').strip() or None
        p.entidad_federativa = data.get('entidad_federativa', '').strip() or None
        p.fecha_vigencia = data.get('fecha_vigencia', '').strip() or None
        p.estatus = data.get('estatus', 'activo') or 'activo'
        p.save()
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'editó al proveedor {p.nombre_razon_social}',
            link=f'/recursos-humanos/contratistas/?tipo=proveedor&contratista_id={p.contratista.id}' if p.contratista else '/recursos-humanos/contratistas/?tipo=proveedor',
            propietario=p.creado_por or request.user
        )
        return JsonResponse({'success': True, 'message': 'Proveedor actualizado correctamente.'})
    except ProveedorRH.DoesNotExist: return JsonResponse({'success': False, 'error': 'Proveedor no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='/login/')
@require_POST
@require_hr_permission('proveedores_contratistas', 'eliminar', json_response=True)
def eliminar_proveedor_rh_ajax(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        p = ProveedorRH.objects.get(id=id, empresa=empresa_actual)
        nombre = p.nombre_razon_social
        
        if p.usuario:
            try:
                p.usuario.delete()
            except Exception:
                pass

        p.delete()
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'eliminó al proveedor {nombre}',
            link='/recursos-humanos/contratistas/?tipo=proveedor',
            propietario=request.user
        )
        return JsonResponse({'success': True, 'message': 'Proveedor eliminado correctamente.'})
    except ProveedorRH.DoesNotExist: return JsonResponse({'success': False, 'error': 'Proveedor no encontrado.'})
    except Exception as e: return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='/login/')
def portal_proveedores(request):
    if not hasattr(request.user, 'proveedor_rh'):
        return redirect('dashboard_inicio')
        
    empresa_actual = get_empresa_actual(request)
    prov = request.user.proveedor_rh
    
    anio = int(request.GET.get('anio', datetime.now().year))
    
    anios_disponibles = list(DocumentacionProveedor.objects.filter(
        proveedor=prov
    ).values_list('anio', flat=True).distinct().order_by('-anio'))
    
    if anio not in anios_disponibles:
        anios_disponibles.append(anio)
        anios_disponibles.sort(reverse=True)
        
    contexto = {
        'proveedor': prov,
        'anio_seleccionado': anio,
        'anios_disponibles': anios_disponibles,
        'empresa': empresa_actual,
    }
    return render(request, 'recursos_humanos/portal_proveedores.html', contexto)


@login_required(login_url='/login/')
def obtener_documentacion_proveedor_json(request, id):
    empresa_actual = get_empresa_actual(request)
    is_self = hasattr(request.user, 'proveedor_rh') and request.user.proveedor_rh.id == id
    if not is_self:
        from preferencias.permissions import user_has_hr_permission
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion') and not user_has_hr_permission(request, 'proveedores_contratistas', 'ver'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)
            
    prov = get_object_or_404(ProveedorRH, id=id, empresa=empresa_actual)
    
    try:
        anio = int(request.GET.get('anio') or datetime.now().year)
    except ValueError:
        anio = datetime.now().year
    docs_existentes = DocumentacionProveedor.objects.filter(proveedor=prov, anio=anio)
    
    tipos_doc = DocumentacionProveedor.NOMBRE_DOC_CHOICES
    
    matrix = []
    for code, nombre in tipos_doc:
        meses_data = {}
        for m in range(1, 13):
            doc = docs_existentes.filter(nombre_documento=code, mes=m).first()
            meses_data[m] = {
                'id': doc.id if doc else None,
                'url': reverse('descargar_documento_proveedor', args=[doc.id]) if doc else None,
                'nombre_archivo': doc.archivo.name.split('/')[-1] if doc else None,
                'estatus': doc.status if doc else None,
                'estatus_display': doc.get_status_display() if doc else None,
                'comentario_rechazo': (doc.comentario_rechazo or '') if doc else ''
            }
        matrix.append({
            'codigo': code,
            'nombre': nombre,
            'meses': meses_data
        })
        
    return JsonResponse({
        'success': True,
        'proveedor': prov.nombre_razon_social,
        'anio': anio,
        'matrix': matrix
    })


@login_required(login_url='/login/')
@require_POST
def subir_documento_proveedor_ajax(request, id):
    import os
    empresa_actual = get_empresa_actual(request)
    if hasattr(request.user, 'proveedor_rh') and request.user.proveedor_rh.id == id:
        prov = request.user.proveedor_rh
    else:
        prov = get_object_or_404(ProveedorRH, id=id, empresa=empresa_actual)
        
    try:
        nombre_documento = request.POST.get('nombre_documento')
        mes = int(request.POST.get('mes'))
        anio = int(request.POST.get('anio'))
        archivo = request.FILES.get('archivo')
        
        if not archivo:
            return JsonResponse({'success': False, 'error': 'No se proporcionó ningún archivo.'})
            
        doc, creado = DocumentacionProveedor.objects.get_or_create(
            empresa=empresa_actual,
            proveedor=prov,
            nombre_documento=nombre_documento,
            mes=mes,
            anio=anio,
            defaults={'archivo': archivo, 'status': 'revision'}
        )
        if not creado:
            if doc.status == 'aprobado' and hasattr(request.user, 'proveedor_rh'):
                return JsonResponse({'success': False, 'error': 'No puedes modificar un documento que ya ha sido aprobado.'})
            if doc.archivo:
                try:
                    if os.path.exists(doc.archivo.path):
                        os.remove(doc.archivo.path)
                except Exception:
                    pass
            doc.archivo = archivo
            doc.status = 'revision'
            doc.comentario_rechazo = ''
            doc.save()
            
        # Enviar correo de notificación al contratista si existe
        if prov.contratista:
            try:
                # Nombre legible del documento
                dict_docs = dict(DocumentacionProveedor.NOMBRE_DOC_CHOICES)
                nombre_doc_humano = dict_docs.get(nombre_documento, nombre_documento)
                accion_str = "subido" if creado else "actualizado"

                # Asunto y Cuerpo
                asunto = f"Documento {accion_str} por proveedor: {prov.nombre_razon_social}"
                cuerpo = (
                    f"Estimado/a {prov.contratista.nombre_razon_social}:\n\n"
                    f"Le notificamos que el proveedor \"{prov.nombre_razon_social}\" ha {accion_str} "
                    f"el siguiente documento en el portal del sistema:\n\n"
                    f"• Documento: {nombre_doc_humano}\n"
                    f"• Período: {mes}/{anio}\n\n"
                    f"Se adjunta el archivo correspondiente para su revisión.\n\n"
                    f"Atentamente,\n"
                    f"Sistema CrossoverSuite"
                )

                from preferencias.utils import enviar_correo_contratista
                archivos_adjuntos = []
                if doc.archivo:
                    archivos_adjuntos.append(doc.archivo.path)

                enviar_correo_contratista(
                    contratista=prov.contratista,
                    asunto=asunto,
                    cuerpo=cuerpo,
                    archivos_adjuntos=archivos_adjuntos
                )
            except Exception as mail_err:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error al enviar correo de notificación de documento: {mail_err}")
            
        return JsonResponse({'success': True, 'message': 'Documento subido correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='/login/')
@require_POST
def eliminar_documento_proveedor_ajax(request, id):
    import os
    empresa_actual = get_empresa_actual(request)
    if hasattr(request.user, 'proveedor_rh'):
        doc = get_object_or_404(DocumentacionProveedor, id=id, proveedor=request.user.proveedor_rh, empresa=empresa_actual)
    else:
        doc = get_object_or_404(DocumentacionProveedor, id=id, empresa=empresa_actual)
        
    if doc.status == 'aprobado' and hasattr(request.user, 'proveedor_rh'):
        return JsonResponse({'success': False, 'error': 'No puedes eliminar un documento que ya ha sido aprobado.'})

    try:
        if doc.archivo:
            try:
                if os.path.exists(doc.archivo.path):
                    os.remove(doc.archivo.path)
            except Exception:
                pass
        doc.delete()
        return JsonResponse({'success': True, 'message': 'Documento eliminado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='/login/')
def descargar_documento_proveedor(request, doc_id):
    from django.core.exceptions import PermissionDenied
    from django.http import FileResponse, Http404
    import os
    
    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(DocumentacionProveedor, id=doc_id, empresa=empresa_actual)
    
    if hasattr(request.user, 'proveedor_rh'):
        if doc.proveedor != request.user.proveedor_rh:
            raise PermissionDenied("No tiene permiso para ver este documento.")
    else:
        from preferencias.permissions import user_has_hr_permission
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion_descargar'):
            raise PermissionDenied("No tiene permiso para descargar este documento.")
        
    if not doc.archivo:
        raise Http404("El archivo no existe.")
        
    path_archivo = doc.archivo.path
    if not os.path.exists(path_archivo):
        raise Http404("El archivo físico no fue encontrado en el servidor.")
        
    import mimetypes
    content_type, _ = mimetypes.guess_type(path_archivo)
    return FileResponse(open(path_archivo, 'rb'), content_type=content_type or 'application/octet-stream')


@login_required(login_url='/login/')
@require_POST
def cambiar_estatus_documento_proveedor_ajax(request, doc_id):
    from preferencias.permissions import user_has_hr_permission
    nuevo_estatus = request.POST.get('status')
    
    if nuevo_estatus == 'aprobado':
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion_aprobar'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para aprobar documentos.'}, status=403)
    elif nuevo_estatus == 'rechazado':
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion_rechazar'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para rechazar documentos.'}, status=403)
    else:
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para modificar este documento.'}, status=403)

    empresa_actual = get_empresa_actual(request)
    doc = get_object_or_404(DocumentacionProveedor, id=doc_id, empresa=empresa_actual)
    
    try:
        nuevo_estatus = request.POST.get('status')
        comentario = request.POST.get('comentario_rechazo', '').strip()
        
        if nuevo_estatus not in ['aprobado', 'rechazado', 'revision']:
            return JsonResponse({'success': False, 'error': 'Estatus inválido.'})
            
        doc.status = nuevo_estatus
        if nuevo_estatus == 'rechazado':
            doc.comentario_rechazo = comentario
        else:
            doc.comentario_rechazo = ''
        doc.save()
        
        return JsonResponse({'success': True, 'message': 'Estatus actualizado correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='/login/')
@require_POST
def api_probar_contratista_smtp(request):
    """
    Realiza una prueba rápida de conexión SMTP para el Contratista utilizando las credenciales enviadas.
    """
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa.'}, status=403)
        
    smtp_host = request.POST.get('smtp_host', '').strip()
    smtp_port_raw = request.POST.get('smtp_port', '587').strip()
    smtp_user = request.POST.get('smtp_user', '').strip()
    smtp_password = request.POST.get('smtp_password', '')
    
    use_ssl = request.POST.get('use_ssl') == 'true' or request.POST.get('use_ssl') == 'on' or request.POST.get('use_ssl') == True
    use_tls = False if use_ssl else (request.POST.get('use_tls') == 'true' or request.POST.get('use_tls') == 'on' or request.POST.get('use_tls') == True or request.POST.get('use_tls') is None)
    
    email_remitente = request.POST.get('email_remitente', '').strip()
    nombre_remitente = request.POST.get('nombre_remitente', '').strip()
    
    contratista_id = request.POST.get('contratista_id')
    
    if not smtp_host:
        return JsonResponse({'success': False, 'error': 'El host SMTP es obligatorio.'})
    if not smtp_user:
        return JsonResponse({'success': False, 'error': 'El usuario SMTP es obligatorio.'})
        
    # Si la contraseña viene vacía, intentamos recuperar la contraseña ya guardada del contratista
    if not smtp_password and contratista_id:
        try:
            from recursos_humanos.models import ContratistaCorreoSMTP
            smtp_config = ContratistaCorreoSMTP.objects.get(contratista_id=contratista_id)
            smtp_password = smtp_config.smtp_password
        except ContratistaCorreoSMTP.DoesNotExist:
            pass
            
    if not smtp_password:
        return JsonResponse({'success': False, 'error': 'La contraseña SMTP es obligatoria.'})

    try:
        from django.core.mail.backends.smtp import EmailBackend
        from django.core.mail import EmailMessage

        port = int(smtp_port_raw) if smtp_port_raw.isdigit() else 587
        if port == 465:
            use_ssl = True
            use_tls = False
        elif port in [587, 25] and use_ssl:
            use_ssl = False
            use_tls = True

        backend = EmailBackend(
            host=smtp_host,
            port=port,
            username=smtp_user,
            password=smtp_password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=10,
            fail_silently=False
        )

        asunto = "Prueba de Configuración SMTP - CrossoverSuite Contratista"
        cuerpo = (
            "Estimado usuario:\n\n"
            "La configuración del correo electrónico del contratista se ha realizado correctamente. Este mensaje confirma que la conexión SMTP funciona de manera adecuada.\n\n"
            f"Servidor: {smtp_host}\n"
            f"Usuario: {smtp_user}\n\n"
            "Atentamente,\n"
            "Sistema CrossoverSuite"
        )

        # El correo de prueba se envía a la misma cuenta SMTP configurada (auto-envío)
        destinatario = smtp_user

        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email=f"{nombre_remitente or 'Notificaciones'} <{email_remitente or smtp_user}>",
            to=[destinatario],
            connection=backend
        )

        email.send(fail_silently=False)
        return JsonResponse({'success': True, 'message': 'Conexión SMTP exitosa. Correo enviado.'})
        
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error de prueba SMTP de Contratista: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': f'Error de conexión SMTP: {str(e)}'})



