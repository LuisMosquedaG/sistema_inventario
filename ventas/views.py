from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from .models import OrdenVenta, DetalleOrdenVenta
from pedidos.models import Pedido, DetallePedido
from panel.models import Empresa
from almacenes.models import Inventario # Asegúrate de importar tu modelo Inventario
from django.db.models import F

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

@login_required
def dashboard_ventas(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    # 1. Cargamos las órdenes con sus relaciones principales
    ordenes = OrdenVenta.objects.filter(empresa=empresa_actual).select_related('pedido_origen', 'cliente').order_by('-fecha_creacion')
    
    # 2. Recolectamos los IDs de cotización únicos que están en los pedidos
    cotizaciones_ids = set()
    for orden in ordenes:
        if orden.pedido_origen and orden.pedido_origen.cotizacion_origen_id:
            cotizaciones_ids.add(orden.pedido_origen.cotizacion_origen_id)
    
    # 3. Mapa de fechas
    # NOTA: Usamos 'creado_en' porque así se llama el campo en tu modelo Cotizacion
    fechas_map = {}
    if cotizaciones_ids:
        from cotizaciones.models import Cotizacion 
        # CORRECCIÓN: Usamos 'creado_en' en lugar de 'fecha_creacion'
        datos_cot = Cotizacion.objects.filter(id__in=cotizaciones_ids).values('id', 'creado_en')
        for dato in datos_cot:
            fechas_map[dato['id']] = dato['creado_en']

    # 4. Adjuntamos la fecha a cada objeto 'orden' como un atributo temporal
    for orden in ordenes:
        orden.fecha_cotizacion_display = None
        if orden.pedido_origen and orden.pedido_origen.cotizacion_origen_id:
            orden.fecha_cotizacion_display = fechas_map.get(orden.pedido_origen.cotizacion_origen_id)

    contexto = {'ordenes': ordenes}
    return render(request, 'dashboard_ventas.html', contexto)

@login_required
@transaction.atomic
def crear_orden_venta(request, pedido_id):
    """Crea una Orden de Venta en Borrador basada en un Pedido Confirmado"""
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        messages.error(request, "Empresa no detectada")
        return redirect('dashboard_pedidos')

    pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)

    # Validamos que el pedido esté en estado 'confirmado' o 'completo' (todo reservado)
    if pedido.estado not in ['confirmado', 'completo']:
        messages.error(request, 'Solo se pueden generar Órdenes de Venta desde pedidos confirmados.')
        return redirect('dashboard_pedidos')

    # Verificamos si ya existe una OV para este pedido
    if hasattr(pedido, 'orden_venta'):
        messages.warning(request, 'Este pedido ya tiene una Orden de Venta generada.')
        return redirect('dashboard_ventas')

    # 1. Crear Cabecera OV
    ov = OrdenVenta.objects.create(
        pedido_origen=pedido,
        cliente=pedido.cliente,
        vendedor=request.user,
        empresa=empresa_actual,
        estado='borrador'
    )

    # 2. Copiar Detalles (solo las líneas principales, omitimos hijos si los hubo de splits)
    # Opcional: Podrías querer aplanar todo, pero asumiremos las líneas principales.
    lineas_pedido = pedido.detalles.filter(parent_line__isnull=True)
    
    for linea in lineas_pedido:
        DetalleOrdenVenta.objects.create(
            orden_venta=ov,
            producto=linea.producto,
            cantidad=linea.cantidad_solicitada,
            precio_unitario=linea.precio_unitario
        )

    messages.success(request, f'Orden de Venta #{ov.id} creada en estado Borrador.')
    return redirect('dashboard_ventas')

@login_required
def cambiar_estado_ov(request, ov_id, nuevo_estado):
    """Cambia estados simples (Borrador -> Aprobado)"""
    empresa_actual = get_empresa_actual(request)
    ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)

    if nuevo_estado == 'aprobado' and ov.estado == 'borrador':
        ov.estado = 'aprobado'
        ov.save()
        messages.success(request, 'Orden de Venta Aprobada. Lista para surtir.')
    
    return redirect('dashboard_ventas')

