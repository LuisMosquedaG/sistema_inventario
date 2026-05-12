from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import Pedido, DetallePedido
from django.contrib import messages
from clientes.models import Cliente, ContactoCliente
from core.models import Producto, DetalleReceta
from cotizaciones.models import Cotizacion
from almacenes.models import Inventario, Almacen
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
from django.utils import timezone
import json
from django.db.models import F, Sum
from django.db import transaction
from collections import defaultdict
from solicitudcompras.models import SolicitudCompra, DetalleSolicitudCompra
from produccion.models import OrdenProduccion
from notificaciones.utils import crear_notificacion
from preferencias.permissions import require_sales_permission

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
@transaction.atomic
@require_sales_permission('pedidos', 'crear', json_response=True)
def crear_pedido_manual(request):
    """Crea un pedido directamente desde el dashboard de pedidos"""
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no detectada'})

    if request.method == 'POST':
        try:
            cliente_id = request.POST.get('cliente')
            contacto_id = request.POST.get('contacto')
            notas = request.POST.get('notas', '')

            if not cliente_id:
                return JsonResponse({'success': False, 'error': 'El cliente es obligatorio.'})

            cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
            contacto = None
            if contacto_id:
                contacto = get_object_or_404(ContactoCliente, id=contacto_id, cliente=cliente)

            # Asignar sucursal desde la sesión
            sucursal_obj = None
            sucursal_id = request.session.get('sucursal_id')
            if sucursal_id:
                from preferencias.models import Sucursal
                try:
                    sucursal_obj = Sucursal.objects.get(id=sucursal_id, empresa=empresa_actual)
                except Sucursal.DoesNotExist:
                    pass

            # 1. Crear Cabecera
            nuevo_pedido = Pedido.objects.create(
                cliente=cliente,
                contacto=contacto,
                vendedor=request.user,
                empresa=empresa_actual,
                sucursal=sucursal_obj,
                estado='borrador',
                notas=notas
            )

            # 2. Guardar Detalles
            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            precios = request.POST.getlist('precio_unitario[]')

            count = 0
            for prod_id, cant, prec in zip(productos_ids, cantidades, precios):
                if prod_id and prod_id != '':
                    producto_obj = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
                    DetallePedido.objects.create(
                        pedido=nuevo_pedido,
                        producto=producto_obj,
                        cantidad_solicitada=cant,
                        precio_unitario=prec,
                        estado_linea='pendiente'
                    )
                    count += 1
            
            if count == 0:
                # Si no hay productos, cancelamos la transacción (por el atomic)
                raise Exception("Debes agregar al menos un producto al pedido.")

            messages.success(request, f'Pedido #{nuevo_pedido.id} creado correctamente.')
            crear_notificacion(
                empresa=empresa_actual,
                actor=request.user,
                mensaje=f'creó el pedido manual #{nuevo_pedido.id:04d}',
                propietario=request.user
            )
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

