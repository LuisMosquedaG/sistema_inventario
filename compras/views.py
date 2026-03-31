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

@login_required(login_url='/login/')
def dashboard_compras(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    compras_list = OrdenCompra.objects.filter(empresa=empresa_actual).order_by('-fecha', '-id')
    
    paginator = Paginator(compras_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    productos = Producto.objects.filter(empresa=empresa_actual)
    almacenes = Almacen.objects.filter(empresa=empresa_actual)
    proveedores = Proveedor.objects.filter(empresa=empresa_actual, estado='activo')
    monedas = Moneda.objects.filter(empresa=empresa_actual) # <--- NUEVO

    context = {
        'page_obj': page_obj,
        'productos': productos,
        'almacenes': almacenes,
        'proveedores': proveedores,
        'monedas': monedas, # <--- PASAR AL HTML
        'section': 'compras',
    }
    return render(request, 'dashboard_compras.html', context)

@login_required
def crear_compra(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                 return JsonResponse({'success': False, 'error': 'No se pudo detectar tu empresa.'})

            # Pasar datos adicionales al servicio
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
            # Al aprobar, podríamos forzar a que el tipo de cambio sea el actual si no se puso,
            # pero por ahora respetamos lo que el usuario escribió o el default 1.0
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
            'proveedor': orden.proveedor.id,
            'almacen': orden.almacen_destino.id if orden.almacen_destino else '',
            'moneda': orden.moneda.id if orden.moneda else '', # <--- NUEVO
            'tipo_cambio': str(orden.tipo_cambio), # <--- NUEVO
            'fecha': orden.fecha.strftime('%Y-%m-%d'),
            'notas': orden.notas,
            'estado': orden.estado,
            'detalles': [
                {
                    'producto_id': d.producto.id,
                    'producto_nombre': d.producto.nombre,
                    'cantidad': d.cantidad,
                    'precio': float(d.precio_costo),
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
            orden.almacen_destino_id = request.POST.get('almacen')
            orden.moneda_id = request.POST.get('moneda') # <--- NUEVO
            orden.tipo_cambio = request.POST.get('tipo_cambio', '1.0000') # <--- NUEVO
            
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