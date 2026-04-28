from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db import transaction
from proveedores.models import Proveedor
from .models import OrdenCompra, DetalleCompra
from core.models import Producto
from almacenes.models import Almacen
from preferencias.models import Moneda
from django.utils import timezone
from .services import crear_orden_compra_servicio
from panel.models import Empresa 

# --- 1. FUNCIÓN AYUDANTE (Estándar en todo el proyecto) ---
def get_empresa_actual(request):
    """Detecta la empresa basándose en el username del usuario logueado."""
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

from django.db.models import Q

@login_required(login_url='/login/')
def dashboard_compras(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    folio_compra = request.GET.get('folio_compra', '')
    folio_solicitud = request.GET.get('folio_solicitud', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')

    compras_list = OrdenCompra.objects.filter(empresa=empresa_actual).order_by('-fecha', '-id')

    if q:
        compras_list = compras_list.filter(
            Q(id__icontains=q) |
            Q(solicitud_origen__id__icontains=q) |
            Q(proveedor__razon_social__icontains=q) |
            Q(usuario__username__icontains=q) |
            Q(notas__icontains=q) |
            Q(estado__icontains=q)
        )
    if folio_compra:
        # Limpiar el folio por si el usuario escribe "OC-0001" o "OC0001"
        clean_folio = folio_compra.upper().replace('OC-', '').replace('OC', '').strip()
        compras_list = compras_list.filter(id__icontains=clean_folio)
    if folio_solicitud:
        # Limpiar el folio por si el usuario escribe "SOL-0001" o "SOL0001"
        clean_solicitud = folio_solicitud.upper().replace('SOL-', '').replace('SOL', '').strip()
        compras_list = compras_list.filter(solicitud_origen__id__icontains=clean_solicitud)
    if proveedor_id and proveedor_id != 'all':
        compras_list = compras_list.filter(proveedor_id=proveedor_id)
    if fecha:
        try:
            compras_list = compras_list.filter(fecha__date=fecha)
        except:
            pass
    if estado:
        compras_list = compras_list.filter(estado=estado)

    # Para el buscador visual de proveedor
    proveedor_nombre_display = ""
    if proveedor_id and proveedor_id != 'all':
        try:
            p_obj = Proveedor.objects.get(id=proveedor_id, empresa=empresa_actual)
            proveedor_nombre_display = p_obj.razon_social
        except:
            pass

    filtros = {
        'q': q,
        'folio_compra': folio_compra,
        'folio_solicitud': folio_solicitud,
        'proveedor_id': proveedor_id,
        'proveedor_nombre': proveedor_nombre_display,
        'fecha': fecha,
        'estado': estado
    }
    # --- FIN LÓGICA DE FILTRADO ---
    
    paginator = Paginator(compras_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    productos = Producto.objects.filter(empresa=empresa_actual)
    almacenes = Almacen.objects.filter(empresa=empresa_actual)
    proveedores_activos = Proveedor.objects.filter(empresa=empresa_actual, estado='activo')
    todos_los_proveedores = Proveedor.objects.filter(empresa=empresa_actual)
    monedas = Moneda.objects.filter(empresa=empresa_actual)

    context = {
        'page_obj': page_obj,
        'productos': productos,
        'almacenes': almacenes,
        'proveedores': proveedores_activos,
        'todos_los_proveedores': todos_los_proveedores,
        'monedas': monedas,
        'section': 'compras',
        'filtros': filtros
    }
    return render(request, 'dashboard_compras.html', context)

@login_required
def crear_compra(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                 return JsonResponse({'success': False, 'error': 'No se pudo detectar tu empresa.'})

            orden = crear_orden_compra_servicio(
                usuario=request.user,
                data_post=request.POST,
                empresa_actual=empresa_actual
            )

            return JsonResponse({'success': True, 'message': 'Orden creada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def cambiar_estado_compra(request, compra_id):
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        empresa_actual = get_empresa_actual(request)
        compra = get_object_or_404(OrdenCompra, id=compra_id, empresa=empresa_actual)
        
        if nuevo_estado in ['borrador', 'aprobada', 'recibida', 'cancelada', 'parcial']:
            compra.estado = nuevo_estado
            compra.save()
            return JsonResponse({'success': True, 'message': f'Estado cambiado a {nuevo_estado}'})
        else:
            return JsonResponse({'success': False, 'error': 'Estado inválido'})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def obtener_compra_json(request, compra_id):
    try:
        empresa_actual = get_empresa_actual(request)
        orden = get_object_or_404(OrdenCompra, id=compra_id, empresa=empresa_actual)
        detalles = DetalleCompra.objects.filter(orden_compra=orden)
        
        data = {
            'id': orden.id,
            'folio': f"OC-{orden.id:04d}",
            'proveedor_id': orden.proveedor.id,
            'proveedor_nombre': orden.proveedor.razon_social,
            'sucursal_id': orden.sucursal.id if orden.sucursal else '',
            'sucursal_nombre': orden.sucursal.nombre if orden.sucursal else 'Matriz / Principal',
            'almacen_id': orden.almacen_destino.id if orden.almacen_destino else '',
            'almacen_nombre': orden.almacen_destino.nombre if orden.almacen_destino else 'No asignado',
            'moneda_id': orden.moneda.id if orden.moneda else '',
            'moneda_nombre': orden.moneda.siglas if orden.moneda else 'MXN',
            'tipo_cambio': str(orden.tipo_cambio),
            'fecha': orden.fecha.strftime('%Y-%m-%d'),
            'fecha_formateada': orden.fecha.strftime('%d/%m/%Y'),
            'notas': orden.notas or '',
            'estado': orden.estado,
            'detalles': [
                {
                    'producto_id': d.producto.id,
                    'producto_nombre': d.producto.nombre,
                    'cantidad': d.cantidad,
                    'precio': float(d.precio_costo),
                    'total': float(d.subtotal),
                } for d in detalles
            ]
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@login_required
@transaction.atomic
def actualizar_compra(request, compra_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            orden = get_object_or_404(OrdenCompra, id=compra_id, empresa=empresa_actual)

            # 1. Actualizar Cabecera
            orden.proveedor_id = request.POST.get('proveedor')
            orden.sucursal_id = request.POST.get('sucursal')
            orden.almacen_destino_id = request.POST.get('almacen')
            orden.moneda_id = request.POST.get('moneda')
            orden.tipo_cambio = request.POST.get('tipo_cambio', '1.0000')
            
            nueva_fecha_str = request.POST.get('fecha')
            if nueva_fecha_str:
                from datetime import datetime
                try:
                    nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()
                    orden.fecha = nueva_fecha
                except ValueError: pass
            
            orden.notas = request.POST.get('notas')
            orden.save()

            # 2. Manejo de Ítems
            orden.detalles.all().delete() 
            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            precios = request.POST.getlist('precio_unitario[]')

            for i in range(len(productos_ids)):
                prod_id = productos_ids[i]
                if not prod_id: continue
                cant = int(cantidades[i])
                precio = float(precios[i])
                if prod_id and cant > 0:
                    DetalleCompra.objects.create(
                        orden_compra=orden,
                        producto_id=prod_id,
                        cantidad=cant,
                        precio_costo=precio
                    )
            return JsonResponse({'success': True, 'message': 'Orden actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def consolidar_compras_ajax(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'message': 'Empresa no detectada.'})

            # 1. Obtener órdenes en borrador
            ordenes_borrador = OrdenCompra.objects.filter(
                empresa=empresa_actual, 
                estado='borrador'
            ).select_related('proveedor', 'sucursal', 'moneda', 'almacen_destino')

            if not ordenes_borrador.exists():
                return JsonResponse({'success': False, 'message': 'No hay órdenes en borrador para consolidar.'})

            # 2. Agrupar por (Proveedor, Sucursal, Moneda, Almacén)
            grupos = {}
            for oc in ordenes_borrador:
                llave = (
                    oc.proveedor_id, 
                    oc.sucursal_id, 
                    oc.moneda_id, 
                    oc.almacen_destino_id
                )
                if llave not in grupos:
                    grupos[llave] = []
                grupos[llave].append(oc)

            ordenes_creadas_count = 0
            
            # 3. Procesar cada grupo
            for llave, lista_ocs in grupos.items():
                if len(lista_ocs) < 2:
                    continue 

                # Datos base de la nueva OC
                oc_base = lista_ocs[0]
                
                # Folios a consolidar
                folios = [f"OC-{oc.id:04d}" for oc in lista_ocs]
                leyenda_notas = f"Orden de compra creada de los folios {', '.join(folios)}"

                # Crear la nueva OC
                nueva_oc = OrdenCompra.objects.create(
                    proveedor_id=llave[0],
                    sucursal_id=llave[1],
                    moneda_id=llave[2],
                    almacen_destino_id=llave[3],
                    tipo_cambio=oc_base.tipo_cambio,
                    fecha=timezone.now(),
                    estado='borrador',
                    empresa=empresa_actual,
                    usuario=request.user,
                    notas=leyenda_notas
                )

                # Mover detalles
                for oc_original in lista_ocs:
                    for det in oc_original.detalles.all():
                        DetalleCompra.objects.create(
                            orden_compra=nueva_oc,
                            producto=det.producto,
                            cantidad=det.cantidad,
                            precio_costo=det.precio_costo,
                            detalle_pedido_origen=det.detalle_pedido_origen
                        )
                    
                    # Cancelar la original
                    oc_original.estado = 'cancelada'
                    oc_original.notas = f"{oc_original.notas or ''} [CONSOLIDADA EN OC-{nueva_oc.id:04d}]".strip()
                    oc_original.save()

                ordenes_creadas_count += 1

            if ordenes_creadas_count > 0:
                return JsonResponse({'success': True, 'message': f'Consolidación exitosa. Se generaron {ordenes_creadas_count} nuevas órdenes unificadas.'})
            else:
                return JsonResponse({'success': False, 'message': 'No se encontraron órdenes que pudieran ser agrupadas (mismo proveedor, sucursal, moneda y almacén).'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido.'})