from django.db.models import Q

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'ver')
def dashboard_pedidos(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    folio_pedido = request.GET.get('folio_pedido', '')
    folio_cotizacion = request.GET.get('folio_cotizacion', '')
    cliente_id = request.GET.get('cliente_id', '')
    contacto_id = request.GET.get('contacto_id', '')
    fecha = request.GET.get('fecha', '')
    estado = request.GET.get('estado', '')
    sucursal_id_filtro = request.GET.get('sucursal', '')

    lista_pedidos = Pedido.objects.filter(empresa=empresa_actual).select_related('cliente', 'vendedor', 'sucursal').order_by('-fecha_creacion')

    if q:
        lista_pedidos = lista_pedidos.filter(
            Q(id__icontains=q) |
            Q(cotizacion_origen_id__icontains=q) |
            Q(cliente__razon_social__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(cliente__apellidos__icontains=q) |
            Q(estado__icontains=q)
        )
    if folio_pedido:
        lista_pedidos = lista_pedidos.filter(id__icontains=folio_pedido)
    if folio_cotizacion:
        lista_pedidos = lista_pedidos.filter(cotizacion_origen_id__icontains=folio_cotizacion)
    if cliente_id and cliente_id != 'all':
        lista_pedidos = lista_pedidos.filter(cliente_id=cliente_id)
    if contacto_id and contacto_id != 'all':
        lista_pedidos = lista_pedidos.filter(contacto_id=contacto_id)
    if fecha:
        try:
            lista_pedidos = lista_pedidos.filter(fecha_creacion__date=fecha)
        except:
            pass
    if estado:
        lista_pedidos = lista_pedidos.filter(estado=estado)
    if sucursal_id_filtro:
        lista_pedidos = lista_pedidos.filter(sucursal_id=sucursal_id_filtro)

    # Para el buscador visual y cascada
    cliente_nombre_display = ""
    contactos_del_cliente = []
    contacto_nombre_display = ""

    if cliente_id and cliente_id != 'all':
        try:
            c_obj = Cliente.objects.get(id=cliente_id, empresa=empresa_actual)
            cliente_nombre_display = c_obj.razon_social if c_obj.razon_social else f"{c_obj.nombre} {c_obj.apellidos}"
            
            # Cargar contactos para la cascada
            contactos_del_cliente = ContactoCliente.objects.filter(cliente=c_obj)
            
            if contacto_id and contacto_id != 'all':
                cont_obj = contactos_del_cliente.get(id=contacto_id)
                contacto_nombre_display = cont_obj.nombre_completo
        except:
            pass

    filtros = {
        'q': q,
        'folio_pedido': folio_pedido,
        'folio_cotizacion': folio_cotizacion,
        'cliente_id': cliente_id,
        'cliente_nombre': cliente_nombre_display,
        'contacto_id': contacto_id,
        'contacto_nombre': contacto_nombre_display,
        'fecha': fecha,
        'estado': estado,
        'sucursal': sucursal_id_filtro
    }
    # --- FIN LÓGICA DE FILTRADO ---
    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    # --- DATOS PARA EL MODAL DE NUEVO PEDIDO ---
    clientes = Cliente.objects.filter(empresa=empresa_actual)
    productos = Producto.objects.filter(empresa=empresa_actual)

    # --- DATOS PARA EL MODAL DE PAGO ---
    from tesoreria.models import CajaBanco
    from preferencias.models import Moneda
    from categorias.models import ListaPrecioCosto
    
    cajas = CajaBanco.objects.filter(empresa=empresa_actual, activo=True)
    monedas = Moneda.objects.filter(empresa=empresa_actual)
    listas_precios = ListaPrecioCosto.objects.filter(empresa=empresa_actual, tipo='precio').order_by('nombre')

    contexto = {
        'pedidos': lista_pedidos,
        'clientes': clientes,
        'productos': productos,
        'listas_precios': listas_precios,
        'cajas': cajas,
        'monedas': monedas,
        'sucursales': sucursales,
        'contactos_filtro': contactos_del_cliente,
        'filtros': filtros,
        'hoy': timezone.now().date()
    }
    return render(request, 'dashboard_pedidos.html', contexto)

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'crear')
def crear_pedido_desde_cotizacion(request, cotizacion_id):
    """Convierte una Cotización Aprobada en un Pedido en estado Borrador"""
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        messages.error(request, "No tienes empresa asignada.")
        return redirect('dashboard_cotizaciones')

    try:
        # 1. Obtener cotización
        cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id, empresa=empresa_actual)
        
        if cotizacion.estado != 'aprobada':
            messages.error(request, 'Solo se pueden crear pedidos desde cotizaciones Aprobadas.')
            return redirect('dashboard_cotizaciones')

        # Asignar sucursal desde la sesión
        sucursal_obj = None
        sucursal_id = request.session.get('sucursal_id')
        if sucursal_id:
            from preferencias.models import Sucursal
            try:
                sucursal_obj = Sucursal.objects.get(id=sucursal_id, empresa=empresa_actual)
            except Sucursal.DoesNotExist:
                pass

        # 2. Crear Pedido (Cabecera)
        nuevo_pedido = Pedido.objects.create(
            cliente=cotizacion.cliente,
            contacto=cotizacion.contacto,
            vendedor=request.user,
            empresa=empresa_actual,
            sucursal=sucursal_obj,
            cotizacion_origen_id=cotizacion.id,
            estado='borrador' # Inicia en borrador para que el usuario revise antes de confirmar
        )

        # 3. Migrar Detalles
        for det_cot in cotizacion.detalles.all():
            DetallePedido.objects.create(
                pedido=nuevo_pedido,
                producto=det_cot.producto,
                cantidad_solicitada=det_cot.cantidad,
                precio_unitario=det_cot.precio_unitario,
                estado_linea='pendiente' # Inicialmente pendiente de validación
            )

        # 4. Actualizar estado de la Cotización
        cotizacion.estado = 'ganada'
        cotizacion.resultado = 'ganada'
        cotizacion.save()

        messages.success(request, f'Pedido #{nuevo_pedido.id} creado exitosamente. Por favor confírmalo para validar stock.')
        crear_notificacion(
            empresa=empresa_actual,
            actor=request.user,
            mensaje=f'generó el pedido #{nuevo_pedido.id:04d} desde {cotizacion.folio_completo}',
            propietario=request.user
        )
        return redirect('dashboard_pedidos')

    except Exception as e:
        messages.error(request, f'Error al crear pedido: {str(e)}')
        return redirect('dashboard_cotizaciones')

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'validar_stock')
def validar_pedido(request, pedido_id):
    """
    Diagnóstico básico. Deja la lógica de decisión de compra/producción
    para cuando el usuario da clic en "Solicitar".
    """
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)

    if pedido.estado != 'borrador':
        messages.warning(request, 'Este pedido ya ha sido procesado.')
        return redirect('dashboard_pedidos')

    # 1. Diagnosticar líneas
    for detalle in pedido.detalles.all():
        
        # --- NUEVO: Omitir validación de stock para servicios ---
        if detalle.producto.tipo == 'servicio':
            detalle.estado_linea = 'pendiente'
            detalle.save()
            continue
        # --------------------------------------------------------

        stock_libre = detalle.producto.stock_disponible
        solicitado = detalle.cantidad_solicitada
        
        # --- LÓGICA PARA PRODUCCIÓN ---
        if detalle.producto.tipo_abastecimiento == 'produccion':
            
            if stock_libre >= solicitado:
                # Hay producto terminado, se puede reservar directo
                detalle.estado_linea = 'pendiente'
                detalle.save()
            else:
                # No hay producto terminado. Lo marcamos como COMPRA.
                # El botón "Solicitar" se encargará de pedir los componentes.
                detalle.estado_linea = 'compra'
                detalle.save()

        # --- LÓGICA NORMAL (STOCK / COMPRA) ---
        elif detalle.producto.tipo_abastecimiento in ['stock', 'compra']:
            
            if stock_libre >= solicitado:
                detalle.estado_linea = 'pendiente'
                detalle.save()
                
            elif stock_libre > 0:
                # Stock Parcial
                faltante = solicitado - stock_libre
                
                DetallePedido.objects.create(
                    pedido=detalle.pedido,
                    producto=detalle.producto,
                    cantidad_solicitada=faltante,
                    precio_unitario=detalle.precio_unitario,
                    estado_linea='compra',
                    parent_line=detalle
                )
                
                detalle.cantidad_solicitada = stock_libre
                detalle.estado_linea = 'pendiente'
                detalle.save()
                
            else:
                # Sin Stock
                detalle.estado_linea = 'compra'
                detalle.save()

    pedido.estado = 'revision'
    pedido.save()
    
    messages.success(request, 'Validación completada. Revise las partidas faltantes.')
    return redirect('dashboard_pedidos')

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'revision', json_response=True)
def api_detalle_pedido(request, pedido_id):
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)
    
    # 1. OBTENER TODOS LOS DETALLES
    # Obtenemos todo, el orden por ID no importa ahora, lo reordenaremos abajo
    todos_los_detalles = pedido.detalles.all()
    
    # 2. REORDENAMIENTO LÓGICO (ALGORITMO DE JERARQUÍA)
    # Separamos en Raíces (sin padre) e Hijos (con padre)
    raices = []
    mapa_hijos = defaultdict(list)
    
    for det in todos_los_detalles:
        if det.parent_line:
            # Guardamos al hijo en la lista de su padre
            mapa_hijos[det.parent_line.id].append(det)
        else:
            # Es una línea principal
            raices.append(det)
            
    # Función auxiliar para construir la lista final ordenada
    lista_ordenada_final = []
    
    def agregar_con_hijos(detalle):
        lista_ordenada_final.append(detalle)
        # Si este detalle tiene hijos, los agregamos inmediatamente después (recursivo)
        hijos = mapa_hijos.get(detalle.id, [])
        # Ordenamos hijos por ID por si hay varios, para que salgan en orden
        hijos.sort(key=lambda x: x.id) 
        for hijo in hijos:
            agregar_con_hijos(hijo)
            
    # Construimos la lista final recorriendo las raíces
    for raiz in raices:
        agregar_con_hijos(raiz)
        
    # 3. ASIGNAR NÚMEROS DE PARTIDA BASADOS EN EL ORDEN VISUAL
    # Ahora que la lista está ordenada (Padre -> Hijo -> Padre -> Hijo...)
    # El número de partida será secuencial 1, 2, 3... según lo que ve el usuario.
    mapa_partidas = {det.id: (i + 1) for i, det in enumerate(lista_ordenada_final)}
    
    # 4. GENERAR LA RESPUESTA JSON
    detalles_data = []
    for det in lista_ordenada_final:
        stock_total = det.producto.stock_total
        stock_disponible = det.producto.stock_disponible
        stock_reservado = stock_total - stock_disponible
        
        # Lógica de etiqueta de parte de...
        texto_parte_de = ""
        if det.parent_line_id:
            num_partida_padre = mapa_partidas.get(det.parent_line_id, "?")
            texto_parte_de = f"(Parte de Partida {num_partida_padre})"
        
        detalles_data.append({
            'id': det.id,
            'producto': det.producto.nombre,
            'solicitado': det.cantidad_solicitada,
            'stock_total': stock_total,
            'stock_reservado': stock_reservado,
            'stock_disponible': stock_disponible,
            'estado_linea': det.estado_linea,
            'estado_display': det.get_estado_linea_display(),
            'texto_parte_de': texto_parte_de
        })
        
    return JsonResponse({'detalles': detalles_data})

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'revision')
def completar_linea_pedido(request, detalle_id):
    """
    Acción manual para marcar que un producto de "Compra" o "Producción" ya llegó/terminó.
    Esto mueve la línea a 'completo'.
    """
    empresa_actual = get_empresa_actual(request)
    # Necesitamos buscar el detalle a través del pedido para validar empresa
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = get_object_or_404(Pedido, id=detalle.pedido.id, empresa=empresa_actual)

    if detalle.estado_linea in ['compra', 'produccion', 'parcial']:
        detalle.estado_linea = 'completo'
        detalle.cantidad_entregada = detalle.cantidad_solicitada
        detalle.save()
        messages.success(request, f'Línea marcada como completa.')
        
        # Verificar si todo el pedido está completo
        verificar_completitud_pedido(pedido)
    else:
        messages.info(request, 'Esta línea no requiere acción o ya está completa.')

    return redirect('dashboard_pedidos')

