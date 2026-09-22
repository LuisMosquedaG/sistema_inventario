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
            contratistas = contratistas.filter(
                Q(registro_patronal__icontains=f_rp) |
                Q(registros_patronales_adicionales__registro_patronal__icontains=f_rp)
            ).distinct()
        if sucursal_id:
            contratistas = contratistas.filter(sucursal_id=sucursal_id)
            
        razones_sociales_unicas = Contratista.objects.filter(empresa=empresa_actual).exclude(nombre_razon_social='').values_list('nombre_razon_social', flat=True).distinct().order_by('nombre_razon_social')
        rfcs_unicos = Contratista.objects.filter(empresa=empresa_actual).exclude(rfc='').values_list('rfc', flat=True).distinct().order_by('rfc')
        
        from recursos_humanos.models import ContratistaRegistroPatronal
        rps_principales = list(Contratista.objects.filter(empresa=empresa_actual).exclude(registro_patronal='').exclude(registro_patronal__isnull=True).values_list('registro_patronal', flat=True))
        rps_adicionales = list(ContratistaRegistroPatronal.objects.filter(contratista__empresa=empresa_actual).exclude(registro_patronal='').values_list('registro_patronal', flat=True))
        reg_patronales_unicos = sorted(list(set(rps_principales + rps_adicionales)))
        
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
@require_hr_permission('contratistas', 'ver', json_response=True)
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

        # Obtener registros patronales adicionales
        registros_patronales_adicionales = list(
            cont.registros_patronales_adicionales.values_list('registro_patronal', flat=True)
        )

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
            'registros_patronales_adicionales': registros_patronales_adicionales,
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
            
        # Guardar registros patronales adicionales si se proporcionan
        registros_raw = data.get('registros_patronales_adicionales', '')
        if registros_raw:
            import json
            try:
                lista_rps = json.loads(registros_raw) if isinstance(registros_raw, str) and (registros_raw.startswith('[') or registros_raw.startswith('{')) else [r.strip() for r in str(registros_raw).split(',') if r.strip()]
            except Exception:
                lista_rps = [r.strip() for r in str(registros_raw).split(',') if r.strip()]
            
            from recursos_humanos.models import ContratistaRegistroPatronal
            for rp in lista_rps:
                rp_clean = str(rp).strip().upper()
                if rp_clean and rp_clean != (nuevo.registro_patronal or '').strip().upper():
                    ContratistaRegistroPatronal.objects.get_or_create(
                        contratista=nuevo,
                        registro_patronal=rp_clean
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
            
        # Guardar o actualizar registros patronales adicionales
        registros_raw = data.get('registros_patronales_adicionales', '')
        from recursos_humanos.models import ContratistaRegistroPatronal
        if registros_raw is not None:
            import json
            try:
                lista_rps = json.loads(registros_raw) if isinstance(registros_raw, str) and (registros_raw.startswith('[') or registros_raw.startswith('{')) else [r.strip() for r in str(registros_raw).split(',') if r.strip()]
            except Exception:
                lista_rps = [r.strip() for r in str(registros_raw).split(',') if r.strip()]
            
            rps_limpios = set()
            for rp in lista_rps:
                rp_clean = str(rp).strip().upper()
                if rp_clean and rp_clean != (cont.registro_patronal or '').strip().upper():
                    rps_limpios.add(rp_clean)
            
            # Eliminar los que ya no están
            ContratistaRegistroPatronal.objects.filter(contratista=cont).exclude(registro_patronal__in=rps_limpios).delete()
            # Crear los nuevos
            for rp_clean in rps_limpios:
                ContratistaRegistroPatronal.objects.get_or_create(contratista=cont, registro_patronal=rp_clean)

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
            if any(h in row_vals for h in ["registro federal de contribuyente", "rfc", "nombre denominacion o razon social", "cuatrimestre que declara", "cuatrimestre que se declara"]):
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
        ).filter(
            Q(vigencia_contrato__isnull=True) | Q(vigencia_contrato__gte=cuat_start)
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
                
            cp_val = str(ben.cp if ben else '').strip()
            if cp_val.isdigit() and len(cp_val) <= 5 and len(cp_val) > 0:
                cp_val = cp_val.zfill(5)

            data_rows.append([
                cuatrimestre, anio, str(contratista.rfc or ''), str(con.folio or ''), t_display, 
                con.objeto_contrato, con.monto_contrato, 
                con.vigencia_contrato.strftime('%d/%m/%Y') if con.vigencia_contrato else '',
                con.fecha_inicio.strftime('%d/%m/%Y') if con.fecha_inicio else '', 
                con.fecha_fin.strftime('%d/%m/%Y') if con.fecha_fin else '', 
                con.empleados.count(), 
                str(ben.rfc if ben else ''), str(ben.nombre_razon_social if ben else ''), str(ben.registro_patronal if ben else ''), 
                str(ben.calle if ben else ''), str(ben.num_ext if ben else ''), str(ben.num_int if ben else ''), 
                str(ben.entre_calle if ben else ''), str(ben.y_calle if ben else ''), str(ben.colonia if ben else ''), 
                cp_val, str(ben.municipio_alcaldia if ben else ''), str(ben.entidad_federativa if ben else ''), 
                str(ben.correo if ben else ''), str(ben.telefono if ben else '')
            ])

        rfc_clean = re.sub(r'[^A-Z0-9]', '', contratista.rfc.upper())
        
        if formato == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="Layout-detalle-contrato_{rfc_clean}.csv"'
            response.write(u'\ufeff'.encode('utf8'))
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(data_rows)
            return response
        else:
            from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Layout-detalle-contrato"
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
            for row_idx, row_data in enumerate(data_rows, 4):
                for col_idx, val in enumerate(row_data, 1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = border
                    cell.alignment = Alignment(vertical="center")
                    if col_idx in [1, 2, 8, 9, 10, 11, 14, 16, 17, 21, 25]:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    if col_idx in [3, 4, 12, 14, 21, 25]:
                        cell.number_format = '@'
            for i in range(1, 26): ws.column_dimensions[get_column_letter(i)].width = 18
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="Layout-detalle-contrato_{rfc_clean}.xlsx"'; wb.save(response)
            return response
    except Exception as e: return HttpResponse(f"Error al generar reporte: {str(e)}", status=500)

@login_required(login_url='/login/')
@require_hr_permission('contratistas', 'reporte_informacion')
def exportar_icsoe(request, id):
    empresa_actual = get_empresa_actual(request)
    try:
        contratista = get_object_or_404(Contratista, id=id, empresa=empresa_actual)
        cuat = request.GET.get('cuatrimestre', '1')
        anio = request.GET.get('anio', '')
        formato = request.GET.get('formato', 'excel')
        if not anio: return HttpResponse("Año requerido", status=400)
        
        import datetime
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        from .sua import obtener_rango_fechas_periodo

        cuat_num = int(cuat)
        anio_num = int(anio)
        if cuat_num == 1:
            cuat_start = datetime.date(anio_num, 1, 1)
            cuat_end = datetime.date(anio_num, 4, 30)
        elif cuat_num == 2:
            cuat_start = datetime.date(anio_num, 5, 1)
            cuat_end = datetime.date(anio_num, 8, 31)
        else:
            cuat_start = datetime.date(anio_num, 9, 1)
            cuat_end = datetime.date(anio_num, 12, 31)

        rfc_input_clean = re.sub(r'[^A-Z0-9]', '', (contratista.rfc or '').upper())
        rp_principal_clean = re.sub(r'[^A-Z0-9]', '', (contratista.registro_patronal or '').upper())
        rps_adicionales = set(
            re.sub(r'[^A-Z0-9]', '', (r.registro_patronal or '').upper())
            for r in contratista.registros_patronales_adicionales.all()
        )
        rps_contratista = ({rp_principal_clean} | rps_adicionales) - {''}

        # Buscar importaciones SUA de la empresa
        importaciones_qs = ImportacionSUA.objects.filter(empresa=empresa_actual)
        importaciones_validas = []

        for imp in importaciones_qs:
            # 1. Validar coincidencia de Contratista (RFC, Registros Patronales Principal/Adicionales o Razón Social)
            imp_rfc_clean = re.sub(r'[^A-Z0-9]', '', (imp.rfc_empresa or '').upper())
            imp_rp_clean = re.sub(r'[^A-Z0-9]', '', (imp.registro_patronal or '').upper())
            
            match_contratista = False
            if rfc_input_clean and rfc_input_clean != "POR_DEFINIR":
                if rfc_input_clean == imp_rfc_clean or rfc_input_clean in imp_rfc_clean or imp_rfc_clean in rfc_input_clean:
                    match_contratista = True
            if not match_contratista and imp_rp_clean:
                if imp_rp_clean in rps_contratista:
                    match_contratista = True
            if not match_contratista and contratista.nombre_razon_social and imp.nombre_razon_social:
                if contratista.nombre_razon_social.strip().upper() in imp.nombre_razon_social.strip().upper():
                    match_contratista = True

            if not match_contratista:
                continue

            # 2. Validar periodo cronológico del cuatrimestre
            try:
                imp_start, imp_end = obtener_rango_fechas_periodo(imp.periodo, imp.tipo)
                if imp_start <= cuat_end and imp_end >= cuat_start:
                    importaciones_validas.append(imp)
            except Exception:
                if str(anio_num) in (imp.periodo or ''):
                    importaciones_validas.append(imp)

        # 3. Obtener Contratos del Contratista en este cuatrimestre
        # 3. Obtener Contratos del Contratista en este cuatrimestre
        contratos_cuat = Contrato.objects.filter(
            contratista=contratista,
            empresa=empresa_actual,
            fecha_inicio__lte=cuat_end
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=cuat_start)
        ).filter(
            Q(vigencia_contrato__isnull=True) | Q(vigencia_contrato__gte=cuat_start)
        ).prefetch_related('empleados')

        tiene_contratos_global = Contrato.objects.filter(contratista=contratista, empresa=empresa_actual).exists()

        nss_contrato_set = set()
        curp_contrato_set = set()
        claves_beneficiarios = set()
        beneficiarios_cuat_ids = set()

        for con in contratos_cuat:
            if con.beneficiario_id:
                beneficiarios_cuat_ids.add(con.beneficiario_id)
                if con.beneficiario and con.beneficiario.clave:
                    claves_beneficiarios.add(con.beneficiario.clave.strip().upper())
            for emp in con.empleados.all():
                if emp.nss:
                    nss_clean = re.sub(r'[^0-9]', '', emp.nss).strip()[:11]
                    if nss_clean: nss_contrato_set.add(nss_clean)
                if emp.curp:
                    curp_clean = re.sub(r'[^A-Z0-9]', '', emp.curp.upper()).strip()[:18]
                    if curp_clean: curp_contrato_set.add(curp_clean)

        # Incluir también empleados de este contratista asignados a estos beneficiarios
        if beneficiarios_cuat_ids:
            empleados_directos = Empleado.objects.filter(
                empresa=empresa_actual,
                contratista=contratista,
                beneficiario_id__in=beneficiarios_cuat_ids
            )
            for emp in empleados_directos:
                if emp.nss:
                    nss_clean = re.sub(r'[^0-9]', '', emp.nss).strip()[:11]
                    if nss_clean: nss_contrato_set.add(nss_clean)
                if emp.curp:
                    curp_clean = re.sub(r'[^A-Z0-9]', '', emp.curp.upper()).strip()[:18]
                    if curp_clean: curp_contrato_set.add(curp_clean)

        # 4. Obtener Número STPS (del Contratista o de su Proveedor RH vinculado)
        numero_stps_val = (contratista.numero_stps or '').strip()
        if not numero_stps_val:
            prov = getattr(contratista, 'proveedores', None)
            if prov:
                p_first = prov.first()
                if p_first and p_first.numero_stps:
                    numero_stps_val = p_first.numero_stps.strip()

        # 5. Obtener lista ordenada y única de Registros Patronales
        lista_rps = []
        rp_clean_set = set()

        if contratista.registro_patronal and contratista.registro_patronal.strip():
            rp_p = contratista.registro_patronal.strip()
            rp_c = re.sub(r'[^A-Z0-9]', '', rp_p.upper())
            if rp_c:
                lista_rps.append(rp_p)
                rp_clean_set.add(rp_c)

        for r in contratista.registros_patronales_adicionales.all():
            if r.registro_patronal and r.registro_patronal.strip():
                rp_a = r.registro_patronal.strip()
                rp_c = re.sub(r'[^A-Z0-9]', '', rp_a.upper())
                if rp_c and rp_c not in rp_clean_set:
                    lista_rps.append(rp_a)
                    rp_clean_set.add(rp_c)

        for imp in importaciones_validas:
            if imp.registro_patronal and imp.registro_patronal.strip():
                rp_i = imp.registro_patronal.strip()
                rp_c = re.sub(r'[^A-Z0-9]', '', rp_i.upper())
                if rp_c and rp_c not in rp_clean_set:
                    lista_rps.append(rp_i)
                    rp_clean_set.add(rp_c)

        if not lista_rps:
            lista_rps = [contratista.registro_patronal or '']

        # 6. Calcular Aportaciones y Amortizaciones POR CADA Registro Patronal
        headers = ["Cuatrimestre que se declara", "Año que se declara", "Registro Federal de Contribuyente", "Nombre denominacion o razon social", "Correo electronico", "Telefono (numero extension)", "Registro patronal", "Calle", "Numero exterior", "Numero interior", "Entre calle", "Y calle", "Colonia", "Codigo Postal", "Municipio o Alcaldia", "Entidad Federativa", "Representante legal", "Administrador Unico", "Numero de escritura", "Nombre del Notario Publico", "Numero de Notario Publico", "Fecha de escritura publica", "Folio mercantil", "Aportacion sin credito de los trabajadores del contrato", "Aportacion con credito de los trabajadores del contrato", "Amortizacion de los trabajadores del contrato", "Numero de registro ante la Secretaria de Trabajo y Prevision Social"]
        
        data_rows = []
        for rp_actual in lista_rps:
            rp_actual_clean = re.sub(r'[^A-Z0-9]', '', (rp_actual or '').upper())
            
            # Filtrar importaciones que corresponden a este registro patronal
            importaciones_rp = []
            for imp in importaciones_validas:
                imp_rp_clean = re.sub(r'[^A-Z0-9]', '', (imp.registro_patronal or '').upper())
                if rp_actual_clean and imp_rp_clean == rp_actual_clean:
                    importaciones_rp.append(imp)
                elif not rp_actual_clean and not imp_rp_clean:
                    importaciones_rp.append(imp)
            
            total_sin_credito = Decimal('0')
            total_con_credito = Decimal('0')
            total_amortizaciones = Decimal('0')

            for imp in importaciones_rp:
                for t in imp.trabajadores.all():
                    t_nss_clean = re.sub(r'[^0-9]', '', t.nss or '').strip()[:11]
                    t_curp_clean = re.sub(r'[^A-Z0-9]', '', (t.rfc_curp or '').upper()).strip()[:18]
                    clave_t = (t.clave_ubicacion or '').strip().upper()

                    is_match = False
                    if t_nss_clean and t_nss_clean in nss_contrato_set:
                        is_match = True
                    elif t_curp_clean and t_curp_clean in curp_contrato_set:
                        is_match = True
                    elif clave_t and clave_t in claves_beneficiarios:
                        is_match = True
                    elif not nss_contrato_set and not claves_beneficiarios and not tiene_contratos_global:
                        is_match = True

                    if is_match:
                        val_inf = (t.tipo_valor_infonavit or '').strip()
                        if not val_inf or val_inf == '-':
                            total_sin_credito += (t.aportacion_patronal or Decimal('0'))
                        else:
                            total_con_credito += (t.aportacion_patronal or Decimal('0'))
                        total_amortizaciones += (t.amortizacion or Decimal('0'))

            total_sin_credito_red = total_sin_credito.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            total_con_credito_red = total_con_credito.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            total_amortizaciones_red = total_amortizaciones.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            rp_sin_guiones = re.sub(r'[^A-Z0-9]', '', (rp_actual or '').upper())

            cp_val = str(contratista.cp or '').strip()
            if cp_val.isdigit() and len(cp_val) <= 5 and len(cp_val) > 0:
                cp_val = cp_val.zfill(5)

            row = [
                cuat, anio, str(contratista.rfc or ''), str(contratista.nombre_razon_social or ''), 
                str(contratista.correo or ''), str(contratista.telefono or ''), rp_sin_guiones, 
                str(contratista.calle or ''), str(contratista.num_ext or ''), str(contratista.num_int or ''), str(contratista.entre_calle or ''), 
                str(contratista.y_calle or ''), str(contratista.colonia or ''), cp_val, str(contratista.municipio_alcaldia or ''), 
                str(contratista.entidad_federativa or ''), str(contratista.representante_legal or ''), str(contratista.administrador_unico or ''), 
                str(contratista.num_escritura or ''), str(contratista.nombre_notario_publico or ''), str(contratista.num_notario_publico or ''), 
                contratista.fecha_escritura_publica.strftime('%d/%m/%Y') if contratista.fecha_escritura_publica else '', 
                str(contratista.folio_mercantil or ''), 
                total_sin_credito_red, total_con_credito_red, total_amortizaciones_red, 
                str(numero_stps_val or '')
            ]
            data_rows.append(row)

        if formato == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="Layout-informacion-sujeto-obligado_{rfc_input_clean}_{anio}_C{cuat}.csv"'
            response.write(u'\ufeff'.encode('utf8'))
            writer = csv.writer(response)
            writer.writerow(headers)
            for r_data in data_rows:
                writer.writerow(r_data)
            return response
        else:
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Layout-info-sujeto-obligado"
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
            
            curr_row = 4
            for r_data in data_rows:
                ws.append(r_data)
                for col_idx in [24, 25, 26]: ws.cell(row=curr_row, column=col_idx).number_format = '"$"#,##0.00'
                for col_idx in [3, 6, 7, 14, 27]: ws.cell(row=curr_row, column=col_idx).number_format = '@'
                for col_idx in range(1, 28): ws.cell(row=curr_row, column=col_idx).border = border
                curr_row += 1
                
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="Layout-informacion-sujeto-obligado_{rfc_input_clean}_{anio}_C{cuat}.xlsx"'; wb.save(response)
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
    
    import datetime as dt
    from .sua import obtener_rango_fechas_periodo

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
    
    # Identificadores del contratista
    rfc_clean_input = re.sub(r'[^A-Z0-9]', '', (contratista.rfc or '').upper())
    rp_principal_clean = re.sub(r'[^A-Z0-9]', '', (contratista.registro_patronal or '').upper())
    rps_adicionales = set(
        re.sub(r'[^A-Z0-9]', '', (r.registro_patronal or '').upper())
        for r in contratista.registros_patronales_adicionales.all()
    )
    rps_contratista = ({rp_principal_clean} | rps_adicionales) - {''}

    # Buscar Importaciones SUA
    importaciones_qs = ImportacionSUA.objects.filter(empresa=empresa_actual)
    importaciones_validas = []

    for imp in importaciones_qs:
        imp_rfc_clean = re.sub(r'[^A-Z0-9]', '', (imp.rfc_empresa or '').upper())
        imp_rp_clean = re.sub(r'[^A-Z0-9]', '', (imp.registro_patronal or '').upper())
        
        match_contratista = False
        if rfc_clean_input and rfc_clean_input != "POR_DEFINIR":
            if rfc_clean_input == imp_rfc_clean or rfc_clean_input in imp_rfc_clean or imp_rfc_clean in rfc_clean_input:
                match_contratista = True
        if not match_contratista and imp_rp_clean:
            if imp_rp_clean in rps_contratista:
                match_contratista = True
        if not match_contratista and contratista.nombre_razon_social and imp.nombre_razon_social:
            if contratista.nombre_razon_social.strip().upper() in imp.nombre_razon_social.strip().upper():
                match_contratista = True

        if not match_contratista:
            continue

        try:
            imp_start, imp_end = obtener_rango_fechas_periodo(imp.periodo, imp.tipo)
            if imp_start <= cuat_end and imp_end >= cuat_start:
                importaciones_validas.append(imp)
        except Exception:
            if str(anio_int) in (imp.periodo or ''):
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
                ).filter(
                    Q(vigencia_contrato__isnull=True) | Q(vigencia_contrato__gte=cuat_start)
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
        response['Content-Disposition'] = f'attachment; filename="Carga_Trabajadores_{contratista.rfc}{filename_suffix}_{anio}_C{cuat}.csv"'
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
        ws.title = "Carga trabajadores"
        
        headers = ['NSS(11 dígitos)', 'CURP(18 caracteres)', 'Salario base de cotización(numérico con 2 decimales)']
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=i, value=h)
            cell.font = Font(bold=True)
        
        row_num = 2
        for nss in sorted(trabajadores_data.keys()):
            d = trabajadores_data[nss]
            nss_clean = str(d['nss'] or '').strip()
            if nss_clean.isdigit() and len(nss_clean) <= 11 and len(nss_clean) > 0:
                nss_clean = nss_clean.zfill(11)
            c1 = ws.cell(row=row_num, column=1, value=nss_clean)
            c1.number_format = '@'
            c2 = ws.cell(row=row_num, column=2, value=str(d['curp'] or ''))
            c2.number_format = '@'
            ws.cell(row=row_num, column=3, value=d['sbc']).number_format = '0.00'
            row_num += 1
            
        for i in range(1, 4):
            ws.column_dimensions[get_column_letter(i)].width = 30
            
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="Carga_Trabajadores_{contratista.rfc}{filename_suffix}_{anio}_C{cuat}.xlsx"'
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
    
    catalogo = DocumentacionProveedor.CATALOGO_DOCUMENTOS
    
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
                
            doc = docs_existentes.filter(nombre_documento=code, mes=p).first()
            if doc:
                if doc.status == 'aprobado':
                    totales_resumen['aprobados'] += 1
                elif doc.status == 'revision':
                    totales_resumen['revision'] += 1
                elif doc.status == 'rechazado':
                    totales_resumen['rechazados'] += 1
            else:
                totales_resumen['vacio'] += 1
                
            periodos_list.append({
                'num': p,
                'colspan': colspan,
                'short_label': short_lbl,
                'label': full_lbl,
                'id': doc.id if doc else None,
                'url': reverse('descargar_documento_proveedor', args=[doc.id]) if doc else None,
                'nombre_archivo': doc.archivo.name.split('/')[-1] if doc else None,
                'estatus': doc.status if doc else None,
                'estatus_display': doc.get_status_display() if doc else None,
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
        'proveedor': prov.nombre_razon_social,
        'anio': anio,
        'matrix': matrix,
        'resumen': totales_resumen
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
            
        dict_catalogo = {d['codigo']: d for d in DocumentacionProveedor.CATALOGO_DOCUMENTOS}
        doc_meta = dict_catalogo.get(nombre_documento, {})
        nombre_doc_humano = doc_meta.get('nombre', nombre_documento)
        periodo_tipo = doc_meta.get('periodo', 'mensual')
        formato_esperado = doc_meta.get('formato', 'pdf')
        
        # Validar extensión de archivo estrictamente según el formato indicado
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
                dict_catalogo = {d['codigo']: d for d in DocumentacionProveedor.CATALOGO_DOCUMENTOS}
                doc_meta = dict_catalogo.get(nombre_documento, {})
                nombre_doc_humano = doc_meta.get('nombre', nombre_documento)
                periodo_tipo = doc_meta.get('periodo', 'mensual')
                accion_str = "subido" if creado else "actualizado"

                meses_nombres = {
                    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                }
                bimestres_nombres = {
                    1: '1er Bimestre (Ene-Feb)', 2: '2do Bimestre (Mar-Abr)', 3: '3er Bimestre (May-Jun)',
                    4: '4to Bimestre (Jul-Ago)', 5: '5to Bimestre (Sep-Oct)', 6: '6to Bimestre (Nov-Dic)'
                }
                cuatrimestres_nombres = {
                    1: '1er Cuatrimestre (Ene-Abr)', 2: '2do Cuatrimestre (May-Ago)', 3: '3er Cuatrimestre (Sep-Dic)'
                }
                
                if periodo_tipo == 'mensual':
                    periodo_str = f"{meses_nombres.get(mes, f'Mes {mes}')} {anio}"
                elif periodo_tipo == 'bimestral':
                    periodo_str = f"{bimestres_nombres.get(mes, f'Bimestre {mes}')} {anio}"
                elif periodo_tipo == 'cuatrimestral':
                    periodo_str = f"{cuatrimestres_nombres.get(mes, f'Cuatrimestre {mes}')} {anio}"
                else: # unica_ocasion
                    periodo_str = f"Única Ocasión (Ejercicio {anio})"

                # Asunto y Cuerpo HTML con diseño institucional
                asunto = f"Documento {accion_str} por proveedor: {prov.nombre_razon_social}"
                cuerpo = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; line-height: 1.6; max-width: 700px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
                    <div style="background-color: #1a252f; padding: 18px 24px; border-bottom: 4px solid #00b8b9;">
                        <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">CrossoverSuite</h2>
                        <span style="color: #94a3b8; font-size: 13px;">Gestión de Documentos de Proveedores</span>
                    </div>
                    
                    <div style="padding: 24px 28px;">
                        <p style="font-size: 15px; margin-top: 0; margin-bottom: 14px;">
                            Estimado/a <strong>{prov.contratista.nombre_razon_social}</strong>,
                        </p>
                        <p style="font-size: 14px; margin-bottom: 14px; color: #475569;">
                            Le notificamos que el proveedor <strong>{prov.nombre_razon_social}</strong> ha <strong>{accion_str}</strong> un documento en la plataforma del sistema para su revisión:
                        </p>
                        
                        <div style="overflow-x: auto; margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 6px;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; white-space: nowrap;">
                                <thead>
                                    <tr style="background-color: #1a252f; color: #ffffff; white-space: nowrap;">
                                        <th style="padding: 8px 12px; font-weight: 600;">Proveedor</th>
                                        <th style="padding: 8px 12px; font-weight: 600;">Documento</th>
                                        <th style="padding: 8px 12px; font-weight: 600; text-align: center;">Período</th>
                                        <th style="padding: 8px 12px; font-weight: 600; text-align: center;">Estatus</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr style="background-color: #f8fafc; white-space: nowrap;">
                                        <td style="padding: 9px 12px; font-weight: 600; color: #1e293b;">{prov.nombre_razon_social}</td>
                                        <td style="padding: 9px 12px; color: #334155;">{nombre_doc_humano}</td>
                                        <td style="padding: 9px 12px; color: #475569; text-align: center;">{periodo_str}</td>
                                        <td style="padding: 9px 12px; text-align: center;">
                                            <span style="background-color: #fff9db; color: #f59f00; border: 1px solid #ffec99; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                                                En Revisión
                                            </span>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        
                        <div style="background-color: #f0fdfa; border-left: 4px solid #00b8b9; padding: 14px 16px; border-radius: 4px; margin: 20px 0; font-size: 13.5px; color: #134e4a;">
                            <strong>ℹ️ Nota:</strong> Se adjunta el archivo correspondiente para su revisión. También puede revisarlo, aprobarlo o rechazarlo directamente desde la plataforma.
                        </div>
                        
                        <div style="text-align: center; margin: 26px 0 20px 0;">
                            <a href="https://suite.crossovermx.com/login/" target="_blank" style="background-color: #00b8b9; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                Ingresar al Panel de Control
                            </a>
                        </div>
                        
                        <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; font-size: 13px; color: #64748b;">
                            Atentamente,<br>
                            <strong style="color: #1e293b; font-size: 14px;">{prov.nombre_razon_social}</strong><br>
                            <span>Sistema CrossoverSuite</span>
                        </div>
                    </div>
                    
                    <div style="background-color: #f8fafc; padding: 12px 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 11.5px; color: #94a3b8;">
                        Este es un mensaje automático emitido por la plataforma de gestión de contratistas y proveedores.
                    </div>
                </div>
                """.strip()

                from preferencias.utils import enviar_correo_contratista
                archivos_adjuntos = []
                if doc.archivo:
                    archivos_adjuntos.append(doc.archivo.path)

                enviar_correo_contratista(
                    contratista=prov.contratista,
                    asunto=asunto,
                    cuerpo=cuerpo,
                    archivos_adjuntos=archivos_adjuntos,
                    es_html=True
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
        if doc.status == 'aprobado':
            return JsonResponse({'success': False, 'error': 'No puedes eliminar un documento que ya ha sido aprobado.'})
    else:
        from preferencias.permissions import user_has_hr_permission
        if not user_has_hr_permission(request, 'proveedores_contratistas', 'eliminar') and not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion') and not user_has_hr_permission(request, 'proveedores_contratistas', 'ver'):
            return JsonResponse({'success': False, 'error': 'No cuentas con permiso para eliminar documentos.'}, status=403)
        doc = get_object_or_404(DocumentacionProveedor, id=id, empresa=empresa_actual)

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
        
        # Enviar correo de notificación al proveedor si el estatus es 'aprobado' o 'rechazado'
        if nuevo_estatus in ['aprobado', 'rechazado']:
            try:
                prov = doc.proveedor
                email_destino = (prov.correo or (prov.usuario.email if prov.usuario else '') or '').strip()
                if email_destino:
                    from preferencias.utils import enviar_correo_contratista
                    
                    dict_catalogo = {d['codigo']: d for d in DocumentacionProveedor.CATALOGO_DOCUMENTOS}
                    doc_meta = dict_catalogo.get(doc.nombre_documento, {})
                    nombre_doc_humano = doc_meta.get('nombre', doc.nombre_documento)
                    periodo_tipo = doc_meta.get('periodo', 'mensual')
                    
                    meses_nombres = {
                        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                    }
                    bimestres_nombres = {
                        1: '1er Bimestre (Ene-Feb)', 2: '2do Bimestre (Mar-Abr)', 3: '3er Bimestre (May-Jun)',
                        4: '4to Bimestre (Jul-Ago)', 5: '5to Bimestre (Sep-Oct)', 6: '6to Bimestre (Nov-Dic)'
                    }
                    cuatrimestres_nombres = {
                        1: '1er Cuatrimestre (Ene-Abr)', 2: '2do Cuatrimestre (May-Ago)', 3: '3er Cuatrimestre (Sep-Dic)'
                    }
                    
                    if periodo_tipo == 'mensual':
                        periodo_str = f"{meses_nombres.get(doc.mes, f'Mes {doc.mes}')} {doc.anio}"
                    elif periodo_tipo == 'bimestral':
                        periodo_str = f"{bimestres_nombres.get(doc.mes, f'Bimestre {doc.mes}')} {doc.anio}"
                    elif periodo_tipo == 'cuatrimestral':
                        periodo_str = f"{cuatrimestres_nombres.get(doc.mes, f'Cuatrimestre {doc.mes}')} {doc.anio}"
                    else: # unica_ocasion
                        periodo_str = f"Única Ocasión (Ejercicio {doc.anio})"

                    nombre_contratista = prov.contratista.nombre_razon_social if prov.contratista else (doc.empresa.nombre if doc.empresa else "Contratista")
                    
                    if nuevo_estatus == 'aprobado':
                        asunto = f"Documento Aceptado - {nombre_doc_humano} ({periodo_str})"
                        cuerpo = f"""
                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; line-height: 1.6; max-width: 700px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
                            <div style="background-color: #1a252f; padding: 18px 24px; border-bottom: 4px solid #00b8b9;">
                                <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">CrossoverSuite</h2>
                                <span style="color: #94a3b8; font-size: 13px;">Gestión de Documentos de Proveedores</span>
                            </div>
                            
                            <div style="padding: 24px 28px;">
                                <p style="font-size: 15px; margin-top: 0; margin-bottom: 14px;">
                                    Estimado/a <strong>{prov.nombre_razon_social}</strong>,
                                </p>
                                <p style="font-size: 14px; margin-bottom: 14px; color: #475569;">
                                    Le informamos que el siguiente documento ha sido revisado y su estatus ha sido actualizado a <strong>Aceptado</strong> por <strong>{nombre_contratista}</strong>:
                                </p>
                                
                                <div style="overflow-x: auto; margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 6px;">
                                    <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; white-space: nowrap;">
                                        <thead>
                                            <tr style="background-color: #1a252f; color: #ffffff; white-space: nowrap;">
                                                <th style="padding: 8px 12px; font-weight: 600;">Contratista</th>
                                                <th style="padding: 8px 12px; font-weight: 600;">Documento</th>
                                                <th style="padding: 8px 12px; font-weight: 600; text-align: center;">Período</th>
                                                <th style="padding: 8px 12px; font-weight: 600; text-align: center;">Estatus</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr style="background-color: #f8fafc; white-space: nowrap;">
                                                <td style="padding: 9px 12px; font-weight: 600; color: #1e293b;">{nombre_contratista}</td>
                                                <td style="padding: 9px 12px; color: #334155;">{nombre_doc_humano}</td>
                                                <td style="padding: 9px 12px; color: #475569; text-align: center;">{periodo_str}</td>
                                                <td style="padding: 9px 12px; text-align: center;">
                                                    <span style="background-color: #ebfbee; color: #2f9e44; border: 1px solid #b2f2bb; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                                                        Aceptado
                                                    </span>
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                                
                                <div style="background-color: #f0fdf4; border-left: 4px solid #22c55e; padding: 14px 16px; border-radius: 4px; margin: 20px 0; font-size: 13.5px; color: #14532d;">
                                    <strong>✓ Documento Aprobado:</strong> Su documento cumple satisfactoriamente con los requerimientos y ha sido registrado con estatus Aceptado en el expediente.
                                </div>
                                
                                <div style="text-align: center; margin: 26px 0 20px 0;">
                                    <a href="https://suite.crossovermx.com/login/" target="_blank" style="background-color: #00b8b9; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                        Ingresar al Portal de Documentación
                                    </a>
                                </div>
                                
                                <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; font-size: 13px; color: #64748b;">
                                    Atentamente,<br>
                                    <strong style="color: #1e293b; font-size: 14px;">{nombre_contratista}</strong><br>
                                    <span>Sistema CrossoverSuite</span>
                                </div>
                            </div>
                            
                            <div style="background-color: #f8fafc; padding: 12px 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 11.5px; color: #94a3b8;">
                                Este es un mensaje automático emitido por la plataforma de gestión de contratistas y proveedores.
                            </div>
                        </div>
                        """.strip()
                    else:
                        asunto = f"Documento Rechazado - {nombre_doc_humano} ({periodo_str})"
                        motivo_texto = comentario if comentario else "El documento presentado requiere corrección."
                        cuerpo = f"""
                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; line-height: 1.6; max-width: 700px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
                            <div style="background-color: #1a252f; padding: 18px 24px; border-bottom: 4px solid #00b8b9;">
                                <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">CrossoverSuite</h2>
                                <span style="color: #94a3b8; font-size: 13px;">Gestión de Documentos de Proveedores</span>
                            </div>
                            
                            <div style="padding: 24px 28px;">
                                <p style="font-size: 15px; margin-top: 0; margin-bottom: 14px;">
                                    Estimado/a <strong>{prov.nombre_razon_social}</strong>,
                                </p>
                                <p style="font-size: 14px; margin-bottom: 14px; color: #475569;">
                                    Le informamos que el siguiente documento ha sido revisado y su estatus ha sido actualizado a <strong>Rechazado</strong> por <strong>{nombre_contratista}</strong>:
                                </p>
                                
                                <div style="overflow-x: auto; margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 6px;">
                                    <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; white-space: nowrap;">
                                        <thead>
                                            <tr style="background-color: #1a252f; color: #ffffff; white-space: nowrap;">
                                                <th style="padding: 8px 12px; font-weight: 600;">Contratista</th>
                                                <th style="padding: 8px 12px; font-weight: 600;">Documento</th>
                                                <th style="padding: 8px 12px; font-weight: 600; text-align: center;">Período</th>
                                                <th style="padding: 8px 12px; font-weight: 600; text-align: center;">Estatus</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr style="background-color: #f8fafc; white-space: nowrap;">
                                                <td style="padding: 9px 12px; font-weight: 600; color: #1e293b;">{nombre_contratista}</td>
                                                <td style="padding: 9px 12px; color: #334155;">{nombre_doc_humano}</td>
                                                <td style="padding: 9px 12px; color: #475569; text-align: center;">{periodo_str}</td>
                                                <td style="padding: 9px 12px; text-align: center;">
                                                    <span style="background-color: #fff5f5; color: #e03131; border: 1px solid #ffc9c9; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                                                        Rechazado
                                                    </span>
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                                
                                <div style="background-color: #fff5f5; border-left: 4px solid #ef4444; padding: 14px 16px; border-radius: 4px; margin: 20px 0; font-size: 13.5px; color: #7f1d1d;">
                                    <strong>⚠️ Motivo de Cancelación / Rechazo:</strong><br>
                                    <span style="color: #991b1b; display: block; margin-top: 4px; font-weight: 500;">{motivo_texto}</span>
                                </div>
                                
                                <div style="background-color: #f0fdfa; border-left: 4px solid #00b8b9; padding: 14px 16px; border-radius: 4px; margin: 20px 0; font-size: 13.5px; color: #134e4a;">
                                    <strong>Acción requerida:</strong> Por favor ingrese al portal del sistema para solventar la observación y subir el archivo corregido.
                                </div>
                                
                                <div style="text-align: center; margin: 26px 0 20px 0;">
                                    <a href="https://suite.crossovermx.com/login/" target="_blank" style="background-color: #00b8b9; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                        Ingresar al Portal para Corregir
                                    </a>
                                </div>
                                
                                <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; font-size: 13px; color: #64748b;">
                                    Atentamente,<br>
                                    <strong style="color: #1e293b; font-size: 14px;">{nombre_contratista}</strong><br>
                                    <span>Sistema CrossoverSuite</span>
                                </div>
                            </div>
                            
                            <div style="background-color: #f8fafc; padding: 12px 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 11.5px; color: #94a3b8;">
                                Este es un mensaje automático emitido por la plataforma de gestión de contratistas y proveedores.
                            </div>
                        </div>
                        """.strip()

                    enviar_correo_contratista(
                        contratista=prov.contratista,
                        asunto=asunto,
                        cuerpo=cuerpo,
                        destinatarios=[email_destino],
                        es_html=True
                    )
            except Exception as mail_err:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error al enviar correo de notificación de estatus al proveedor: {mail_err}")
        
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


@login_required(login_url='/login/')
def descargar_plantilla_reporte_trabajadores(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla Trabajadores"

    fill_group = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
    fill_head = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    border = Border(
        left=Side(style='thin', color="B2B2B2"),
        right=Side(style='thin', color="B2B2B2"),
        top=Side(style='thin', color="B2B2B2"),
        bottom=Side(style='thin', color="B2B2B2")
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 1. Fila 1: Grupos
    # Proveedor (A-C), Contrato (D-E), Informacion del colaborador (F-S)
    ws.merge_cells('A1:C1')
    ws.merge_cells('D1:E1')
    ws.merge_cells('F1:S1')

    ws['A1'] = "Proveedor"
    ws['D1'] = "Contrato"
    ws['F1'] = "Informacion del colaborador"

    for col in range(1, 20):
        cell = ws.cell(row=1, column=col)
        cell.fill = fill_group
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.alignment = center_align
        cell.border = border

    # 2. Fila 2: Columnas
    headers = [
        "Consecutivo",
        "RFC Proveedor",
        "Registro Patronal Proveedor",
        "# Contrato",
        "Nombre del contrato",
        "Primer Apellido",
        "Segundo Apellido",
        "Nombre (s)",
        "Género",
        "RFC",
        "CURP",
        "NSS",
        "Puesto Desempeñado",
        "Tipo de Personal",
        "SBC",
        "Dias Pagados",
        "Estatus Colaborador",
        "Fecha de Ingreso",
        "Fecha de Baja"
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_idx, value=h)
        cell.fill = fill_head
        cell.font = Font(name="Calibri", size=10, bold=True, color="000000")
        cell.alignment = center_align
        cell.border = border

    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 28

    col_widths = {
        1: 14,  # Consecutivo
        2: 18,  # RFC Proveedor
        3: 26,  # Registro Patronal Proveedor
        4: 18,  # # Contrato
        5: 26,  # Nombre del contrato
        6: 18,  # Primer Apellido
        7: 18,  # Segundo Apellido
        8: 22,  # Nombre (s)
        9: 12,  # Género
        10: 16, # RFC
        11: 22, # CURP
        12: 16, # NSS
        13: 24, # Puesto Desempeñado
        14: 18, # Tipo de Personal
        15: 14, # SBC
        16: 14, # Dias Pagados
        17: 20, # Estatus Colaborador
        18: 18, # Fecha de Ingreso
        19: 18, # Fecha de Baja
    }

    for col_idx, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Plantilla_Reporte_Trabajadores_Servicio_Especializado.xlsx"'
    wb.save(response)
    return response


def obtener_documentos_pendientes_proveedor(prov, anio, fecha_referencia=None):
    """
    Retorna la lista de documentos que no se han subido o están rechazados
    para los períodos transcurridos hasta la fecha de referencia en el año indicado.
    """
    if fecha_referencia is None:
        fecha_referencia = datetime.now()
        
    cur_year = fecha_referencia.year
    cur_month = fecha_referencia.month
    
    docs_existentes = DocumentacionProveedor.objects.filter(proveedor=prov, anio=anio)
    
    meses_nombres = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    bimestres_nombres = {
        1: '1er Bimestre (Ene-Feb)', 2: '2do Bimestre (Mar-Abr)', 3: '3er Bimestre (May-Jun)',
        4: '4to Bimestre (Jul-Ago)', 5: '5to Bimestre (Sep-Oct)', 6: '6to Bimestre (Nov-Dic)'
    }
    cuatrimestres_nombres = {
        1: '1er Cuatrimestre (Ene-Abr)', 2: '2do Cuatrimestre (May-Ago)', 3: '3er Cuatrimestre (Sep-Dic)'
    }
    
    if anio < cur_year:
        max_mes = 12
        max_bim = 6
        max_cuatri = 3
        max_unica = 1
    elif anio == cur_year:
        max_mes = cur_month
        max_bim = min(6, (cur_month + 1) // 2)
        max_cuatri = min(3, (cur_month + 3) // 4)
        max_unica = 1
    else: # Año futuro
        max_mes = 0
        max_bim = 0
        max_cuatri = 0
        max_unica = 0

    pendientes = []
    
    for item in DocumentacionProveedor.CATALOGO_DOCUMENTOS:
        codigo = item['codigo']
        nombre = item['nombre']
        periodo_tipo = item['periodo']
        formato = item.get('formato', 'pdf').upper()
        
        if periodo_tipo == 'mensual':
            limit = max_mes
        elif periodo_tipo == 'bimestral':
            limit = max_bim
        elif periodo_tipo == 'cuatrimestral':
            limit = max_cuatri
        else: # unica_ocasion
            limit = max_unica
            
        for p in range(1, limit + 1):
            doc = docs_existentes.filter(nombre_documento=codigo, mes=p).first()
            if not doc or doc.status == 'rechazado':
                if periodo_tipo == 'mensual':
                    periodo_str = f"{meses_nombres.get(p, f'Mes {p}')} {anio}"
                elif periodo_tipo == 'bimestral':
                    periodo_str = f"{bimestres_nombres.get(p, f'Bimestre {p}')} {anio}"
                elif periodo_tipo == 'cuatrimestral':
                    periodo_str = f"{cuatrimestres_nombres.get(p, f'Cuatrimestre {p}')} {anio}"
                else:
                    periodo_str = f"Única Ocasión ({anio})"
                    
                estatus_detalle = "Sin documento"
                if doc and doc.status == 'rechazado':
                    estatus_detalle = f"Rechazado ({doc.comentario_rechazo or 'Requiere corrección'})"
                    
                pendientes.append({
                    'codigo': codigo,
                    'nombre': nombre,
                    'periodo_num': p,
                    'periodo_str': periodo_str,
                    'formato': formato,
                    'estatus': estatus_detalle,
                    'es_rechazado': bool(doc and doc.status == 'rechazado')
                })
                
    return pendientes


@login_required(login_url='/login/')
def preparar_correo_recordatorio_proveedor_ajax(request, id):
    from preferencias.permissions import user_has_hr_permission
    if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion') and not user_has_hr_permission(request, 'proveedores_contratistas', 'ver') and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No cuentas con permiso para esta acción.'}, status=403)
        
    empresa_actual = get_empresa_actual(request)
    prov = get_object_or_404(ProveedorRH, id=id, empresa=empresa_actual)
    
    try:
        anio = int(request.GET.get('anio') or datetime.now().year)
    except ValueError:
        anio = datetime.now().year
        
    pendientes = obtener_documentos_pendientes_proveedor(prov, anio)
    
    nombre_contratista = prov.contratista.nombre_razon_social if prov.contratista else (empresa_actual.nombre if empresa_actual else "Contratista")
    destinatario = (prov.correo or (prov.usuario.email if prov.usuario else '') or '').strip()
    asunto = f"Recordatorio de Documentación Pendiente ({anio}) - {prov.nombre_razon_social}"
    
    portal_url = "https://suite.crossovermx.com/login/"
    
    # Construir filas de la tabla de documentos en una sola línea compacta
    if pendientes:
        filas_html = ""
        for idx, doc in enumerate(pendientes, 1):
            color_badge = "#e03131" if not doc['es_rechazado'] else "#d97706"
            bg_badge = "#fff5f5" if not doc['es_rechazado'] else "#fffbeb"
            border_badge = "#ffc9c9" if not doc['es_rechazado'] else "#fde68a"
            
            filas_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; white-space: nowrap; {'background-color: #f8fafc;' if idx % 2 == 0 else ''}">
                <td style="padding: 7px 10px; color: #64748b; font-weight: bold; text-align: center; white-space: nowrap;">{idx}</td>
                <td style="padding: 7px 10px; font-weight: 600; color: #1e293b; white-space: nowrap;">{doc['nombre']}</td>
                <td style="padding: 7px 10px; color: #475569; text-align: center; white-space: nowrap;">{doc['periodo_str']}</td>
                <td style="padding: 7px 10px; text-align: center; white-space: nowrap;">
                    <span style="display: inline-block; background-color: {bg_badge}; color: {color_badge}; border: 1px solid {border_badge}; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap;">
                        {doc['estatus']}
                    </span>
                </td>
            </tr>
            """
        tabla_html = f"""
        <div style="overflow-x: auto; margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 6px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; white-space: nowrap;">
                <thead>
                    <tr style="background-color: #1a252f; color: #ffffff; white-space: nowrap;">
                        <th style="padding: 8px 10px; font-weight: 600; text-align: center; width: 30px; white-space: nowrap;">#</th>
                        <th style="padding: 8px 10px; font-weight: 600; white-space: nowrap;">Documento Requerido</th>
                        <th style="padding: 8px 10px; font-weight: 600; text-align: center; white-space: nowrap;">Período</th>
                        <th style="padding: 8px 10px; font-weight: 600; text-align: center; white-space: nowrap;">Estatus</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
        """
        descripcion_intro = f"De parte de <strong>{nombre_contratista}</strong>, le informamos que tras la revisión de su expediente correspondiente al ejercicio fiscal <strong>{anio}</strong>, se detectó que tiene <strong>{len(pendientes)}</strong> documento(s) pendiente(s) de entrega o con observaciones:"
    else:
        tabla_html = """
        <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 16px; border-radius: 6px; margin: 18px 0; text-align: center; font-weight: 500;">
            ✓ Actualmente no cuenta con documentos pendientes de entrega para los períodos transcurridos del ejercicio seleccionado.
        </div>
        """
        descripcion_intro = f"De parte de <strong>{nombre_contratista}</strong>, le informamos que hemos revisado su expediente para el ejercicio <strong>{anio}</strong>."

    cuerpo_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #334155; line-height: 1.6; max-width: 760px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
        <div style="background-color: #1a252f; padding: 18px 24px; border-bottom: 4px solid #00b8b9;">
            <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">CrossoverSuite</h2>
            <span style="color: #94a3b8; font-size: 13px;">Gestión de Documentos de Proveedores</span>
        </div>
        
        <div style="padding: 24px 28px;">
            <p style="font-size: 15px; margin-top: 0; margin-bottom: 14px;">
                Estimado/a <strong>{prov.nombre_razon_social}</strong>,
            </p>
            <p style="font-size: 14px; margin-bottom: 14px; color: #475569;">
                {descripcion_intro}
            </p>
            
            {tabla_html}
            
            <div style="background-color: #f0fdfa; border-left: 4px solid #00b8b9; padding: 14px 16px; border-radius: 4px; margin: 20px 0; font-size: 13.5px; color: #134e4a;">
                <strong>⚠️ Acción Requerida:</strong> Le solicitamos ingresar al portal del sistema para cargar o solventar los documentos requeridos a la brevedad a fin de mantener su expediente en cumplimiento normativo.
            </div>
            
            <div style="text-align: center; margin: 26px 0 20px 0;">
                <a href="{portal_url}" target="_blank" style="background-color: #00b8b9; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    Ingresar al Portal de Documentación
                </a>
            </div>
            
            <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; font-size: 13px; color: #64748b;">
                Atentamente,<br>
                <strong style="color: #1e293b; font-size: 14px;">{nombre_contratista}</strong><br>
                <span>Sistema CrossoverSuite</span>
            </div>
        </div>
        
        <div style="background-color: #f8fafc; padding: 12px 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 11.5px; color: #94a3b8;">
            Este es un mensaje automático emitido por la plataforma de gestión de contratistas y proveedores.
        </div>
    </div>
    """.strip()

    return JsonResponse({
        'success': True,
        'proveedor': prov.nombre_razon_social,
        'destinatario': destinatario,
        'cc': '',
        'asunto': asunto,
        'total_pendientes': len(pendientes),
        'cuerpo_html': cuerpo_html
    })


@login_required(login_url='/login/')
@require_POST
def enviar_correo_recordatorio_proveedor_ajax(request, id):
    import re
    from preferencias.permissions import user_has_hr_permission
    if not user_has_hr_permission(request, 'proveedores_contratistas', 'documentacion') and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No cuentas con permiso para enviar recordatorios.'}, status=403)
        
    empresa_actual = get_empresa_actual(request)
    prov = get_object_or_404(ProveedorRH, id=id, empresa=empresa_actual)
    
    destinatario_raw = request.POST.get('destinatario', '').strip()
    cc_raw = request.POST.get('cc', '').strip()
    asunto = request.POST.get('asunto', '').strip()
    cuerpo = request.POST.get('cuerpo', '').strip()
    
    if not destinatario_raw:
        return JsonResponse({'success': False, 'error': 'El correo destinatario es obligatorio.'})
    if not asunto:
        return JsonResponse({'success': False, 'error': 'El asunto es obligatorio.'})
    if not cuerpo:
        return JsonResponse({'success': False, 'error': 'El cuerpo del correo no puede estar vacío.'})
        
    to_emails = [e.strip() for e in re.split(r'[,;]+', destinatario_raw) if e.strip()]
    cc_emails = [e.strip() for e in re.split(r'[,;]+', cc_raw) if e.strip()] if cc_raw else []
    archivos = request.FILES.getlist('archivos')
    
    from preferencias.utils import enviar_correo_contratista
    try:
        exito = enviar_correo_contratista(
            contratista=prov.contratista,
            asunto=asunto,
            cuerpo=cuerpo,
            destinatarios=to_emails,
            cc=cc_emails,
            archivos_adjuntos=archivos,
            es_html=True
        )
        if exito:
            return JsonResponse({'success': True, 'message': f'Correo enviado exitosamente a {", ".join(to_emails)}.'})
        else:
            return JsonResponse({'success': False, 'error': 'No se pudo enviar el correo. Por favor verifique la configuración SMTP del contratista o del servidor.'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error al enviar correo recordatorio a proveedor {prov.id}: {e}")
        return JsonResponse({'success': False, 'error': f'Error al procesar el envío: {str(e)}'})




