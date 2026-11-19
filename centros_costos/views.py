import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Sum
from django.core.paginator import Paginator

from panel.models import Empresa
from preferencias.models import Sucursal
from preferencias.permissions import require_centros_costos_permission
from .models import CentroCosto
from almacenes.models import DetalleSalidaPorUso, SalidaPorUso, Almacen
from tesoreria.models import Egreso, Ingreso
from compras.models import OrdenCompra
from pedidos.models import Pedido
from recepciones.models import Recepcion, DetalleRecepcion
from ventas.models import OrdenVenta

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
@require_centros_costos_permission('centros_costos', 'ver')
def dashboard_centros_costos(request):
    empresa = get_empresa_actual(request)
    if not empresa:
        return render(request, 'error_empresa.html')

    if not getattr(empresa, 'modulo_centros_costos', True):
        return redirect('dashboard_inicio')

    now = timezone.now()
    anio_actual = now.year
    mes_actual = now.month

    # Filtros
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    estado = request.GET.get('estado', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()
    almacen_id = request.GET.get('almacen', '').strip()

    centros_qs = CentroCosto.objects.filter(empresa=empresa).select_related('parent', 'sucursal', 'responsable', 'almacen')

    if q:
        centros_qs = centros_qs.filter(
            Q(codigo__icontains=q) |
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(responsable__username__icontains=q)
        )

    if tipo:
        centros_qs = centros_qs.filter(tipo=tipo)

    if estado == 'activos':
        centros_qs = centros_qs.filter(activo=True)
    elif estado == 'inactivos':
        centros_qs = centros_qs.filter(activo=False)

    if sucursal_id:
        centros_qs = centros_qs.filter(sucursal_id=sucursal_id)

    if almacen_id:
        centros_qs = centros_qs.filter(almacen_id=almacen_id)

    # Métricas Globales
    todos_empresa = CentroCosto.objects.filter(empresa=empresa)
    total_activos = todos_empresa.filter(activo=True).count()
    presupuesto_global = sum([c.presupuesto_mensual for c in todos_empresa.filter(activo=True)], Decimal('0.00'))

    # Calcular gastos de centros para la vista actual
    centros_con_metricas = []
    gasto_global_mes = Decimal('0.00')
    centros_alerta_count = 0

    for c in centros_qs:
        egresos_mes = c.calcular_egresos_mes(anio_actual, mes_actual)
        ingresos_mes = c.calcular_ingresos_mes(anio_actual, mes_actual)
        gastado = egresos_mes - ingresos_mes
        comprometido = c.calcular_comprometido_mes(anio_actual, mes_actual)
        pct = c.porcentaje_presupuesto(anio_actual, mes_actual)
        pct_total = c.porcentaje_total_comprometido(anio_actual, mes_actual)
        gasto_global_mes += gastado

        remanente = (c.presupuesto_mensual or Decimal('0.00')) - gastado

        # Alerta si supera 80% o está excedido
        if c.presupuesto_mensual > 0 and (pct >= 80 or pct_total >= 80):
            centros_alerta_count += 1

        centros_con_metricas.append({
            'obj': c,
            'egresos_mes': egresos_mes,
            'ingresos_mes': ingresos_mes,
            'gastado_mes': gastado,
            'comprometido_mes': comprometido,
            'pct_presupuesto': pct,
            'pct_total': pct_total,
            'remanente': remanente,
        })

    # Paginación
    paginator = Paginator(centros_con_metricas, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Datos para modales y selectores
    sucursales = Sucursal.objects.filter(empresa=empresa).order_by('nombre')
    almacenes = Almacen.objects.filter(empresa=empresa).select_related('sucursal').order_by('nombre')
    usuarios = User.objects.filter(
        Q(username__iendswith=f"@{empresa.subdominio}") |
        Q(roles_empresa__empresa=empresa),
        is_active=True
    ).distinct().exclude(username__icontains='@crossoversuite').order_by('first_name', 'username')

    for u in usuarios:
        nombre_completo = f"{u.first_name} {u.last_name}".strip()
        clean_user = u.username.split('@')[0] if '@' in u.username else u.username
        u.display_name = nombre_completo if nombre_completo else clean_user

    centros_padres = todos_empresa.filter(activo=True).order_by('codigo')

    MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    mes_nombre = MESES_ES[mes_actual]

    context = {
        'page_obj': page_obj,
        'filtros': {
            'q': q,
            'tipo': tipo,
            'estado': estado,
            'sucursal': sucursal_id,
            'almacen': almacen_id,
        },
        'total_activos': total_activos,
        'presupuesto_global': presupuesto_global,
        'gasto_global_mes': gasto_global_mes,
        'centros_alerta_count': centros_alerta_count,
        'sucursales': sucursales,
        'almacenes': almacenes,
        'usuarios': usuarios,
        'centros_padres': centros_padres,
        'mes_nombre': mes_nombre,
        'anio_actual': anio_actual,
    }

    return render(request, 'centros_costos/dashboard_centros_costos.html', context)


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'crear', json_response=True)
def crear_centro_costo_ajax(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    try:
        data = json.loads(request.body)
        codigo = (data.get('codigo') or '').strip().upper()
        nombre = (data.get('nombre') or '').strip()
        tipo = data.get('tipo', 'departamento')
        descripcion = data.get('descripcion', '').strip()
        parent_id = data.get('parent_id') or None
        sucursal_id = data.get('sucursal_id') or None
        almacen_id = data.get('almacen_id') or None
        responsable_id = data.get('responsable_id') or None
        presupuesto = Decimal(str(data.get('presupuesto_mensual') or 0))
        fecha_inicio = data.get('fecha_inicio') or None
        fecha_fin = data.get('fecha_fin') or None

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'El código y el nombre son obligatorios.'}, status=400)

        if CentroCosto.objects.filter(empresa=empresa, codigo=codigo).exists():
            return JsonResponse({'success': False, 'error': f'Ya existe un centro de costos con el código "{codigo}".'}, status=400)

        parent = None
        if parent_id:
            parent = CentroCosto.objects.filter(empresa=empresa, id=parent_id).first()

        sucursal = None
        if sucursal_id:
            sucursal = Sucursal.objects.filter(empresa=empresa, id=sucursal_id).first()

        almacen = None
        if almacen_id:
            almacen = Almacen.objects.filter(empresa=empresa, id=almacen_id).first()

        responsable = None
        if responsable_id:
            responsable = User.objects.filter(id=responsable_id).first()

        nuevo_cc = CentroCosto.objects.create(
            empresa=empresa,
            codigo=codigo,
            nombre=nombre,
            tipo=tipo,
            descripcion=descripcion,
            parent=parent,
            sucursal=sucursal,
            almacen=almacen,
            responsable=responsable,
            presupuesto_mensual=presupuesto,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            activo=True
        )

        # Si el almacén asignado no tiene centro de costo asignado, podemos asociarlo bidireccionalmente
        if almacen and not almacen.centro_costo_id:
            almacen.centro_costo = nuevo_cc
            almacen.save(update_fields=['centro_costo'])

        usuarios_autorizados = data.get('usuarios_autorizados', [])
        if usuarios_autorizados:
            nuevo_cc.usuarios_autorizados.set(usuarios_autorizados)

        return JsonResponse({
            'success': True,
            'message': f'Centro de costos "{nuevo_cc.codigo} - {nuevo_cc.nombre}" creado exitosamente.',
            'id': nuevo_cc.id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al crear centro de costos: {str(e)}'}, status=400)


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def obtener_centro_costo_json(request, centro_id):
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    cc = get_object_or_404(CentroCosto, id=centro_id, empresa=empresa)

    data = {
        'id': cc.id,
        'codigo': cc.codigo,
        'nombre': cc.nombre,
        'tipo': cc.tipo,
        'descripcion': cc.descripcion or '',
        'parent_id': cc.parent_id or '',
        'sucursal_id': cc.sucursal_id or '',
        'almacen_id': cc.almacen_id or '',
        'responsable_id': cc.responsable_id or '',
        'presupuesto_mensual': float(cc.presupuesto_mensual),
        'fecha_inicio': cc.fecha_inicio.strftime('%Y-%m-%d') if cc.fecha_inicio else '',
        'fecha_fin': cc.fecha_fin.strftime('%Y-%m-%d') if cc.fecha_fin else '',
        'activo': cc.activo,
        'usuarios_autorizados': list(cc.usuarios_autorizados.values_list('id', flat=True)),
    }

    return JsonResponse({'success': True, 'centro': data})


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def actualizar_centro_costo_ajax(request, centro_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    cc = get_object_or_404(CentroCosto, id=centro_id, empresa=empresa)

    try:
        data = json.loads(request.body)
        codigo = (data.get('codigo') or '').strip().upper()
        nombre = (data.get('nombre') or '').strip()
        tipo = data.get('tipo', 'departamento')
        descripcion = data.get('descripcion', '').strip()
        parent_id = data.get('parent_id') or None
        sucursal_id = data.get('sucursal_id') or None
        almacen_id = data.get('almacen_id') or None
        responsable_id = data.get('responsable_id') or None
        presupuesto = Decimal(str(data.get('presupuesto_mensual') or 0))
        fecha_inicio = data.get('fecha_inicio') or None
        fecha_fin = data.get('fecha_fin') or None

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'El código y el nombre son obligatorios.'}, status=400)

        if CentroCosto.objects.filter(empresa=empresa, codigo=codigo).exclude(id=cc.id).exists():
            return JsonResponse({'success': False, 'error': f'Ya existe otro centro de costos con el código "{codigo}".'}, status=400)

        # Prevenir auto-referencia circular
        parent = None
        if parent_id:
            if int(parent_id) == cc.id:
                return JsonResponse({'success': False, 'error': 'Un centro de costo no puede ser padre de sí mismo.'}, status=400)
            parent = CentroCosto.objects.filter(empresa=empresa, id=parent_id).first()

        sucursal = None
        if sucursal_id:
            sucursal = Sucursal.objects.filter(empresa=empresa, id=sucursal_id).first()

        almacen = None
        if almacen_id:
            almacen = Almacen.objects.filter(empresa=empresa, id=almacen_id).first()

        responsable = None
        if responsable_id:
            responsable = User.objects.filter(id=responsable_id).first()

        cc.codigo = codigo
        cc.nombre = nombre
        cc.tipo = tipo
        cc.descripcion = descripcion
        cc.parent = parent
        cc.sucursal = sucursal
        cc.almacen = almacen
        cc.responsable = responsable
        cc.presupuesto_mensual = presupuesto
        cc.fecha_inicio = fecha_inicio
        cc.fecha_fin = fecha_fin
        cc.save()

        # Si el almacén asignado no tiene centro de costo asignado, podemos asociarlo bidireccionalmente
        if almacen and not almacen.centro_costo_id:
            almacen.centro_costo = cc
            almacen.save(update_fields=['centro_costo'])

        usuarios_autorizados = data.get('usuarios_autorizados')
        if usuarios_autorizados is not None:
            cc.usuarios_autorizados.set(usuarios_autorizados)

        return JsonResponse({
            'success': True,
            'message': f'Centro de costos "{cc.codigo} - {cc.nombre}" actualizado correctamente.'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al actualizar: {str(e)}'}, status=400)


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def toggle_estado_centro_costo_ajax(request, centro_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    cc = get_object_or_404(CentroCosto, id=centro_id, empresa=empresa)
    cc.activo = not cc.activo
    cc.save(update_fields=['activo'])

    estado_txt = "activado" if cc.activo else "desactivado"
    return JsonResponse({
        'success': True,
        'activo': cc.activo,
        'message': f'Centro de costos "{cc.nombre}" {estado_txt} correctamente.'
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'eliminar', json_response=True)
def eliminar_centro_costo_ajax(request, centro_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    cc = get_object_or_404(CentroCosto, id=centro_id, empresa=empresa)

    # Validar si tiene relaciones
    tiene_subcentros = cc.subcentros.exists()
    tiene_spu = cc.salidas_por_uso.exists() or cc.detalles_salida_uso.exists()
    tiene_egresos = cc.egresos.exists()
    tiene_oc = cc.ordenes_compra.exists()

    if tiene_subcentros or tiene_spu or tiene_egresos or tiene_oc:
        return JsonResponse({
            'success': False,
            'error': f'No se puede eliminar el centro "{cc.nombre}" porque ya tiene registros o subcentros asociados. Puedes desactivarlo para que no aparezca en nuevas operaciones.'
        }, status=400)

    nombre = cc.nombre
    cc.delete()
    return JsonResponse({
        'success': True,
        'message': f'Centro de costos "{nombre}" eliminado correctamente.'
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver_movimientos', json_response=True)
def api_movimientos_centro_costo(request, centro_id):
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    cc = get_object_or_404(CentroCosto, id=centro_id, empresa=empresa)

    now = timezone.now()
    anio = int(request.GET.get('anio', now.year))
    mes = int(request.GET.get('mes', now.month))
    consolidar_param = request.GET.get('consolidar') in ['1', 'true', 'True']

    es_padre = cc.es_padre
    subcentros_directos = list(cc.subcentros.filter(activo=True))

    def get_descendant_ids(centro):
        ids = [centro.id]
        for child in centro.subcentros.filter(activo=True):
            ids.extend(get_descendant_ids(child))
        return list(set(ids))

    if consolidar_param and es_padre:
        centros_ids = get_descendant_ids(cc)
        consolidado = True
    else:
        centros_ids = [cc.id]
        consolidado = False

    # 1. Movimientos de Almacén y Mercancía (Entradas y Salidas)
    
    # 1.A. ENTRADAS: Recepciones de compras vinculadas a este centro de costos
    recepciones = Recepcion.objects.filter(
        orden_compra__centro_costo_id__in=centros_ids,
        empresa=empresa,
        fecha__year=anio,
        fecha__month=mes
    ).select_related('almacen', 'orden_compra', 'orden_compra__proveedor', 'orden_compra__centro_costo').prefetch_related('detalles__producto').order_by('-fecha')

    lista_recepciones = []
    total_recepciones = Decimal('0.00')
    for rec in recepciones:
        oc_cc = (rec.orden_compra.centro_costo if rec.orden_compra else None) or cc
        cc_codigo = oc_cc.codigo if oc_cc else '--'
        cc_nombre = oc_cc.nombre if oc_cc else '--'
        for det in rec.detalles.all():
            costo_total = Decimal(str(det.total or det.subtotal or 0))
            total_recepciones += costo_total
            lista_recepciones.append({
                'tipo': 'recepcion_compra',
                'movimiento': 'entrada',
                'tipo_label': 'Entrada (Recepción OC)',
                'folio': f"REC-{rec.id:04d}",
                'doc_origen': f"OC-{rec.orden_compra.id:04d}",
                'fecha': rec.fecha.strftime('%d/%m/%Y'),
                'fecha_dt': rec.fecha,
                'almacen': rec.almacen.nombre if rec.almacen else '--',
                'recibe': rec.orden_compra.proveedor.razon_social if (rec.orden_compra and rec.orden_compra.proveedor) else '--',
                'producto': det.producto.nombre,
                'cantidad': float(det.cantidad_recibida),
                'unidad': det.unidad_compra or 'pza',
                'costo_unitario': float(det.costo_unitario),
                'subtotal': float(costo_total),
                'estado': rec.get_estado_display() if hasattr(rec, 'get_estado_display') else rec.estado,
                'centro_costo': cc_codigo,
                'centro_costo_nombre': cc_nombre
            })

    # 1.B. SALIDAS: Salidas internas de almacén por uso / consumo
    spu_detalles = DetalleSalidaPorUso.objects.filter(
        Q(centro_costo_id__in=centros_ids) | Q(salida__centro_costo_id__in=centros_ids, centro_costo__isnull=True),
        salida__empresa=empresa
    ).exclude(salida__estado='cancelada').filter(
        Q(salida__fecha_salida__year=anio, salida__fecha_salida__month=mes) |
        Q(salida__fecha_salida__isnull=True, salida__fecha_creacion__year=anio, salida__fecha_creacion__month=mes)
    ).select_related('salida', 'producto', 'salida__usuario_recibe', 'salida__almacen', 'centro_costo', 'salida__centro_costo').order_by('-salida__fecha_creacion')

    lista_spu = []
    total_spu = Decimal('0.00')
    for d in spu_detalles:
        sub = Decimal(str(d.subtotal or 0))
        total_spu += sub
        f_salida = d.salida.fecha_salida or d.salida.fecha_creacion.date()
        spu_cc = d.centro_costo or d.salida.centro_costo or cc
        lista_spu.append({
            'tipo': 'salida_uso',
            'movimiento': 'salida',
            'tipo_label': 'Salida por Uso',
            'folio': d.salida.folio or f"SPU-{d.salida.id:04d}",
            'doc_origen': 'Consumo Interno',
            'fecha': f_salida.strftime('%d/%m/%Y'),
            'fecha_dt': f_salida,
            'almacen': d.salida.almacen.nombre if d.salida.almacen else '--',
            'recibe': (d.salida.usuario_recibe.get_full_name() or d.salida.usuario_recibe.username) if d.salida.usuario_recibe else '--',
            'producto': d.producto.nombre,
            'cantidad': float(d.cantidad),
            'unidad': d.unidad_medida or 'pza',
            'costo_unitario': float(d.costo_unitario),
            'subtotal': float(sub),
            'estado': d.salida.get_estado_display() if hasattr(d.salida, 'get_estado_display') else d.salida.estado,
            'centro_costo': spu_cc.codigo if spu_cc else '--',
            'centro_costo_nombre': spu_cc.nombre if spu_cc else '--'
        })

    # 1.C. SALIDAS: Salidas físicas por ventas / despacho de pedidos del centro de costo
    ordenes_venta = OrdenVenta.objects.filter(
        pedido_origen__centro_costo_id__in=centros_ids,
        empresa=empresa
    ).exclude(estado='cancelada').filter(
        Q(fecha_surtido__year=anio, fecha_surtido__month=mes) |
        Q(fecha_surtido__isnull=True, fecha_creacion__year=anio, fecha_creacion__month=mes)
    ).select_related('almacen', 'pedido_origen', 'cliente', 'pedido_origen__centro_costo').prefetch_related('detalles__producto').order_by('-fecha_creacion')

    lista_salidas_ventas = []
    total_salidas_ventas = Decimal('0.00')
    for ov in ordenes_venta:
        f_salida = (ov.fecha_surtido or ov.fecha_creacion)
        f_salida_dt = f_salida.date() if hasattr(f_salida, 'date') else f_salida
        ov_cc = (ov.pedido_origen.centro_costo if ov.pedido_origen else None) or cc

        for det in ov.detalles.all():
            costo_u = Decimal(str(getattr(det.producto, 'costo_estandar', 0) or det.precio_unitario or 0))
            cant = Decimal(str(det.cantidad or 0))
            sub = cant * costo_u
            total_salidas_ventas += sub

            cli_nom = ov.quien_recibe or (ov.cliente.razon_social or ov.cliente.nombre_completo if ov.cliente else '--')

            lista_salidas_ventas.append({
                'tipo': 'salida_venta',
                'movimiento': 'salida',
                'tipo_label': 'Salida por Venta',
                'folio': f"OV-{ov.id:04d}",
                'doc_origen': f"PED-{ov.pedido_origen.id:04d}",
                'fecha': f_salida_dt.strftime('%d/%m/%Y'),
                'fecha_dt': f_salida_dt,
                'almacen': ov.almacen.nombre if ov.almacen else '--',
                'recibe': cli_nom,
                'producto': det.producto.nombre,
                'cantidad': float(cant),
                'unidad': getattr(det.producto, 'unidad_medida', 'pza') or 'pza',
                'costo_unitario': float(costo_u),
                'subtotal': float(sub),
                'estado': ov.get_estado_display() if hasattr(ov, 'get_estado_display') else ov.estado,
                'centro_costo': ov_cc.codigo if ov_cc else '--',
                'centro_costo_nombre': ov_cc.nombre if ov_cc else '--'
            })

    # Combinamos todas las entradas y salidas de mercancía
    lista_salidas_totales = lista_spu + lista_salidas_ventas
    lista_mercancia = lista_recepciones + lista_salidas_totales
    lista_mercancia.sort(key=lambda x: x['fecha_dt'], reverse=True)
    for item in lista_mercancia:
        item.pop('fecha_dt', None)

    # 2. Egresos de tesorería
    egresos = Egreso.objects.filter(
        Q(centro_costo_id__in=centros_ids) | Q(pago_compra__orden_compra__centro_costo_id__in=centros_ids),
        empresa=empresa,
        estado='aplicado',
        fecha__year=anio,
        fecha__month=mes
    ).select_related('caja_banco', 'proveedor', 'pago_compra__orden_compra__proveedor', 'centro_costo', 'pago_compra__orden_compra__centro_costo').distinct().order_by('-fecha')

    lista_egresos = []
    total_egresos = Decimal('0.00')
    for eg in egresos:
        m = Decimal(str(eg.monto_mxn or eg.monto or 0))
        total_egresos += m

        prov_nombre = '--'
        if eg.proveedor:
            prov_nombre = eg.proveedor.razon_social
        elif eg.pago_compra and eg.pago_compra.orden_compra and eg.pago_compra.orden_compra.proveedor:
            prov_nombre = eg.pago_compra.orden_compra.proveedor.razon_social

        forma_pago_desc = eg.get_forma_pago_display() if hasattr(eg, 'get_forma_pago_display') else (eg.forma_pago or '--')
        eg_cc = eg.centro_costo or (eg.pago_compra.orden_compra.centro_costo if eg.pago_compra and eg.pago_compra.orden_compra else None) or cc

        # Solo mostrar el folio de la orden de compra si proviene de una OC
        concepto_display = '--'
        if eg.pago_compra and eg.pago_compra.orden_compra:
            concepto_display = f"OC-{eg.pago_compra.orden_compra.id:04d}"
        else:
            concepto_display = eg.concepto or '--'

        lista_egresos.append({
            'id': eg.id,
            'folio': f"EGR-{eg.id:04d}",
            'fecha': eg.fecha.strftime('%d/%m/%Y'),
            'concepto': concepto_display,
            'monto': float(m),
            'monto_mxn': float(m),
            'caja_banco': eg.caja_banco.nombre if eg.caja_banco else '--',
            'forma_pago': forma_pago_desc,
            'referencia': eg.referencia or '--',
            'proveedor': prov_nombre,
            'centro_costo': eg_cc.codigo if eg_cc else '--',
            'centro_costo_nombre': eg_cc.nombre if eg_cc else '--'
        })

    # 3. Órdenes de compra
    ordenes = OrdenCompra.objects.filter(
        centro_costo_id__in=centros_ids,
        empresa=empresa,
        fecha__year=anio,
        fecha__month=mes
    ).select_related('proveedor', 'centro_costo').order_by('-fecha')

    lista_oc = []
    total_oc = Decimal('0.00')
    total_comprometido_oc = Decimal('0.00')
    for oc in ordenes:
        oc_cc = oc.centro_costo or cc
        sub = oc.calcular_total or Decimal('0.00')
        total_oc += sub
        saldo = oc.saldo_pendiente
        if oc.estado in ['aprobada', 'recibida', 'parcial'] and saldo > 0:
            total_comprometido_oc += saldo * (oc.tipo_cambio or Decimal('1.0000'))

        lista_oc.append({
            'id': oc.id,
            'folio': f"OC-{oc.id:04d}",
            'fecha': oc.fecha.strftime('%d/%m/%Y'),
            'proveedor': oc.proveedor.razon_social if oc.proveedor else '--',
            'total': float(sub),
            'saldo_pendiente': float(saldo),
            'pago_estado': oc.pago_estado,
            'estado': oc.get_estado_display(),
            'centro_costo': oc_cc.codigo if oc_cc else '--',
            'centro_costo_nombre': oc_cc.nombre if oc_cc else '--'
        })

    # 4. Pedidos de venta
    pedidos = Pedido.objects.filter(
        centro_costo_id__in=centros_ids,
        empresa=empresa,
        fecha_creacion__year=anio,
        fecha_creacion__month=mes
    ).select_related('cliente', 'vendedor', 'centro_costo').order_by('-fecha_creacion')

    lista_pedidos = []
    total_pedidos = Decimal('0.00')
    total_saldo_pedidos = Decimal('0.00')
    for ped in pedidos:
        ped_cc = ped.centro_costo or cc
        tot = ped.total_pedido or Decimal('0.00')
        total_pedidos += tot
        saldo = ped.saldo_pendiente or Decimal('0.00')
        if ped.estado != 'cancelado':
            total_saldo_pedidos += saldo

        cliente_nom = '--'
        if ped.cliente:
            cliente_nom = ped.cliente.razon_social or ped.cliente.nombre_completo

        lista_pedidos.append({
            'id': ped.id,
            'folio': f"PED-{ped.id:04d}",
            'fecha': ped.fecha_creacion.strftime('%d/%m/%Y'),
            'cliente': cliente_nom,
            'estado': ped.get_estado_display(),
            'pago_estado': ped.pago_estado,
            'total': float(tot),
            'saldo_pendiente': float(saldo),
            'vendedor': (ped.vendedor.get_full_name() or ped.vendedor.username) if ped.vendedor else '--',
            'centro_costo': ped_cc.codigo if ped_cc else '--',
            'centro_costo_nombre': ped_cc.nombre if ped_cc else '--'
        })

    # 5. Ingresos de tesorería
    ingresos = Ingreso.objects.filter(
        Q(centro_costo_id__in=centros_ids) | Q(pago_pedido__pedido__centro_costo_id__in=centros_ids),
        empresa=empresa,
        estado='aplicado',
        fecha__year=anio,
        fecha__month=mes
    ).select_related('caja_banco', 'cliente', 'pago_pedido__pedido__cliente', 'centro_costo', 'pago_pedido__pedido__centro_costo').distinct().order_by('-fecha')

    lista_ingresos = []
    total_ingresos = Decimal('0.00')
    for ing in ingresos:
        m = Decimal(str(ing.monto_mxn or ing.monto or 0))
        total_ingresos += m

        cli_nom = '--'
        if ing.cliente:
            cli_nom = ing.cliente.razon_social or ing.cliente.nombre_completo
        elif ing.pago_pedido and ing.pago_pedido.pedido and ing.pago_pedido.pedido.cliente:
            cli_nom = ing.pago_pedido.pedido.cliente.razon_social or ing.pago_pedido.pedido.cliente.nombre_completo

        forma_pago_desc = ing.get_forma_pago_display() if hasattr(ing, 'get_forma_pago_display') else (ing.forma_pago or '--')
        ing_cc = ing.centro_costo or (ing.pago_pedido.pedido.centro_costo if ing.pago_pedido and ing.pago_pedido.pedido else None) or cc

        # Solo mostrar el folio del pedido si proviene de un pedido
        concepto_display = '--'
        if ing.pago_pedido and ing.pago_pedido.pedido:
            concepto_display = f"PED-{ing.pago_pedido.pedido.id:04d}"
        else:
            concepto_display = ing.concepto or '--'

        lista_ingresos.append({
            'id': ing.id,
            'folio': f"ING-{ing.id:05d}",
            'fecha': ing.fecha.strftime('%d/%m/%Y'),
            'concepto': concepto_display,
            'monto': float(m),
            'monto_mxn': float(m),
            'caja_banco': ing.caja_banco.nombre if ing.caja_banco else '--',
            'forma_pago': forma_pago_desc,
            'referencia': ing.referencia or '--',
            'cliente': cli_nom,
            'centro_costo': ing_cc.codigo if ing_cc else '--',
            'centro_costo_nombre': ing_cc.nombre if ing_cc else '--'
        })

    gran_total_gastado = total_egresos

    if consolidado:
        presupuesto = CentroCosto.objects.filter(id__in=centros_ids).aggregate(tot=Sum('presupuesto_mensual'))['tot'] or Decimal('0.00')
    else:
        presupuesto = cc.presupuesto_mensual or Decimal('0.00')

    remanente = max(Decimal('0.00'), presupuesto - gran_total_gastado - total_comprometido_oc)
    pct = (gran_total_gastado / presupuesto * Decimal('100.0')) if presupuesto > 0 else Decimal('0.0')
    pct_comprometido = ((gran_total_gastado + total_comprometido_oc) / presupuesto * Decimal('100.0')) if presupuesto > 0 else Decimal('0.0')

    # Operación de flujo real: total de ingresos menos total de egresos sin inflar sumando OCs ni Pedidos
    gasto_neto = total_egresos - total_ingresos
    disponible_calculado = presupuesto - gasto_neto

    return JsonResponse({
        'success': True,
        'es_padre': es_padre,
        'num_subcentros': len(subcentros_directos),
        'subcentros': [{'id': sc.id, 'codigo': sc.codigo, 'nombre': sc.nombre} for sc in subcentros_directos],
        'consolidado': consolidado,
        'centro': {
            'id': cc.id,
            'codigo': cc.codigo,
            'nombre': cc.nombre,
            'tipo': cc.get_tipo_display() if cc.tipo != 'departamento' else 'Departamento',
            'tipo_raw': cc.tipo,
            'sucursal': cc.sucursal.nombre if cc.sucursal else 'Todas',
            'almacen': cc.almacen.nombre if cc.almacen else '--',
            'responsable': (cc.responsable.get_full_name() or cc.responsable.username) if cc.responsable else '--',
            'fecha_inicio': cc.fecha_inicio.strftime('%d/%m/%Y') if cc.fecha_inicio else '--',
            'fecha_fin': cc.fecha_fin.strftime('%d/%m/%Y') if cc.fecha_fin else '--',
            'descripcion': cc.descripcion or '--',
            'presupuesto_mensual': float(presupuesto),
        },
        'periodo': {
            'anio': anio,
            'mes': mes,
        },
        'resumen': {
            'total_spu': float(total_spu),
            'total_salidas_ventas': float(total_salidas_ventas),
            'total_recepciones': float(total_recepciones),
            'total_entradas_piezas': sum(m['cantidad'] for m in lista_recepciones),
            'total_salidas_piezas': sum(m['cantidad'] for m in lista_salidas_totales),
            'total_entradas_count': len(lista_recepciones),
            'total_salidas_count': len(lista_salidas_totales),
            'total_egresos': float(total_egresos),
            'total_oc': float(total_oc),
            'total_comprometido': float(total_comprometido_oc),
            'total_gastado': float(gran_total_gastado),
            'consumo_total': float(gran_total_gastado),
            'total_pedidos': float(total_pedidos),
            'total_saldo_pedidos': float(total_saldo_pedidos),
            'total_ingresos': float(total_ingresos),
            'gasto_neto': float(gasto_neto),
            'impacto_neto': float(gasto_neto),
            'disponible_calculado': float(disponible_calculado),
            'balance_neto': float(total_ingresos - gran_total_gastado),
            'presupuesto': float(presupuesto),
            'remanente': float(remanente),
            'pct_consumido': round(float(pct), 1),
            'pct_total_con_comprometido': round(float(pct_comprometido), 1),
        },
        'pedidos': lista_pedidos,
        'ingresos': lista_ingresos,
        'ingresos_tesoreria': lista_ingresos,
        'salidas_almacen': lista_mercancia,
        'mercancia_almacen': lista_mercancia,
        'entradas_almacen': lista_recepciones,
        'salidas_almacen_solo': lista_salidas_totales,
        'salidas_por_uso': lista_spu,
        'recepciones_almacen': lista_recepciones,
        'egresos_tesoreria': lista_egresos,
        'egresos': lista_egresos,
        'ordenes_compra': lista_oc
    })