def verificar_completitud_pedido(pedido):
    """Revisa si todas las líneas están completas para generar la venta"""
    detalles = pedido.detalles.all()
    if all(d.estado_linea == 'completo' for d in detalles):
        pedido.estado = 'completo'
        pedido.save()
        
        # --- GENERAR VENTA AQUÍ ---
        # Intenta importar el modelo Venta. Ajusta la ruta según tu estructura real.
        try:
            from ventas.models import Venta # Ajustar ruta si es necesario
            for det in detalles:
                Venta.objects.create(
                    producto=det.producto,
                    cliente=str(pedido.cliente),
                    cantidad=det.cantidad_solicitada,
                    total=det.subtotal,
                    fecha=timezone.now(),
                    empresa=pedido.empresa
                )
            # Nota: Aquí podrías guardar un mensaje en sesión, pero como es función auxiliar interna,
            # lo ideal es que la vista que llama maneje el mensaje de éxito de venta.
        except ImportError:
            pass # Si no existe el modelo ventas, no falla el proceso de pedido

@login_required(login_url='/login/')
@transaction.atomic # Asegura que si falla, no guarde nada a medias
@require_sales_permission('pedidos', 'reservar', json_response=True)
def ejecutar_reserva(request, detalle_id):
    """
    Reserva físicamente el stock en Inventario y marca la línea como 'reservado'
    """
    from almacenes.models import Inventario
    from django.db.models import F

    empresa_actual = get_empresa_actual(request)
    
    # Obtener el detalle
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    
    # Seguridad: Verificar que el detalle pertenezca a un pedido de la empresa
    pedido = get_object_or_404(Pedido, id=detalle.pedido.id, empresa=empresa_actual)

    if detalle.estado_linea != 'pendiente':
        return JsonResponse({'success': False, 'error': 'Esta línea ya fue procesada o no se puede reservar.'})

    # --- NUEVO: Omitir reserva física para servicios ---
    if detalle.producto.tipo == 'servicio':
        detalle.estado_linea = 'reservado'
        detalle.save()
        
        # Verificar si el pedido está COMPLETO
        lineas_pendientes = pedido.detalles.filter(
            estado_linea__in=['pendiente', 'compra', 'en_proceso', 'produccion', 'comprado']
        ).count()

        if lineas_pendientes == 0:
            pedido.estado = 'completo'
            pedido.save()

        return JsonResponse({'success': True, 'message': 'Servicio marcado como listo.'})
    # ----------------------------------------------------

    # 1. Verificar que todavía haya stock libre (por si acaso alguien más compró mientras tanto)
    stock_libre = detalle.producto.stock_disponible
    
    if stock_libre < detalle.cantidad_solicitada:
        return JsonResponse({'success': False, 'error': 'Ya no hay stock suficiente para reservar.'})

    # 2. Realizar la Reserva Física
    faltante_por_reservar = detalle.cantidad_solicitada
    
    inventarios_con_stock = Inventario.objects.filter(
        producto=detalle.producto
    ).annotate(
        disponible_calc=F('cantidad') - F('reservado')
    ).order_by('-disponible_calc')

    for inv in inventarios_con_stock:
        if faltante_por_reservar <= 0:
            break
        
        cuanto_puedo_reservar_aqui = inv.disponible_calc
        
        if cuanto_puedo_reservar_aqui > 0:
            if cuanto_puedo_reservar_aqui >= faltante_por_reservar:
                inv.reservado += faltante_por_reservar
                inv.save()
                faltante_por_reservar = 0
            else:
                inv.reservado += cuanto_puedo_reservar_aqui
                inv.save()
                faltante_por_reservar -= cuanto_puedo_reservar_aqui

    # 3. Actualizar estado de la línea
    detalle.estado_linea = 'reservado'
    detalle.save()

    crear_notificacion(
        empresa=empresa_actual,
        actor=request.user,
        mensaje=f'reservó {detalle.cantidad_solicitada} pz de {detalle.producto.nombre} para Pedido #{pedido.id:04d}',
        propietario=pedido.vendedor
    )

    # --- NUEVA LÓGICA: Verificar si el pedido está COMPLETO ---
    # Buscamos si quedan líneas que NO estén 'reservadas' o 'completas'
    # (es decir, si quedan pendientes, en compra o en proceso)
    lineas_pendientes = pedido.detalles.filter(
        estado_linea__in=['pendiente', 'compra', 'en_proceso', 'produccion', 'comprado']
    ).count()

    # Si el contador es 0, significa que todo el pedido está listo (reservado)
    if lineas_pendientes == 0:
        pedido.estado = 'completo'
        pedido.save()

    return JsonResponse({'success': True, 'message': 'Stock reservado correctamente.'})

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'generar_solicitud_global')
def generar_solicitud_global(request, pedido_id):
    """
    Genera UNA sola solicitud de compra para TODAS las partidas 'compra' del pedido.
    Explosiona recetas de producción y agrupa componentes.
    """
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)

    # 1. Buscar todas las líneas que necesitan compra
    lineas_a_comprar = DetallePedido.objects.filter(pedido=pedido, estado_linea='compra')

    if not lineas_a_comprar.exists():
        messages.warning(request, 'No hay partidas pendientes de compra en este pedido.')
        return redirect('dashboard_pedidos')

    # 2. Buscar o Crear la Solicitud de Compra Maestra para este pedido
    solicitud_maestra = SolicitudCompra.objects.filter(
        pedido_origen=pedido,
        estado='borrador',
        empresa=empresa_actual
    ).first()

    if not solicitud_maestra:
        solicitud_maestra = SolicitudCompra.objects.create(
            pedido_origen=pedido,
            solicitante=request.user,
            empresa=empresa_actual,
            estado='borrador',
            sucursal=pedido.sucursal,
            notas="Solicitud Global Generada Automáticamente"
        )

    # 3. Mapa para agrupar items en la solicitud (evita duplicados)
    mapa_solicitud = {}
    
    # Precargar items que ya estén en la solicitud
    for det_sol in solicitud_maestra.detalles.all():
        mapa_solicitud[det_sol.producto.id] = det_sol

    # 4. Procesar cada línea del pedido
    for linea_pedido in lineas_a_comprar:
        producto = linea_pedido.producto
        
        # --- CASO A: PRODUCCIÓN ---
        if producto.tipo_abastecimiento == 'produccion':
            # 1. Crear la Orden de Producción vinculada al pedido (En Borrador)
            op = OrdenProduccion.objects.create(
                empresa=empresa_actual,
                producto=producto,
                cantidad=linea_pedido.cantidad_solicitada,
                pedido_origen=pedido,
                solicitante=request.user, # Quién dispara la solicitud
                almacen=linea_pedido.pedido.cliente.almacen if hasattr(linea_pedido.pedido.cliente, 'almacen') and linea_pedido.pedido.cliente.almacen else Almacen.objects.filter(empresa=empresa_actual).first(),
                estado='borrador',
                notas=f"Generada automáticamente desde Pedido #{pedido.id}",
                sucursal=pedido.sucursal
            )

            # 2. Explorar receta y COPIAR a DetalleOrdenProduccion
            receta = DetalleReceta.objects.filter(producto_padre=producto)
            
            if not receta.exists():
                messages.error(request, f'El producto "{producto.nombre}" es de producción pero NO TIENE RECETA asignada.')
                continue

            for item_receta in receta:
                # Copiamos a la tabla de la orden específica
                from produccion.models import DetalleOrdenProduccion
                DetalleOrdenProduccion.objects.create(
                    orden_produccion=op,
                    producto=item_receta.componente,
                    cantidad=item_receta.cantidad * linea_pedido.cantidad_solicitada
                )

                # Lógica de compra para materiales faltantes
                componente = item_receta.componente
                cantidad_necesaria = item_receta.cantidad * linea_pedido.cantidad_solicitada
                stock_componente = componente.stock_disponible
                
                if stock_componente < cantidad_necesaria:
                    faltante = cantidad_necesaria - stock_componente
                    
                    # Agregar o sumar al mapa
                    if componente.id in mapa_solicitud:
                        det_sol_existente = mapa_solicitud[componente.id]
                        det_sol_existente.cantidad_solicitada += faltante
                        det_sol_existente.costo_unitario = componente.precio_costo
                        # Mantenemos el vínculo al pedido si ya existe, o lo ponemos
                        if not det_sol_existente.detalle_pedido_origen:
                            det_sol_existente.detalle_pedido_origen = linea_pedido
                        det_sol_existente.save()
                    else:
                        nuevo_det = DetalleSolicitudCompra.objects.create(
                            solicitud=solicitud_maestra,
                            producto=componente,
                            cantidad_solicitada=faltante,
                            costo_unitario=componente.precio_costo,
                            detalle_pedido_origen=linea_pedido # <--- VÍNCULO CRÍTICO
                        )
                        mapa_solicitud[componente.id] = nuevo_det
                    componentes_agregados = True
            
            if not componentes_agregados:
                # CAMBIO: Aviso de por qué se saltó
                messages.warning(request, f'El producto "{producto.nombre}" se ignora porque YA TIENES STOCK SUFICIENTE de todos sus componentes.')

        # --- CASO B: STOCK / COMPRA (NORMAL) ---
        else:
            # Agregar o sumar el producto final
            if producto.id in mapa_solicitud:
                det_sol_existente = mapa_solicitud[producto.id]
                det_sol_existente.cantidad_solicitada += linea_pedido.cantidad_solicitada
                det_sol_existente.costo_unitario = producto.precio_costo
                if not det_sol_existente.detalle_pedido_origen:
                    det_sol_existente.detalle_pedido_origen = linea_pedido
                det_sol_existente.save()
            else:
                nuevo_det = DetalleSolicitudCompra.objects.create(
                    solicitud=solicitud_maestra,
                    producto=producto,
                    cantidad_solicitada=linea_pedido.cantidad_solicitada,
                    costo_unitario=producto.precio_costo,
                    detalle_pedido_origen=linea_pedido # <--- VÍNCULO CRÍTICO
                )
                mapa_solicitud[producto.id] = nuevo_det

    # 5. Actualizar el estado de todas las líneas procesadas
    lineas_a_comprar.update(estado_linea='en_proceso')

    # NOTIFICACIÓN
    crear_notificacion(
        empresa=empresa_actual,
        mensaje=f"Se ha generado una Solicitud de Compra desde el Pedido #{pedido.id}",
        actor=request.user,
        propietario=pedido.vendedor if pedido.vendedor else None
    )

    messages.success(request, f'Solicitud Global generada exitosamente con {len(mapa_solicitud)} ítems únicos.')
    return redirect('dashboard_solicitudcompras')

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'ver', json_response=True)
def obtener_pedido_json(request, pedido_id):
    """Devuelve los datos de un pedido específico para visualizar"""
    try:
        empresa_actual = get_empresa_actual(request)
        pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)
        
        data = {
            'folio': f"PED-{pedido.id:04d}",
            'cliente_nombre': pedido.cliente.razon_social or f"{pedido.cliente.nombre} {pedido.cliente.apellidos}",
            'cliente_tel': pedido.cliente.telefono or '--',
            'cliente_email': pedido.cliente.email or '--',
            'contacto_nombre': pedido.contacto.nombre_completo if pedido.contacto else 'Sin contacto',
            'contacto_tel': pedido.contacto.telefono_1 if pedido.contacto else '--',
            'contacto_email': pedido.contacto.correo_1 if pedido.contacto else '--',
            'fecha': pedido.fecha_creacion.strftime('%d/%m/%Y'),
            'cotizacion_folio': f"COT-{pedido.cotizacion_origen_id:04d}" if pedido.cotizacion_origen_id else '--',
            'detalles': []
        }

        for det in pedido.detalles.all():
            data['detalles'].append({
                'producto': det.producto.nombre,
                'solicitado': det.cantidad_solicitada,
                'estado': det.get_estado_linea_display()
            })

        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'imprimir')
