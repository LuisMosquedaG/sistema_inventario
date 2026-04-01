from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.db.models import F
from decimal import Decimal
from .models import OrdenProduccion, DetalleOrdenProduccion
from core.models import Producto, DetalleReceta
from almacenes.models import Inventario, Almacen
from panel.models import Empresa
import json

# --- HELPER MULTI-TENANCY ---
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
def dashboard_produccion(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    ordenes_qs = OrdenProduccion.objects.filter(empresa=empresa_actual).select_related(
        'producto', 'pedido_origen', 'almacen', 'responsable', 'solicitante', 'producto__test_calidad'
    ).prefetch_related('detalles', 'resultados_test').order_by('-fecha_creacion')
    
    # AGREGAMOS LOS CÁLCULOS DE AVANCE A CADA ORDEN
    ordenes = []
    mapa_estados = {
        'borrador': 0,
        'en_proceso': 33,
        'testeo': 66,
        'terminado': 100,
        'cancelada': 0
    }

    for o in ordenes_qs:
        # 1. Avance por Estado
        o.porcentaje_estado = mapa_estados.get(o.estado, 0)
        
        # 2. Avance por Calidad (Tareas)
        o.porcentaje_calidad = 0
        if o.producto.test_calidad:
            total_tareas = o.producto.test_calidad.items.count()
            if total_tareas > 0:
                completadas = o.resultados_test.filter(completado=True).count()
                o.porcentaje_calidad = int((completadas / total_tareas) * 100)
        else:
            # Si no tiene test, lo marcamos como N/A o 100 si ya terminó
            o.porcentaje_calidad = 100 if o.estado == 'terminado' else 0
            
        ordenes.append(o)
    
    # PRODUCTOS QUE SE PUEDEN PRODUCIR
    productos_finales = Producto.objects.filter(empresa=empresa_actual, tipo_abastecimiento='produccion')
    almacenes = Almacen.objects.filter(empresa=empresa_actual)
    todos_productos = Producto.objects.filter(empresa=empresa_actual).values('id', 'nombre')
    
    contexto = {
        'ordenes': ordenes,
        'productos_finales': productos_finales,
        'almacenes': almacenes,
        'productos_json': list(todos_productos),
        'section': 'produccion'
    }
    return render(request, 'produccion/dashboard_produccion.html', contexto)

# ==========================================
# VISTAS PARA CATÁLOGO DE TESTS
# ==========================================

from .models import Test, ItemTest

@login_required(login_url='/login/')
def lista_tests(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    tests = Test.objects.filter(empresa=empresa_actual).prefetch_related('items')
    
    contexto = {
        'tests': tests,
        'section': 'produccion_tests'
    }
    return render(request, 'produccion/dashboard_tests.html', contexto)

@login_required
def api_obtener_test_orden(request, orden_id):
    """Jala las tareas del test y los resultados que ya se hayan guardado"""
    empresa_actual = get_empresa_actual(request)
    orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
    producto = orden.producto
    
    if not producto.test_calidad:
        return JsonResponse({'has_test': False})
    
    test = producto.test_calidad
    
    # Jalar resultados ya guardados para esta orden
    from .models import ResultadoTestOP
    resultados_dict = {r.item_test_id: {
        'completado': r.completado,
        'usuario': r.usuario_verifico.username.split('@')[0] if r.usuario_verifico else '?',
        'fecha': r.fecha_chequeo.strftime('%d/%m %H:%M') if r.fecha_chequeo else ''
    } for r in ResultadoTestOP.objects.filter(orden_produccion=orden)}

    tareas = []
    for item in test.items.all():
        res = resultados_dict.get(item.id, {'completado': False, 'usuario': '', 'fecha': ''})
        tareas.append({
            'id': item.id,
            'tarea': item.tarea,
            'completado': res['completado'],
            'usuario': res['usuario'],
            'fecha': res['fecha']
        })
        
    return JsonResponse({
        'has_test': True,
        'test_nombre': test.nombre,
        'tareas': tareas
    })

@login_required
@transaction.atomic
def guardar_avance_test_ajax(request, orden_id):
    """Guarda los checks sin finalizar la orden"""
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
            data = json.loads(request.body)
            checks_enviados = [int(id) for id in data.get('checks', [])]

            from .models import ResultadoTestOP, ItemTest
            
            # 1. Marcar como completados los que vienen en la lista
            for item_id in checks_enviados:
                ResultadoTestOP.objects.update_or_create(
                    orden_produccion=orden,
                    item_test_id=item_id,
                    defaults={
                        'completado': True,
                        'fecha_chequeo': timezone.now(),
                        'usuario_verifico': request.user
                    }
                )
            
            # 2. Desmarcar los que NO vienen (por si alguien quita un check)
            test_id = orden.producto.test_calidad_id
            todas_tareas_ids = ItemTest.objects.filter(test_id=test_id).values_list('id', flat=True)
            ids_a_desmarcar = [id for id in todas_tareas_ids if id not in checks_enviados]
            
            ResultadoTestOP.objects.filter(orden_produccion=orden, item_test_id__in=ids_a_desmarcar).delete()

            return JsonResponse({'success': True, 'message': 'Avance guardado mi chingon.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def finalizar_con_test_ajax(request, orden_id):
    """Guarda checks y finaliza orden vía AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        empresa_actual = get_empresa_actual(request)
        orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
        
        data = json.loads(request.body)
        checks = data.get('checks', [])

        # 1. Calidad
        from .models import ResultadoTestOP
        for item_id in checks:
            ResultadoTestOP.objects.update_or_create(
                orden_produccion=orden,
                item_test_id=item_id,
                defaults={'completado': True, 'fecha_chequeo': timezone.now(), 'usuario_verifico': request.user}
            )

        # 2. Finalizar
        res = finalizar_produccion_logica(request, orden)
        return JsonResponse({'success': res.get('success', False), 'message': res.get('message', ''), 'error': res.get('error', '')})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@transaction.atomic
def crear_test_ajax(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            data = json.loads(request.body)
            
            nombre = data.get('nombre')
            descripcion = data.get('descripcion', '')
            tareas = data.get('tareas', [])
            
            if not nombre:
                return JsonResponse({'success': False, 'error': 'El nombre del test es obligatorio.'})
            
            # 1. Crear Cabecera
            nuevo_test = Test.objects.create(
                empresa=empresa_actual,
                nombre=nombre,
                descripcion=descripcion
            )
            
            # 2. Crear Tareas
            for i, t in enumerate(tareas):
                if t.strip():
                    ItemTest.objects.create(
                        test=nuevo_test,
                        tarea=t.strip(),
                        orden=i
                    )
            
            return JsonResponse({'success': True, 'message': 'Test guardado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_detalle_test(request, test_id):
    """Devuelve los datos de un test y sus tareas para edición"""
    try:
        empresa_actual = get_empresa_actual(request)
        test = get_object_or_404(Test, id=test_id, empresa=empresa_actual)
        
        tareas = list(test.items.all().values('tarea', 'orden'))
        
        return JsonResponse({
            'success': True,
            'id': test.id,
            'nombre': test.nombre,
            'descripcion': test.descripcion,
            'tareas': tareas
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@transaction.atomic
def actualizar_test_ajax(request, test_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            test = get_object_or_404(Test, id=test_id, empresa=empresa_actual)
            
            data = json.loads(request.body)
            test.nombre = data.get('nombre')
            test.descripcion = data.get('descripcion', '')
            test.save()
            
            # Re-crear tareas (borramos las anteriores y ponemos las nuevas)
            test.items.all().delete()
            for i, t in enumerate(data.get('tareas', [])):
                if t.strip():
                    ItemTest.objects.create(test=test, tarea=t.strip(), orden=i)
            
            return JsonResponse({'success': True, 'message': 'Test actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def eliminar_test_ajax(request, test_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            test = get_object_or_404(Test, id=test_id, empresa=empresa_actual)
            
            # Verificamos si algún producto lo está usando antes de borrar
            from core.models import Producto
            if Producto.objects.filter(test_calidad=test).exists():
                return JsonResponse({'success': False, 'error': 'No se puede eliminar porque hay productos que usan este test.'})
            
            test.delete()
            return JsonResponse({'success': True, 'message': 'Test eliminado.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def crear_orden_produccion(request):
    """Crea una orden de producción manual y copia la receta base"""
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            producto_id = request.POST.get('producto')
            cantidad = int(request.POST.get('cantidad', 1))
            almacen_id = request.POST.get('almacen')
            
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
            almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)
            
            # 1. Crear Cabecera
            op = OrdenProduccion.objects.create(
                empresa=empresa_actual,
                producto=producto,
                cantidad=cantidad,
                almacen=almacen,
                solicitante=request.user,
                estado='borrador'
            )
            
            # 2. Copiar Receta Base
            receta_base = DetalleReceta.objects.filter(producto_padre=producto)
            for item in receta_base:
                DetalleOrdenProduccion.objects.create(
                    orden_produccion=op,
                    producto=item.componente,
                    cantidad=item.cantidad * cantidad
                )
                
            messages.success(request, f'Orden {op.folio} creada en Borrador.')
            return redirect('dashboard_produccion')
        except Exception as e:
            messages.error(request, f'Error al crear: {str(e)}')
            return redirect('dashboard_produccion')
    return redirect('dashboard_produccion')

@login_required
def api_detalle_orden(request, orden_id):
    """Retorna datos de la orden y sus componentes para el modal"""
    empresa_actual = get_empresa_actual(request)
    orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
    
    detalles = []
    for d in orden.detalles.all():
        detalles.append({
            'id': d.id,
            'producto_id': d.producto.id,
            'producto_nombre': d.producto.nombre,
            'cantidad': d.cantidad
        })
        
    data = {
        'id': orden.id,
        'folio': orden.folio,
        'producto_nombre': orden.producto.nombre,
        'cantidad_producir': orden.cantidad,
        'pedido_id': orden.pedido_origen.id if orden.pedido_origen else 'Manual',
        'solicitante': orden.solicitante.username.split('@')[0] if orden.solicitante else 'Sistema',
        'estado': orden.estado,
        'notas': orden.notas,
        'detalles': detalles
    }
    return JsonResponse(data)

@login_required
@transaction.atomic
def actualizar_orden_produccion(request, orden_id):
    """Guarda los cambios realizados en el modal de edición"""
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
            
            if orden.estado != 'borrador':
                return JsonResponse({'success': False, 'error': 'Solo se pueden editar órdenes en Borrador.'})

            # 1. Actualizar Notas
            data = json.loads(request.body)
            orden.notas = data.get('notas', '')
            orden.save()

            # 2. Actualizar Componentes
            # Borramos los actuales y recreamos según lo editado
            orden.detalles.all().delete()
            
            for item in data.get('componentes', []):
                DetalleOrdenProduccion.objects.create(
                    orden_produccion=orden,
                    producto_id=item['producto_id'],
                    cantidad=item['cantidad']
                )

            return JsonResponse({'success': True, 'message': 'Orden actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def avanzar_estado_produccion(request, orden_id):
    """Mueve la orden al siguiente paso de la cadena con validaciones"""
    empresa_actual = get_empresa_actual(request)
    orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
    
    nuevo_estado = request.GET.get('estado')
    
    # 1. BORRADOR -> EN PROCESO (CON RESERVA DE STOCK)
    if nuevo_estado == 'en_proceso' and orden.estado == 'borrador':
        try:
            detalles = orden.detalles.all()
            if not detalles.exists():
                raise Exception("La orden no tiene componentes asignados.")

            # Bloqueamos y validamos stock
            with transaction.atomic():
                for d in detalles:
                    # Usamos filter().first() en lugar de .get() para evitar el error si no existe el registro
                    inv = Inventario.objects.select_for_update().filter(producto=d.producto, almacen=orden.almacen).first()
                    
                    # Si no existe el registro, el stock disponible es 0
                    disponible = (inv.cantidad - inv.reservado) if inv else 0
                    
                    if disponible < d.cantidad:
                        raise Exception(f"Stock insuficiente de {d.producto.nombre} en {orden.almacen.nombre}. (Disponible: {disponible}, Requerido: {d.cantidad})")
                    
                    # Si todo bien, actualizamos la reserva (asegurando que exista el registro)
                    if not inv:
                        # Este caso técnicamente no debería pasar por el check de arriba, pero por seguridad:
                        inv = Inventario.objects.create(producto=d.producto, almacen=orden.almacen, cantidad=0, empresa=empresa_actual)
                    
                    inv.reservado = F('reservado') + d.cantidad
                    inv.save()

            # Si todo bien, iniciamos
            orden.estado = 'en_proceso'
            orden.fecha_inicio = timezone.now()
            orden.responsable = request.user
            orden.save()
            messages.success(request, f'Orden {orden.folio} iniciada. Los materiales han sido reservados en bodega.')
        except Exception as e:
            messages.error(request, str(e))
    
    # 2. EN PROCESO -> TESTEO
    elif nuevo_estado == 'testeo' and orden.estado == 'en_proceso':
        orden.estado = 'testeo'
        orden.save()
        messages.info(request, f'Orden {orden.folio} enviada a Testeo / Calidad.')
        
    # 3. TESTEO -> TERMINADO
    elif nuevo_estado == 'terminado' and orden.estado == 'testeo':
        # --- CANDADO DE SEGURIDAD ---
        if orden.producto.test_calidad:
            return JsonResponse({'success': False, 'error': 'Esta orden requiere validación de checklist.'}, status=400)
        else:
            res = finalizar_produccion_logica(request, orden)
            if res.get('success'):
                messages.success(request, res['message'])
            else:
                messages.error(request, res.get('error'))

    return redirect('dashboard_produccion')

def finalizar_produccion_logica(request, orden):
    """Función interna para cerrar la orden, descontar físico y reserva, y sumar producto terminado"""
    try:
        producto = orden.producto
        almacen = orden.almacen
        cantidad_producir = orden.cantidad

        detalles_orden = orden.detalles.all()

        # 1. Ejecutar Movimientos de Salida (Limpiar Reserva y Quitar Físico)
        for det in detalles_orden:
            # Usamos el método centralizado para que se registre en el Kardex
            Inventario.registrar_salida(
                almacen=almacen,
                producto=det.producto,
                cantidad_salida=det.cantidad,
                referencia=f"OP-{orden.id:04d} (Consumo)"
            )
            # Limpiamos la reserva manualmente ya que registrar_salida no toca 'reservado'
            Inventario.objects.filter(producto=det.producto, almacen=almacen).update(
                reservado=F('reservado') - det.cantidad
            )

        # 2. Sumar Producto Terminado
        Inventario.registrar_ingreso(
            almacen=almacen,
            producto=producto,
            cantidad_ingreso=cantidad_producir,
            costo_unitario=producto.precio_costo, # O el costo calculado de la receta
            referencia=f"OP-{orden.id:04d} (Ensamble)"
        )

        # 5. Finalizar Orden
        orden.estado = 'terminado'
        orden.fecha_terminado = timezone.now()
        orden.save()

        # 6. Sincronizar Pedido
        if orden.pedido_origen:
            from pedidos.models import DetallePedido
            detalles_pedido = DetallePedido.objects.filter(pedido=orden.pedido_origen, producto=producto)
            for dp in detalles_pedido:
                if dp.estado_linea != 'completo':
                    dp.estado_linea = 'pendiente'
                    dp.save()

        return {'success': True, 'message': f'Orden {orden.folio} terminada exitosamente.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@login_required
def cancelar_produccion(request, orden_id):
    empresa_actual = get_empresa_actual(request)
    orden = get_object_or_404(OrdenProduccion, id=orden_id, empresa=empresa_actual)
    if orden.estado != 'terminado':
        orden.estado = 'cancelada'
        orden.save()
        messages.success(request, f'Orden {orden.folio} cancelada.')
    return redirect('dashboard_produccion')
