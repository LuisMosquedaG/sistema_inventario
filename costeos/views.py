from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q
from panel.models import Empresa
from core.models import Producto
from preferencias.models import Moneda, Sucursal
from .models import (
    Costeo, ManufacturaMateriaPrima, ManufacturaManoObra, ManufacturaGastoIndirecto,
    ComercioAdquisicion, ServicioPersonal, ServicioMaterial
)
import json

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

@login_required(login_url='/login/')
def dashboard_costeos(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    q = request.GET.get('q', '')
    sucursal_id = request.GET.get('sucursal', '')

    costeos_qs = Costeo.objects.filter(empresa=empresa_actual).select_related('sucursal', 'vendedor').prefetch_related(
        'materias_primas', 'mano_obra', 'gastos_indirectos',
        'costos_adquisicion', 'personal_servicio', 'materiales_servicio',
        'materias_primas__moneda', 'mano_obra__moneda', 'gastos_indirectos__moneda',
        'costos_adquisicion__moneda', 'personal_servicio__moneda', 'materiales_servicio__moneda'
    ).order_by('-fecha_creacion')

    if q:
        costeos_qs = costeos_qs.filter(
            Q(nombre_identificador__icontains=q) |
            Q(vendedor__username__icontains=q)
        )
    if sucursal_id:
        costeos_qs = costeos_qs.filter(sucursal_id=sucursal_id)

    # PAGINACIÓN
    paginator = Paginator(costeos_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    contexto = {
        'page_obj': page_obj,
        'productos': Producto.objects.filter(empresa=empresa_actual),
        'monedas': Moneda.objects.filter(empresa=empresa_actual),
        'sucursales': Sucursal.objects.filter(empresa=empresa_actual),
        'filtros': {
            'q': q,
            'sucursal': sucursal_id
        },
        'section': 'costeos'
    }
    return render(request, 'costeos/dashboard_costeos.html', contexto)

@login_required
@transaction.atomic
def api_guardar_costeo(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        data = json.loads(request.body)
        empresa_actual = get_empresa_actual(request)
        costeo_id = data.get('id')
        
        # Identificador único (puede ser cualquiera de los nombres)
        nombre = data.get('nombre_manuf') or data.get('nombre_comer') or data.get('nombre_serv') or "Sin nombre"

        if costeo_id:
            costeo = Costeo.objects.get(id=costeo_id, empresa=empresa_actual)
            if costeo.estado != 'BORRADOR':
                return JsonResponse({'success': False, 'error': 'Solo se pueden editar costeos en estado BORRADOR'})
            
            costeo.nombre_identificador = nombre
            costeo.es_manufactura = data.get('es_manufactura', False)
            costeo.es_comercio = data.get('es_comercio', False)
            costeo.es_servicio = data.get('es_servicio', False)
            costeo.margen_porcentaje = data.get('margen_porcentaje', 0)
            costeo.precio_venta_fijo = data.get('precio_venta_fijo', 0)
            costeo.utiliza_porcentaje = data.get('utiliza_porcentaje', True)
            costeo.iva_porcentaje = data.get('iva_porcentaje', 16)
            costeo.save()
            
            # Limpiar items previos para reemplazarlos
            costeo.materias_primas.all().delete()
            costeo.mano_obra.all().delete()
            costeo.gastos_indirectos.all().delete()
            costeo.costos_adquisicion.all().delete()
            costeo.personal_servicio.all().delete()
            costeo.materiales_servicio.all().delete()
        else:
            # 1. Crear Cabecera
            costeo = Costeo.objects.create(
                empresa=empresa_actual,
                sucursal_id=request.session.get('sucursal_id'),
                vendedor=request.user,
                nombre_identificador=nombre,
                es_manufactura=data.get('es_manufactura', False),
                es_comercio=data.get('es_comercio', False),
                es_servicio=data.get('es_servicio', False),
                margen_porcentaje=data.get('margen_porcentaje', 0),
                precio_venta_fijo=data.get('precio_venta_fijo', 0),
                utiliza_porcentaje=data.get('utiliza_porcentaje', True),
                iva_porcentaje=data.get('iva_porcentaje', 16)
            )

        # 2. Guardar Items de Manufactura
        if costeo.es_manufactura:
            for item in data.get('manufactura_mp', []):
                ManufacturaMateriaPrima.objects.create(
                    costeo=costeo, nombre=item['nombre'], cantidad=item['cantidad'],
                    costo_unitario=item['costo'], moneda_id=item['moneda_id']
                )
            for item in data.get('manufactura_mo', []):
                ManufacturaManoObra.objects.create(
                    costeo=costeo, concepto=item['concepto'], horas=item['horas'],
                    costo_hora=item['costo_hora'], moneda_id=item['moneda_id']
                )
            for item in data.get('manufactura_gi', []):
                ManufacturaGastoIndirecto.objects.create(
                    costeo=costeo, concepto=item['concepto'], monto=item['monto'],
                    moneda_id=item['moneda_id']
                )

        # 3. Guardar Items de Comercio
        if costeo.es_comercio:
            for item in data.get('comercio_items', []):
                ComercioAdquisicion.objects.create(
                    costeo=costeo, concepto=item['concepto'], monto=item['monto'],
                    moneda_id=item['moneda_id']
                )

        # 4. Guardar Items de Servicios
        if costeo.es_servicio:
            for item in data.get('servicio_personal', []):
                ServicioPersonal.objects.create(
                    costeo=costeo, rol=item['rol'], horas=item['horas'],
                    tarifa_hora=item['tarifa_hora'], moneda_id=item['moneda_id']
                )
            for item in data.get('servicio_materiales', []):
                ServicioMaterial.objects.create(
                    costeo=costeo, concepto=item['concepto'], cantidad=item['cantidad'],
                    costo=item['costo'], moneda_id=item['moneda_id']
                )

        return JsonResponse({'success': True, 'message': 'Costeo guardado exitosamente.', 'id': costeo.id})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_detalle_costeo(request, costeo_id):
    try:
        empresa_actual = get_empresa_actual(request)
        c = Costeo.objects.get(id=costeo_id, empresa=empresa_actual)
        
        data = {
            'id': c.id,
            'folio': c.folio,
            'nombre': c.nombre_identificador,
            'estado': c.estado,
            'fecha': c.fecha_creacion.strftime('%d/%m/%Y'),
            'sucursal': c.sucursal.nombre if c.sucursal else "Principal",
            'vendedor': c.vendedor.username if c.vendedor else "--",
            'es_manufactura': c.es_manufactura,
            'es_comercio': c.es_comercio,
            'es_servicio': c.es_servicio,
            'utiliza_porcentaje': c.utiliza_porcentaje,
            'margen_porcentaje': float(c.margen_porcentaje),
            'precio_venta_fijo': float(c.precio_venta_fijo),
            'costo_total': float(c.get_costo_total),
            'venta_total': float(c.get_venta_total),
            'utilidad': float(c.get_utilidad),
            'items': {
                'manufactura_mp': list(c.materias_primas.values('nombre', 'cantidad', 'costo_unitario', 'moneda_id')),
                'manufactura_mo': list(c.mano_obra.values('concepto', 'horas', 'costo_hora', 'moneda_id')),
                'manufactura_gi': list(c.gastos_indirectos.values('concepto', 'monto', 'moneda_id')),
                'comercio_items': list(c.costos_adquisicion.values('concepto', 'monto', 'moneda_id')),
                'servicio_personal': list(c.personal_servicio.values('rol', 'horas', 'tarifa_hora', 'moneda_id')),
                'servicio_materiales': list(c.materiales_servicio.values('concepto', 'cantidad', 'costo', 'moneda_id')),
            }
        }
        return JsonResponse({'success': True, 'data': data})
    except Costeo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Costeo no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_aprobar_costeo(request, costeo_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        empresa_actual = get_empresa_actual(request)
        costeo = Costeo.objects.get(id=costeo_id, empresa=empresa_actual)
        costeo.estado = 'APROBADO'
        costeo.save()
        return JsonResponse({'success': True, 'message': 'Costeo aprobado exitosamente.'})
    except Costeo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Costeo no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_duplicar_costeo(request, costeo_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        with transaction.atomic():
            empresa_actual = get_empresa_actual(request)
            original = Costeo.objects.get(id=costeo_id, empresa=empresa_actual)
            
            # Duplicar cabecera
            nuevo = Costeo.objects.create(
                empresa=original.empresa,
                sucursal=original.sucursal,
                vendedor=request.user,
                nombre_identificador=original.nombre_identificador,
                es_manufactura=original.es_manufactura,
                es_comercio=original.es_comercio,
                es_servicio=original.es_servicio,
                margen_porcentaje=original.margen_porcentaje,
                precio_venta_fijo=original.precio_venta_fijo,
                utiliza_porcentaje=original.utiliza_porcentaje,
                iva_porcentaje=original.iva_porcentaje,
                estado='BORRADOR',
                duplicado_de=original
            )
            
            # Duplicar items
            for item in original.materias_primas.all():
                ManufacturaMateriaPrima.objects.create(costeo=nuevo, nombre=item.nombre, cantidad=item.cantidad, costo_unitario=item.costo_unitario, moneda=item.moneda)
            for item in original.mano_obra.all():
                ManufacturaManoObra.objects.create(costeo=nuevo, concepto=item.concepto, horas=item.horas, costo_hora=item.costo_hora, moneda=item.moneda)
            for item in original.gastos_indirectos.all():
                ManufacturaGastoIndirecto.objects.create(costeo=nuevo, concepto=item.concepto, monto=item.monto, moneda=item.moneda)
            for item in original.costos_adquisicion.all():
                ComercioAdquisicion.objects.create(costeo=nuevo, concepto=item.concepto, monto=item.monto, moneda=item.moneda)
            for item in original.personal_servicio.all():
                ServicioPersonal.objects.create(costeo=nuevo, rol=item.rol, horas=item.horas, tarifa_hora=item.tarifa_hora, moneda=item.moneda)
            for item in original.materiales_servicio.all():
                ServicioMaterial.objects.create(costeo=nuevo, concepto=item.concepto, cantidad=item.cantidad, costo=item.costo, moneda=item.moneda)
                
            return JsonResponse({'success': True, 'message': 'Costeo duplicado exitosamente.'})
            
    except Costeo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Costeo no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_eliminar_costeo(request, costeo_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        empresa_actual = get_empresa_actual(request)
        costeo = Costeo.objects.get(id=costeo_id, empresa=empresa_actual)
        costeo.delete()
        return JsonResponse({'success': True, 'message': 'Costeo eliminado exitosamente.'})
    except Costeo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Costeo no encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