def imprimir_pedido(request, pk):
    """Genera la vista para impresión de pedido (PDF)"""
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pk, empresa=empresa_actual)

    # Limpiar nombre del vendedor (quitar @empresa si es necesario)
    vendedor_nombre = pedido.vendedor.get_full_name()
    if not vendedor_nombre:
        vendedor_nombre = pedido.vendedor.username.split('@')[0]

    context = {
        'pedido': pedido,
        'empresa': empresa_actual,
        'vendedor_nombre': vendedor_nombre,
    }
    return render(request, 'pedidos/imprimir_pedido.html', context)

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'registrar_pago', json_response=True)
def api_info_pago_pedido(request, pedido_id):
    """Devuelve los datos necesarios para el modal de pago de un pedido"""
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)
    
    data = {
        'id': pedido.id,
        'cliente_nombre': pedido.cliente.nombre_completo,
        'rfc': pedido.cliente.rfc or '--',
        'fecha_pedido': pedido.fecha_creacion.strftime('%d/%m/%Y'),
        'total_pedido': float(pedido.total_pedido),
        'total_pagado': float(pedido.total_pagado),
        'saldo_pendiente': float(pedido.saldo_pendiente),
    }
    return JsonResponse(data)

@login_required(login_url='/login/')
@require_sales_permission('pedidos', 'editar', json_response=True)
def api_detalle_pedido_edicion(request, pedido_id):
    """Devuelve JSON con la info del pedido para cargar el modal de edición"""
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)
    
    detalles = []
    for det in pedido.detalles.all():
        detalles.append({
            'producto_id': det.producto.id,
            'producto_nombre': det.producto.nombre,
            'cantidad': det.cantidad_solicitada,
            'precio_unitario': float(det.precio_unitario),
            'total': float(det.subtotal)
        })

    data = {
        'success': True,
        'id': pedido.id,
        'cliente_id': pedido.cliente.id,
        'cliente_nombre': pedido.cliente.razon_social or pedido.cliente.nombre_completo,
        'contacto_id': pedido.contacto.id if pedido.contacto else '',
        'notas': pedido.notas or '',
        'detalles': detalles,
        'total': float(pedido.total_pedido)
    }
    return JsonResponse(data)