@login_required
def api_preparar_surtido(request, ov_id):
    """Retorna JSON detallado para el Modal de Surtido con jerarquía de datos"""
    empresa_actual = get_empresa_actual(request)
    ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)

    # Permitimos ver los detalles si está Aprobada (para surtir) o Surtida (para consultar)
    if ov.estado not in ['aprobado', 'surtido']:
        return JsonResponse({'success': False, 'error': 'Estado inválido para ver detalles.'})

    cliente = ov.cliente
    pedido_origen = ov.pedido_origen
    
    # --- 1. DATOS DEL CLIENTE PRINCIPAL (Solo lectura) ---
    razon_social = cliente.razon_social if cliente.razon_social else ""
    nombre_completo = f"{cliente.nombre} {cliente.apellidos}" if not razon_social else ""
    correo_cliente = getattr(cliente, 'email', '')
    telefono_cliente = getattr(cliente, 'telefono', '')
    
    # Construir dirección fiscal completa
    dir_parts = []
    if cliente.calle: dir_parts.append(cliente.calle)
    if cliente.numero_ext: dir_parts.append(f"#{cliente.numero_ext}")
    if cliente.numero_int: dir_parts.append(f"Int {cliente.numero_int}")
    if cliente.colonia: dir_parts.append(cliente.colonia)
    if cliente.cp: dir_parts.append(f"CP {cliente.cp}")
    if cliente.estado_dir: dir_parts.append(cliente.estado_dir)
    direccion_completa = ", ".join(dir_parts)

    # --- 2. DATOS DEL CONTACTO (De la Cotización si existe) ---
    contacto_nombre = ""
    contacto_correo = ""
    contacto_telefono = ""
    
    if pedido_origen.cotizacion_origen_id:
        try:
            from cotizaciones.models import Cotizacion
            cotizacion = Cotizacion.objects.get(id=pedido_origen.cotizacion_origen_id, empresa=empresa_actual)
            if cotizacion.contacto:
                contacto_nombre = cotizacion.contacto.nombre_completo
                contacto_correo = cotizacion.contacto.correo_1 or cotizacion.contacto.correo_2 or ""
                contacto_telefono = cotizacion.contacto.telefono_1 or cotizacion.contacto.telefono_2 or ""
        except:
            pass

    # --- 3. DATOS DE ENVÍO (CON JERARQUÍA: OV -> CLIENTE -> CONTACTO) ---
    
    # A. Construir dirección de envío por defecto del Cliente
    envio_parts = []
    if getattr(cliente, 'envio_calle', ''): envio_parts.append(cliente.envio_calle)
    if getattr(cliente, 'envio_numero_ext', ''): envio_parts.append(f"#{cliente.envio_numero_ext}")
    if getattr(cliente, 'envio_numero_int', ''): envio_parts.append(f"Int {cliente.envio_numero_int}")
    if getattr(cliente, 'envio_colonia', ''): envio_parts.append(cliente.envio_colonia)
    if getattr(cliente, 'envio_cp', ''): envio_parts.append(f"CP {cliente.envio_cp}")
    if getattr(cliente, 'envio_estado', ''): envio_parts.append(cliente.envio_estado)
    direccion_cliente_envio = ", ".join(envio_parts)

    # B. Determinar "Quién Recibe"
    # 1. Si ya está guardado en la OV -> Usar ese.
    # 2. Si no -> Usar "Envio Quien Recibe" del cliente.
    # 3. Si no -> Usar el nombre del cliente.
    final_quien_recibe = ov.quien_recibe
    if not final_quien_recibe:
        final_quien_recibe = getattr(cliente, 'envio_quien_recibe', '') or cliente.nombre

    # C. Determinar "Teléfono Recibe"
    # 1. OV -> 2. Cliente Envio -> 3. Contacto Cotización -> 4. Cliente General
    final_telefono = ov.telefono_recibe
    if not final_telefono:
        final_telefono = getattr(cliente, 'envio_telefono', '') or contacto_telefono or telefono_cliente

    # D. Determinar "Correo Recibe"
    # 1. OV -> 2. Cliente Envio -> 3. Contacto Cotización -> 4. Cliente General
    final_correo = ov.contacto_envio
    if not final_correo:
        final_correo = getattr(cliente, 'envio_correo', '') or contacto_correo or correo_cliente

    # E. Determinar Notas
    final_notas = ov.notas_envio
    if not final_notas:
        final_notas = getattr(cliente, 'envio_notas', '')

    # --- 4. DETALLES DE ARTÍCULOS ---
    detalles_data = []
    total_calculado = 0
    for det in ov.detalles.all():
        subtotal = float(det.subtotal)
        total_calculado += subtotal
        detalles_data.append({
            'producto': det.producto.nombre,
            'cantidad': det.cantidad,
            'precio': float(det.precio_unitario),
            'subtotal': subtotal
        })

    data = {
        'id': ov.id,
        
        # Sección Cliente
        'cliente_razon': razon_social,
        'cliente_nombre': nombre_completo,
        'cliente_correo': correo_cliente,
        'cliente_telefono': telefono_cliente,
        'cliente_direccion': direccion_completa,
        
        # Subsección Contacto
        'contacto_nombre': contacto_nombre,
        'contacto_correo': contacto_correo,
        'contacto_telefono': contacto_telefono,
        
        # Sección Envío (Campos para el formulario)
        # Si la OV tiene datos, usa esos (para reedición). Si no, usa los defaults calculados arriba.
        'direccion_envio': ov.direccion_envio if ov.direccion_envio else direccion_cliente_envio,
        'quien_recibe': final_quien_recibe,
        'telefono_recibe': final_telefono,
        'email': final_correo, 
        'guia': ov.guia or '',
        'notas_envio': final_notas,
        
        # Artículos y Total
        'detalles': detalles_data,
        'total': total_calculado
    }
    return JsonResponse(data)