@login_required(login_url='/login/')
@transaction.atomic
@require_sales_permission('pedidos', 'editar', json_response=True)
def editar_pedido_ajax(request, pedido_id):
    """Actualiza un pedido existente"""
    empresa_actual = get_empresa_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)

    if request.method == 'POST':
        try:
            cliente_id = request.POST.get('cliente')
            contacto_id = request.POST.get('contacto')
            notas = request.POST.get('notas', '')

            if not cliente_id:
                return JsonResponse({'success': False, 'error': 'El cliente es obligatorio.'})

            cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
            contacto = None
            if contacto_id:
                contacto = get_object_or_404(ContactoCliente, id=contacto_id, cliente=cliente)

            # 1. Actualizar Cabecera
            pedido.cliente = cliente
            pedido.contacto = contacto
            pedido.notas = notas
            pedido.save()

            # 2. Actualizar Detalles (Sustituir por los nuevos)
            # Nota: Si ya se reservó stock o algo más avanzado, esto debería ser más complejo.
            # Por simplicidad en este módulo, borramos y recreamos.
            pedido.detalles.all().delete()

            productos_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            precios = request.POST.getlist('precio_unitario[]')

            count = 0
            for prod_id, cant, prec in zip(productos_ids, cantidades, precios):
                if prod_id and prod_id != '':
                    producto_obj = get_object_or_404(Producto, id=prod_id, empresa=empresa_actual)
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto=producto_obj,
                        cantidad_solicitada=cant,
                        precio_unitario=prec,
                        estado_linea='pendiente'
                    )
                    count += 1
            
            if count == 0:
                raise Exception("Debes agregar al menos un producto al pedido.")

            messages.success(request, f'Pedido #{pedido.id} actualizado correctamente.')
            crear_notificacion(
                empresa=empresa_actual,
                actor=request.user,
                mensaje=f'editó el pedido #{pedido.id:04d}',
                propietario=request.user
            )
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})