@login_required
@transaction.atomic
def ejecutar_surtido(request, ov_id):
    """Procesa el surtido con todos los nuevos campos"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    empresa_actual = get_empresa_actual(request)
    ov = get_object_or_404(OrdenVenta, id=ov_id, empresa=empresa_actual)

    if ov.estado != 'aprobado':
        return JsonResponse({'success': False, 'error': 'Estado inválido'})

    # 1. Actualizar todos los campos de envío
    ov.direccion_envio = request.POST.get('direccion')
    ov.quien_recibe = request.POST.get('quien_recibe')
    ov.telefono_recibe = request.POST.get('telefono_recibe')
    ov.guia = request.POST.get('guia')
    ov.notas_envio = request.POST.get('notas')
    
    # El contacto_envio (correo) se guarda si quieres, pero ya lo tenemos en la cotización
    
    ov.fecha_surtido = timezone.now()
    
    try:
        # 2. Lógica de Descontar Inventario (Misma que antes)
        for det in ov.detalles.all():
            producto = det.producto
            cantidad_a_descontar = det.cantidad

            # Usamos select_for_update() para bloquear las filas durante
            # la transacción y evitar condiciones de carrera entre usuarios.
            inventarios = Inventario.objects.select_for_update().filter(
                producto=producto,
                reservado__gt=0
            ).order_by('id')

            pendiente = cantidad_a_descontar
            for inv in inventarios:
                if pendiente <= 0:
                    break

                reservado_aqui = inv.reservado
                if reservado_aqui > 0:
                    quitar = min(pendiente, reservado_aqui)

                    # CORRECCIÓN PRINCIPAL: Usamos update() en lugar de
                    # asignar F() al objeto y llamar save().
                    # update() modifica SOLO los campos indicados directamente
                    # en la BD, sin tocar costo_promedio ni ningún otro campo.
                    Inventario.objects.filter(pk=inv.pk).update(
                        cantidad=F('cantidad') - quitar,
                        reservado=F('reservado') - quitar
                    )

                    # REGISTRAR EN KARDEX MANUALMENTE YA QUE USAMOS UPDATE()
                    from almacenes.models import Kardex
                    Kardex.objects.create(
                        empresa=empresa_actual,
                        producto=producto,
                        almacen=inv.almacen,
                        tipo_movimiento='salida',
                        cantidad=quitar,
                        stock_anterior=inv.cantidad,
                        stock_nuevo=inv.cantidad - quitar,
                        referencia=f"OV-{ov.id:04d}"
                    )
                    
                    pendiente -= quitar

            if pendiente > 0:
                raise Exception(f"Stock insuficiente para surtir {producto.nombre}.")

        ov.estado = 'surtido'
        ov.save()
        return JsonResponse({'success': True, 'message': 'Orden surtida correctamente.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})