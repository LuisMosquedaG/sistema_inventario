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
from .models import (
    CentroCosto, ClaseCosto, CicloDistribucion,
    SegmentoCicloDistribucion, EjecucionCicloDistribucion, DetalleEjecucionCiclo
)
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

    # Sembrar catálogo estándar de Clases de Costo si la empresa aún no tiene ninguna
    ClaseCosto.sembrar_catalogo_estandar(empresa)
    clases_costos = ClaseCosto.objects.filter(empresa=empresa).order_by('tipo', 'codigo')

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
        'clases_costos': clases_costos,
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
        control_presupuesto = data.get('control_presupuesto') or 'desactivado'
        tolerancia_presupuesto = Decimal(str(data.get('tolerancia_presupuesto') or 0))
        fecha_inicio = data.get('fecha_inicio') or None
        fecha_fin = data.get('fecha_fin') or None

        parent = None
        if parent_id:
            parent = CentroCosto.objects.filter(empresa=empresa, id=parent_id).first()
            if parent:
                prefijo = f"{parent.codigo}-"
                if not codigo.startswith(prefijo):
                    if codigo.startswith(parent.codigo):
                        resto = codigo[len(parent.codigo):].lstrip('-')
                        codigo = f"{parent.codigo}-{resto}"
                    else:
                        codigo = f"{prefijo}{codigo}"

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'El código y el nombre son obligatorios.'}, status=400)

        if CentroCosto.objects.filter(empresa=empresa, codigo=codigo).exists():
            return JsonResponse({'success': False, 'error': f'Ya existe un centro de costos con el código "{codigo}".'}, status=400)

        sucursal = None
        if sucursal_id:
            sucursal = Sucursal.objects.filter(empresa=empresa, id=sucursal_id).first()

        almacen = None
        if almacen_id:
            almacen = Almacen.objects.filter(empresa=empresa, id=almacen_id).first()

        responsable = None
        if responsable_id:
            responsable = User.objects.filter(id=responsable_id).first()

        activo = bool(data.get('activo', True))

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
            control_presupuesto=control_presupuesto,
            tolerancia_presupuesto=tolerancia_presupuesto,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            activo=activo
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
        'control_presupuesto': cc.control_presupuesto,
        'tolerancia_presupuesto': float(cc.tolerancia_presupuesto),
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
        control_presupuesto = data.get('control_presupuesto') or 'desactivado'
        tolerancia_presupuesto = Decimal(str(data.get('tolerancia_presupuesto') or 0))
        fecha_inicio = data.get('fecha_inicio') or None
        fecha_fin = data.get('fecha_fin') or None

        # Prevenir auto-referencia circular
        parent = None
        if parent_id:
            if int(parent_id) == cc.id:
                return JsonResponse({'success': False, 'error': 'Un centro de costo no puede ser padre de sí mismo.'}, status=400)
            parent = CentroCosto.objects.filter(empresa=empresa, id=parent_id).first()
            if parent:
                prefijo = f"{parent.codigo}-"
                if not codigo.startswith(prefijo):
                    if codigo.startswith(parent.codigo):
                        resto = codigo[len(parent.codigo):].lstrip('-')
                        codigo = f"{parent.codigo}-{resto}"
                    else:
                        codigo = f"{prefijo}{codigo}"

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'El código y el nombre son obligatorios.'}, status=400)

        if CentroCosto.objects.filter(empresa=empresa, codigo=codigo).exclude(id=cc.id).exists():
            return JsonResponse({'success': False, 'error': f'Ya existe otro centro de costos con el código "{codigo}".'}, status=400)

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
        cc.control_presupuesto = control_presupuesto
        cc.tolerancia_presupuesto = tolerancia_presupuesto
        cc.fecha_inicio = fecha_inicio
        cc.fecha_fin = fecha_fin
        if 'activo' in data:
            cc.activo = bool(data.get('activo'))
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
    ).select_related(
        'caja_banco', 'proveedor', 'pago_compra__orden_compra__proveedor',
        'centro_costo', 'pago_compra__orden_compra__centro_costo', 'clase_costo'
    ).prefetch_related(
        'pago_compra__orden_compra__detalles__clase_costo',
        'pago_compra__orden_compra__detalles__producto__clase_costo_predeterminada'
    ).distinct().order_by('-fecha')

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

        # Clase de costo (solo código)
        clase_desc = '--'
        if eg.clase_costo:
            clase_desc = eg.clase_costo.codigo
        elif eg.pago_compra and eg.pago_compra.orden_compra:
            clases_eg = set()
            for det in eg.pago_compra.orden_compra.detalles.all():
                cc_obj = det.clase_costo or getattr(det.producto, 'clase_costo_predeterminada', None)
                if cc_obj:
                    clases_eg.add(cc_obj.codigo)
            if clases_eg:
                clase_desc = ", ".join(sorted(clases_eg))

        lista_egresos.append({
            'id': eg.id,
            'folio': f"EGR-{eg.id:04d}",
            'fecha': eg.fecha.strftime('%d/%m/%Y'),
            'concepto': concepto_display,
            'clase_costo': clase_desc,
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
    ).select_related('proveedor', 'centro_costo').prefetch_related(
        'detalles__clase_costo',
        'detalles__producto__clase_costo_predeterminada'
    ).order_by('-fecha')

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

        # Clases de costo asociadas a las partidas de la OC (solo código)
        clases_oc = set()
        for det in oc.detalles.all():
            cc_obj = det.clase_costo or getattr(det.producto, 'clase_costo_predeterminada', None)
            if cc_obj:
                clases_oc.add(cc_obj.codigo)
        clases_oc_str = ", ".join(sorted(clases_oc)) if clases_oc else '--'

        lista_oc.append({
            'id': oc.id,
            'folio': f"OC-{oc.id:04d}",
            'fecha': oc.fecha.strftime('%d/%m/%Y'),
            'proveedor': oc.proveedor.razon_social if oc.proveedor else '--',
            'clase_costo': clases_oc_str,
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

    # 6. Distribuciones y Prorrateos (SAP Allocation / Assessment)
    # A) Como centro emisor (distribuciones realizadas hacia otros centros)
    ejecuciones_emitidas = EjecucionCicloDistribucion.objects.filter(
        ciclo__centro_emisor_id__in=centros_ids,
        empresa=empresa,
        anio=anio,
        mes=mes,
        estado='aplicado'
    ).select_related('ciclo', 'ciclo__centro_emisor', 'ciclo__clase_costo_secundaria', 'usuario').prefetch_related('detalles__centro_receptor')

    lista_distribuciones_emitidas = []
    total_distribuciones_emitidas = Decimal('0.00')
    for ejec in ejecuciones_emitidas:
        m = ejec.monto_total_distribuido
        total_distribuciones_emitidas += m
        receptores_str = ", ".join([f"{d.centro_receptor.codigo} ({d.porcentaje_aplicado}%)" for d in ejec.detalles.all()])
        clase_sec = ejec.ciclo.clase_costo_secundaria.codigo if ejec.ciclo.clase_costo_secundaria else '--'
        lista_distribuciones_emitidas.append({
            'id': ejec.id,
            'tipo': 'emitida',
            'tipo_label': 'Prorrateo Emitido (Crédito -)',
            'ciclo_codigo': ejec.ciclo.codigo,
            'ciclo_nombre': ejec.ciclo.nombre,
            'fecha': ejec.fecha_ejecucion.strftime('%d/%m/%Y %H:%M'),
            'centro_origen': ejec.ciclo.centro_emisor.codigo,
            'receptores': receptores_str,
            'clase_costo': clase_sec,
            'monto_base': float(ejec.monto_base_emisor),
            'monto': float(m),
            'usuario': (ejec.usuario.get_full_name() or ejec.usuario.username) if ejec.usuario else '--',
            'notas': ejec.notas or '--'
        })

    # B) Como centro receptor (distribuciones recibidas absorbidas de emisores)
    detalles_recibidos = DetalleEjecucionCiclo.objects.filter(
        centro_receptor_id__in=centros_ids,
        ejecucion__empresa=empresa,
        ejecucion__anio=anio,
        ejecucion__mes=mes,
        ejecucion__estado='aplicado'
    ).select_related('ejecucion', 'ejecucion__ciclo', 'ejecucion__ciclo__centro_emisor', 'ejecucion__ciclo__clase_costo_secundaria', 'centro_receptor')

    lista_distribuciones_recibidas = []
    total_distribuciones_recibidas = Decimal('0.00')
    for det in detalles_recibidos:
        m = det.monto_cargado
        total_distribuciones_recibidas += m
        clase_sec = det.ejecucion.ciclo.clase_costo_secundaria.codigo if det.ejecucion.ciclo.clase_costo_secundaria else '--'
        lista_distribuciones_recibidas.append({
            'id': det.id,
            'ejecucion_id': det.ejecucion.id,
            'tipo': 'recibida',
            'tipo_label': 'Prorrateo Recibido (Cargo +)',
            'ciclo_codigo': det.ejecucion.ciclo.codigo,
            'ciclo_nombre': det.ejecucion.ciclo.nombre,
            'fecha': det.ejecucion.fecha_ejecucion.strftime('%d/%m/%Y %H:%M'),
            'centro_origen': det.ejecucion.ciclo.centro_emisor.codigo,
            'centro_destino': det.centro_receptor.codigo,
            'porcentaje': float(det.porcentaje_aplicado),
            'clase_costo': clase_sec,
            'monto': float(m),
            'usuario': (det.ejecucion.usuario.get_full_name() or det.ejecucion.usuario.username) if det.ejecucion.usuario else '--',
            'notas': det.ejecucion.notas or '--'
        })

    todas_distribuciones = lista_distribuciones_recibidas + lista_distribuciones_emitidas

    gran_total_gastado = total_egresos + total_distribuciones_recibidas - total_distribuciones_emitidas

    if consolidado:
        presupuesto = CentroCosto.objects.filter(id__in=centros_ids).aggregate(tot=Sum('presupuesto_mensual'))['tot'] or Decimal('0.00')
    else:
        presupuesto = cc.presupuesto_mensual or Decimal('0.00')

    remanente = max(Decimal('0.00'), presupuesto - gran_total_gastado - total_comprometido_oc)
    pct = (gran_total_gastado / presupuesto * Decimal('100.0')) if presupuesto > 0 else Decimal('0.0')
    pct_comprometido = ((gran_total_gastado + total_comprometido_oc) / presupuesto * Decimal('100.0')) if presupuesto > 0 else Decimal('0.0')

    # Operación de flujo real considerando prorrateos
    gasto_neto = gran_total_gastado - total_ingresos
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
            'total_distribuciones_recibidas': float(total_distribuciones_recibidas),
            'total_distribuciones_emitidas': float(total_distribuciones_emitidas),
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
        'ordenes_compra': lista_oc,
        'distribuciones': todas_distribuciones,
        'distribuciones_recibidas': lista_distribuciones_recibidas,
        'distribuciones_emitidas': lista_distribuciones_emitidas
    })


@login_required(login_url='/login/')
def api_verificar_disponibilidad_centro(request, centro_id):
    """
    Endpoint para verificación dinámica de disponibilidad presupuestal (SAP AVC)
    utilizado en tiempo real por los formularios de Compras y Solicitudes.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    cc = get_object_or_404(CentroCosto, id=centro_id, empresa=empresa)
    monto_raw = request.GET.get('monto') or request.POST.get('monto') or 0
    orden_id = request.GET.get('orden_id') or request.POST.get('orden_id') or None
    try:
        monto_val = Decimal(str(monto_raw))
    except Exception:
        monto_val = Decimal('0.00')

    exclude_id = int(orden_id) if (orden_id and str(orden_id).isdigit()) else None
    val = cc.validar_disponibilidad(monto_nuevo=monto_val, exclude_orden_id=exclude_id)

    from preferencias.permissions import user_has_centros_costos_permission, is_admin_or_superuser
    puede_sobregirar = is_admin_or_superuser(request.user) or user_has_centros_costos_permission(request, 'centros_costos', 'autorizar_sobregiro')

    return JsonResponse({
        'success': True,
        'centro_id': cc.id,
        'codigo': cc.codigo,
        'nombre': cc.nombre,
        'puede_sobregirar': puede_sobregirar,
        'validacion': val
    })


# ==========================================
# GESTIÓN DE CLASES DE COSTO (COST ELEMENTS)
# ==========================================

@login_required(login_url='/login/')
def api_clases_costos_list(request):
    """Devuelve el catálogo de clases de costos activas para selectores en formato JSON."""
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    # Auto-sembrar si está vacío
    ClaseCosto.sembrar_catalogo_estandar(empresa)

    tipo_filtro = request.GET.get('tipo', '').strip()
    solo_activas = request.GET.get('activas', 'true').lower() == 'true'

    qs = ClaseCosto.objects.filter(empresa=empresa)
    if solo_activas:
        qs = qs.filter(activo=True)
    if tipo_filtro:
        qs = qs.filter(tipo=tipo_filtro)

    data = [{
        'id': c.id,
        'codigo': c.codigo,
        'nombre': c.nombre,
        'display': f"{c.codigo} - {c.nombre}",
        'tipo': c.tipo,
        'tipo_display': c.get_tipo_display(),
        'categoria': c.categoria,
        'categoria_display': c.get_categoria_display(),
        'descripcion': c.descripcion or '',
        'activo': c.activo,
    } for c in qs.order_by('codigo')]

    return JsonResponse({'success': True, 'clases': data})


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'crear', json_response=True)
def crear_clase_costo_ajax(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    codigo = (data.get('codigo') or '').strip().upper()
    nombre = (data.get('nombre') or '').strip()
    tipo = (data.get('tipo') or 'primaria').strip()
    categoria = (data.get('categoria') or 'materiales').strip()
    descripcion = (data.get('descripcion') or '').strip()

    if not codigo or not nombre:
        return JsonResponse({'success': False, 'error': 'El código y el nombre son obligatorios.'}, status=400)

    if ClaseCosto.objects.filter(empresa=empresa, codigo=codigo).exists():
        return JsonResponse({'success': False, 'error': f'Ya existe una clase de costo con el código {codigo}.'}, status=400)

    clase = ClaseCosto.objects.create(
        empresa=empresa,
        codigo=codigo,
        nombre=nombre,
        tipo=tipo,
        categoria=categoria,
        descripcion=descripcion,
        activo=True
    )

    return JsonResponse({
        'success': True,
        'message': f'Clase de costo {clase.codigo} creada correctamente.',
        'clase': {
            'id': clase.id,
            'codigo': clase.codigo,
            'nombre': clase.nombre,
            'tipo': clase.tipo,
            'categoria': clase.categoria,
            'activo': clase.activo
        }
    })


@login_required(login_url='/login/')
def obtener_clase_costo_json(request, clase_id):
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    clase = get_object_or_404(ClaseCosto, id=clase_id, empresa=empresa)
    return JsonResponse({
        'success': True,
        'clase': {
            'id': clase.id,
            'codigo': clase.codigo,
            'nombre': clase.nombre,
            'tipo': clase.tipo,
            'categoria': clase.categoria,
            'descripcion': clase.descripcion or '',
            'activo': clase.activo,
        }
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def actualizar_clase_costo_ajax(request, clase_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    clase = get_object_or_404(ClaseCosto, id=clase_id, empresa=empresa)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    codigo = (data.get('codigo') or '').strip().upper()
    nombre = (data.get('nombre') or '').strip()
    tipo = (data.get('tipo') or clase.tipo).strip()
    categoria = (data.get('categoria') or clase.categoria).strip()
    descripcion = (data.get('descripcion') or '').strip()

    if not codigo or not nombre:
        return JsonResponse({'success': False, 'error': 'El código y el nombre son obligatorios.'}, status=400)

    if ClaseCosto.objects.filter(empresa=empresa, codigo=codigo).exclude(id=clase.id).exists():
        return JsonResponse({'success': False, 'error': f'Ya existe otra clase de costo con el código {codigo}.'}, status=400)

    clase.codigo = codigo
    clase.nombre = nombre
    clase.tipo = tipo
    clase.categoria = categoria
    clase.descripcion = descripcion
    clase.save()

    return JsonResponse({
        'success': True,
        'message': f'Clase de costo {clase.codigo} actualizada correctamente.'
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def toggle_estado_clase_costo_ajax(request, clase_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    clase = get_object_or_404(ClaseCosto, id=clase_id, empresa=empresa)
    clase.activo = not clase.activo
    clase.save()

    return JsonResponse({
        'success': True,
        'nuevo_estado': clase.activo,
        'message': f'Clase de costo {"activada" if clase.activo else "desactivada"} exitosamente.'
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'eliminar', json_response=True)
def eliminar_clase_costo_ajax(request, clase_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    clase = get_object_or_404(ClaseCosto, id=clase_id, empresa=empresa)

    # Validar si tiene transacciones o productos asociados
    tiene_compras = clase.detalles_compras.exists()
    tiene_solicitudes = clase.detalles_solicitudes.exists()
    tiene_egresos = clase.egresos.exists()
    tiene_productos = clase.productos.exists()

    if tiene_compras or tiene_solicitudes or tiene_egresos or tiene_productos:
        return JsonResponse({
            'success': False,
            'error': 'No se puede eliminar esta clase de costo porque tiene compras, egresos o productos vinculados. En su lugar, puedes desactivarla.'
        }, status=400)

    codigo = clase.codigo
    clase.delete()

    return JsonResponse({
        'success': True,
        'message': f'Clase de costo {codigo} eliminada correctamente.'
    })


@login_required(login_url='/login/')
def restablecer_catalogo_estandar_clases_ajax(request):
    """Permite sembrar o completar las clases estándar recomendadas."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    # Forzar siembra de faltantes
    catalogo_base = [
        ('5101', 'Materia Prima e Insumos Directos', 'primaria', 'materiales', 'Consumo directo de insumos para la operación o producción'),
        ('5102', 'Refacciones y Repuestos', 'primaria', 'mantenimiento', 'Piezas de recambio y componentes para maquinaria y vehículos'),
        ('5103', 'Combustibles y Lubricantes', 'primaria', 'transporte', 'Gasolina, diésel, aceites y grasas automotrices/industriales'),
        ('5104', 'Fletes y Envíos', 'primaria', 'transporte', 'Transporte de mercancía y envíos por paquetería externa'),
        ('5105', 'Mantenimiento y Reparaciones Externas', 'primaria', 'mantenimiento', 'Servicios de reparación y mantenimiento contratados a terceros'),
        ('5106', 'Servicios Básicos (Luz, Agua, Gas)', 'primaria', 'instalaciones', 'Servicios públicos directos de las instalaciones'),
        ('5107', 'Comunicaciones e Internet', 'primaria', 'servicios', 'Telefonía, conectividad a internet y servicios de datos'),
        ('5108', 'Honorarios y Asesorías Profesionales', 'primaria', 'servicios', 'Consultoría legal, contable o técnica externa'),
        ('5109', 'Papelería y Artículos de Oficina', 'primaria', 'administrativo', 'Consumibles, impresiones y artículos administrativos'),
        ('5110', 'Viáticos y Gastos de Viaje', 'primaria', 'administrativo', 'Hospedaje, alimentos de viaje y traslados de personal'),
        ('5111', 'Herramientas Menores y Seguridad', 'primaria', 'materiales', 'EPP, uniformes y herramientas no capitalizables'),
        ('9101', 'Reparto Interno Servicios TI / Sistemas', 'secundaria', 'distribucion_interna', 'Liquidación mensual de costos de infraestructura y soporte TI'),
        ('9102', 'Absorción Mano de Obra Taller / Producción', 'secundaria', 'personal', 'Tarifas horarias aplicadas a órdenes de trabajo u operaciones'),
        ('9103', 'Sub-reparto Mantenimiento General', 'secundaria', 'distribucion_interna', 'Prorrateo de gastos del taller de mantenimiento a centros operativos'),
        ('9104', 'Distribución Gastos Corporativos y Renta', 'secundaria', 'distribucion_interna', 'Prorrateo de renta y gastos administrativos corporativos'),
    ]

    agregados = 0
    for codigo, nombre, tipo, cat, desc in catalogo_base:
        if not ClaseCosto.objects.filter(empresa=empresa, codigo=codigo).exists():
            ClaseCosto.objects.create(
                empresa=empresa,
                codigo=codigo,
                nombre=nombre,
                tipo=tipo,
                categoria=cat,
                descripcion=desc,
                activo=True
            )
            agregados += 1

    return JsonResponse({
        'success': True,
        'agregados': agregados,
        'message': f'Se agregaron {agregados} clases de costo estándar recomendadas.' if agregados > 0 else 'El catálogo estándar ya se encuentra completo.'
    })


# =========================================================================
# VISTAS AJAX: GESTIÓN DE CICLOS DE DISTRIBUCIÓN Y PRORRATEO (SAP ALLOCATION)
# =========================================================================

@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def listar_ciclos_distribucion_ajax(request):
    """Devuelve la lista de ciclos de distribución configurados con sus segmentos."""
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclos = CicloDistribucion.objects.filter(empresa=empresa).select_related(
        'centro_emisor', 'clase_costo_secundaria'
    ).prefetch_related('segmentos__centro_receptor', 'ejecuciones')

    resultado = []
    for c in ciclos:
        segmentos_data = []
        for s in c.segmentos.filter(activo=True):
            segmentos_data.append({
                'id': s.id,
                'centro_receptor_id': s.centro_receptor.id,
                'centro_receptor_codigo': s.centro_receptor.codigo,
                'centro_receptor_nombre': s.centro_receptor.nombre,
                'porcentaje': float(s.porcentaje),
                'monto_fijo': float(s.monto_fijo),
                'activo': s.activo
            })

        ult_ejec = c.ejecuciones.order_by('-fecha_ejecucion').first()
        ult_ejec_data = None
        if ult_ejec:
            ult_ejec_data = {
                'id': ult_ejec.id,
                'anio': ult_ejec.anio,
                'mes': ult_ejec.mes,
                'monto': float(ult_ejec.monto_total_distribuido),
                'estado': ult_ejec.estado,
                'fecha': ult_ejec.fecha_ejecucion.strftime('%d/%m/%Y %H:%M')
            }

        resultado.append({
            'id': c.id,
            'codigo': c.codigo,
            'nombre': c.nombre,
            'descripcion': c.descripcion or '',
            'metodo': c.metodo,
            'metodo_label': c.get_metodo_display(),
            'activo': c.activo,
            'centro_emisor': {
                'id': c.centro_emisor.id,
                'codigo': c.centro_emisor.codigo,
                'nombre': c.centro_emisor.nombre,
            },
            'clase_costo_secundaria': {
                'id': c.clase_costo_secundaria.id if c.clase_costo_secundaria else None,
                'codigo': c.clase_costo_secundaria.codigo if c.clase_costo_secundaria else '--',
                'nombre': c.clase_costo_secundaria.nombre if c.clase_costo_secundaria else '--',
            } if c.clase_costo_secundaria else None,
            'total_porcentaje': float(c.total_porcentaje),
            'num_receptores': len(segmentos_data),
            'segmentos': segmentos_data,
            'ultima_ejecucion': ult_ejec_data
        })

    return JsonResponse({'success': True, 'ciclos': resultado})


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'crear', json_response=True)
def guardar_ciclo_distribucion_ajax(request):
    """Crea o actualiza un ciclo de distribución junto con sus segmentos receptores."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    try:
        data = json.loads(request.body)
        ciclo_id = data.get('id')
        codigo = (data.get('codigo') or '').strip().upper()
        nombre = (data.get('nombre') or '').strip()
        descripcion = (data.get('descripcion') or '').strip()
        emisor_id = data.get('centro_emisor_id')
        clase_sec_id = data.get('clase_costo_secundaria_id')
        metodo = data.get('metodo') or 'porcentaje_fijo'
        activo = bool(data.get('activo', True))
        segmentos_input = data.get('segmentos', [])

        if not codigo or not nombre:
            return JsonResponse({'success': False, 'error': 'El código y el nombre del ciclo son obligatorios.'}, status=400)

        if not emisor_id:
            return JsonResponse({'success': False, 'error': 'Debe seleccionar un centro de costo emisor (origen).'}, status=400)

        emisor = get_object_or_404(CentroCosto, id=emisor_id, empresa=empresa)

        # Validar unicidad de código
        qs_cod = CicloDistribucion.objects.filter(empresa=empresa, codigo=codigo)
        if ciclo_id:
            qs_cod = qs_cod.exclude(id=ciclo_id)
        if qs_cod.exists():
            return JsonResponse({'success': False, 'error': f'Ya existe un ciclo con el código "{codigo}".'}, status=400)

        # Validar clase secundaria
        clase_sec = None
        if clase_sec_id:
            clase_sec = ClaseCosto.objects.filter(id=clase_sec_id, empresa=empresa).first()

        # Validar receptores
        if not segmentos_input:
            return JsonResponse({'success': False, 'error': 'Debe agregar al menos un centro receptor al ciclo.'}, status=400)

        suma_pct = Decimal('0.00')
        receptores_vistos = set()
        segmentos_validados = []

        for seg in segmentos_input:
            rec_id = seg.get('centro_receptor_id')
            if not rec_id:
                continue
            rec_id = int(rec_id)
            if rec_id == emisor.id:
                return JsonResponse({'success': False, 'error': f'El centro emisor [{emisor.codigo}] no puede ser receptor de su propio ciclo.'}, status=400)
            if rec_id in receptores_vistos:
                return JsonResponse({'success': False, 'error': 'No puede duplicar centros receptores en el mismo ciclo.'}, status=400)
            receptores_vistos.add(rec_id)

            rec_obj = CentroCosto.objects.filter(id=rec_id, empresa=empresa).first()
            if not rec_obj:
                continue

            pct = Decimal(str(seg.get('porcentaje') or 0))
            monto_f = Decimal(str(seg.get('monto_fijo') or 0))
            suma_pct += pct
            segmentos_validados.append({
                'centro': rec_obj,
                'porcentaje': pct,
                'monto_fijo': monto_f
            })

        if metodo == 'porcentaje_fijo':
            if abs(suma_pct - Decimal('100.00')) > Decimal('0.01'):
                return JsonResponse({
                    'success': False,
                    'error': f'La suma de los porcentajes de los receptores debe ser exactamente 100.00% (Suma actual: {suma_pct:.2f}%).'
                }, status=400)

        # Guardar ciclo
        if ciclo_id:
            ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)
            ciclo.codigo = codigo
            ciclo.nombre = nombre
            ciclo.descripcion = descripcion
            ciclo.centro_emisor = emisor
            ciclo.clase_costo_secundaria = clase_sec
            ciclo.metodo = metodo
            ciclo.activo = activo
            ciclo.save()
        else:
            ciclo = CicloDistribucion.objects.create(
                empresa=empresa,
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion,
                centro_emisor=emisor,
                clase_costo_secundaria=clase_sec,
                metodo=metodo,
                activo=activo
            )

        # Reemplazar segmentos
        ciclo.segmentos.all().delete()
        for sv in segmentos_validados:
            SegmentoCicloDistribucion.objects.create(
                ciclo=ciclo,
                centro_receptor=sv['centro'],
                porcentaje=sv['porcentaje'],
                monto_fijo=sv['monto_fijo'],
                activo=True
            )

        return JsonResponse({
            'success': True,
            'message': f'Ciclo de distribución "{ciclo.codigo} - {ciclo.nombre}" guardado correctamente.',
            'id': ciclo.id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al guardar ciclo: {str(e)}'}, status=400)


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'eliminar', json_response=True)
def eliminar_ciclo_distribucion_ajax(request, ciclo_id):
    """Elimina un ciclo de distribución si no tiene ejecuciones históricas aplicadas."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)

    if ciclo.ejecuciones.filter(estado='aplicado').exists():
        return JsonResponse({
            'success': False,
            'error': 'No se puede eliminar este ciclo porque tiene ejecuciones activas aplicadas en el historial. Primero revierta las ejecuciones o desactive el ciclo.'
        }, status=400)

    codigo = ciclo.codigo
    ciclo.delete()

    return JsonResponse({
        'success': True,
        'message': f'Ciclo de distribución {codigo} eliminado correctamente.'
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def simular_ejecucion_ciclo_ajax(request, ciclo_id):
    """
    Calcula una vista previa del prorrateo para un periodo (año y mes) dado:
    determina el gasto neto acumulado en el centro emisor y calcula cuánto recibiría cada receptor.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)

    now = timezone.now()
    anio = int(request.GET.get('anio', now.year))
    mes = int(request.GET.get('mes', now.month))

    # Verificar si ya existe una ejecución aplicada en ese periodo
    ya_ejecutado = ciclo.ejecuciones.filter(anio=anio, mes=mes, estado='aplicado').first()

    # Monto base: Gasto directo neto del emisor en el mes (Egresos - Ingresos)
    emisor = ciclo.centro_emisor
    egresos_emisor = emisor.calcular_egresos_mes(anio, mes)
    ingresos_emisor = emisor.calcular_ingresos_mes(anio, mes)
    # Gasto real acumulado del emisor
    gasto_base_emisor = max(Decimal('0.00'), egresos_emisor - ingresos_emisor)

    # Permitir monto manual si el usuario lo especifica o usar el gasto base
    monto_override = request.GET.get('monto')
    if monto_override is not None and monto_override != '':
        try:
            monto_distribuir = Decimal(str(monto_override))
        except Exception:
            monto_distribuir = gasto_base_emisor
    else:
        monto_distribuir = gasto_base_emisor

    # Calcular reparto por segmento
    segmentos_simulacion = []
    total_calculado = Decimal('0.00')

    for seg in ciclo.segmentos.filter(activo=True):
        if ciclo.metodo == 'porcentaje_fijo':
            monto_seg = (monto_distribuir * (seg.porcentaje / Decimal('100.00'))).quantize(Decimal('0.01'))
        else:
            monto_seg = seg.monto_fijo

        total_calculado += monto_seg
        segmentos_simulacion.append({
            'centro_id': seg.centro_receptor.id,
            'codigo': seg.centro_receptor.codigo,
            'nombre': seg.centro_receptor.nombre,
            'porcentaje': float(seg.porcentaje),
            'monto_cargado': float(monto_seg)
        })

    return JsonResponse({
        'success': True,
        'ciclo': {
            'id': ciclo.id,
            'codigo': ciclo.codigo,
            'nombre': ciclo.nombre,
            'metodo': ciclo.metodo,
            'emisor_codigo': emisor.codigo,
            'emisor_nombre': emisor.nombre,
            'clase_costo_secundaria': ciclo.clase_costo_secundaria.codigo if ciclo.clase_costo_secundaria else '--'
        },
        'periodo': {'anio': anio, 'mes': mes},
        'ya_ejecutado': bool(ya_ejecutado),
        'ejecucion_previa_id': ya_ejecutado.id if ya_ejecutado else None,
        'gasto_base_emisor': float(gasto_base_emisor),
        'monto_a_distribuir': float(monto_distribuir),
        'total_prorrateado': float(total_calculado),
        'detalles': segmentos_simulacion
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'crear', json_response=True)
def ejecutar_ciclo_distribucion_ajax(request, ciclo_id):
    """
    Aplica formalmente el prorrateo del ciclo en el periodo seleccionado.
    Genera el registro histórico EjecucionCicloDistribucion y los DetalleEjecucionCiclo.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)

    try:
        data = json.loads(request.body)
        anio = int(data.get('anio'))
        mes = int(data.get('mes'))
        monto_distribuir_in = data.get('monto')
        notas = (data.get('notas') or '').strip()

        # Validar si ya hay una ejecución aplicada para este ciclo y periodo
        existente = ciclo.ejecuciones.filter(anio=anio, mes=mes, estado='aplicado').first()
        if existente:
            return JsonResponse({
                'success': False,
                'error': f'El ciclo "{ciclo.codigo}" ya fue ejecutado para el periodo {mes:02d}/{anio}. Si desea re-ejecutarlo, primero revierta la ejecución anterior.'
            }, status=400)

        emisor = ciclo.centro_emisor
        if monto_distribuir_in is not None and monto_distribuir_in != '':
            monto_distribuir = Decimal(str(monto_distribuir_in))
        else:
            egresos_emisor = emisor.calcular_egresos_mes(anio, mes)
            ingresos_emisor = emisor.calcular_ingresos_mes(anio, mes)
            monto_distribuir = max(Decimal('0.00'), egresos_emisor - ingresos_emisor)

        if monto_distribuir <= 0:
            return JsonResponse({
                'success': False,
                'error': 'El monto a distribuir debe ser mayor a cero. El centro emisor no cuenta con gastos acumulados en este periodo.'
            }, status=400)

        # Crear ejecución
        ejecucion = EjecucionCicloDistribucion.objects.create(
            ciclo=ciclo,
            empresa=empresa,
            anio=anio,
            mes=mes,
            usuario=request.user,
            monto_base_emisor=monto_distribuir,
            monto_total_distribuido=monto_distribuir,
            estado='aplicado',
            notas=notas
        )

        total_asignado = Decimal('0.00')
        segmentos = list(ciclo.segmentos.filter(activo=True))
        for seg in segmentos:
            if ciclo.metodo == 'porcentaje_fijo':
                monto_seg = (monto_distribuir * (seg.porcentaje / Decimal('100.00'))).quantize(Decimal('0.01'))
            else:
                monto_seg = seg.monto_fijo

            total_asignado += monto_seg
            DetalleEjecucionCiclo.objects.create(
                ejecucion=ejecucion,
                centro_receptor=seg.centro_receptor,
                porcentaje_aplicado=seg.porcentaje,
                monto_cargado=monto_seg
            )

        ejecucion.monto_total_distribuido = total_asignado
        ejecucion.save(update_fields=['monto_total_distribuido'])

        return JsonResponse({
            'success': True,
            'message': f'Prorrateo del ciclo "{ciclo.codigo}" ejecutado exitosamente por ${total_asignado:,.2f} MXN para el periodo {mes:02d}/{anio}.',
            'ejecucion_id': ejecucion.id
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al ejecutar prorrateo: {str(e)}'}, status=400)


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def revertir_ejecucion_ciclo_ajax(request, ejecucion_id):
    """
    Revierte una ejecución aplicada de distribución, cancelando su impacto financiero en los centros.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ejecucion = get_object_or_404(EjecucionCicloDistribucion, id=ejecucion_id, empresa=empresa)

    if ejecucion.estado == 'revertido':
        return JsonResponse({'success': False, 'error': 'Esta ejecución ya se encuentra revertida.'}, status=400)

    motivo = ''
    try:
        data = json.loads(request.body)
        motivo = (data.get('motivo') or '').strip()
    except Exception:
        pass

    ejecucion.estado = 'revertido'
    ejecucion.fecha_reversion = timezone.now()
    ejecucion.usuario_reversion = request.user
    ejecucion.motivo_reversion = motivo
    ejecucion.save(update_fields=['estado', 'fecha_reversion', 'usuario_reversion', 'motivo_reversion'])

    return JsonResponse({
        'success': True,
        'message': f'La ejecución del periodo {ejecucion.mes:02d}/{ejecucion.anio} fue revertida correctamente.'
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def historial_ejecuciones_distribucion_ajax(request):
    """Devuelve el historial global de prorrateos ejecutados y revertidos en la empresa."""
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ejecuciones = EjecucionCicloDistribucion.objects.filter(empresa=empresa).select_related(
        'ciclo', 'ciclo__centro_emisor', 'usuario', 'usuario_reversion'
    ).prefetch_related('detalles__centro_receptor').order_by('-fecha_ejecucion')[:50]

    resultado = []
    for ej in ejecuciones:
        detalles_data = []
        for d in ej.detalles.all():
            detalles_data.append({
                'centro_receptor_codigo': d.centro_receptor.codigo,
                'centro_receptor_nombre': d.centro_receptor.nombre,
                'porcentaje': float(d.porcentaje_aplicado),
                'monto': float(d.monto_cargado)
            })

        resultado.append({
            'id': ej.id,
            'ciclo_id': ej.ciclo.id,
            'ciclo_codigo': ej.ciclo.codigo,
            'ciclo_nombre': ej.ciclo.nombre,
            'emisor_codigo': ej.ciclo.centro_emisor.codigo,
            'emisor_nombre': ej.ciclo.centro_emisor.nombre,
            'periodo': f"{ej.mes:02d}/{ej.anio}",
            'anio': ej.anio,
            'mes': ej.mes,
            'fecha_ejecucion': ej.fecha_ejecucion.strftime('%d/%m/%Y %H:%M'),
            'usuario': (ej.usuario.get_full_name() or ej.usuario.username) if ej.usuario else '--',
            'monto_total': float(ej.monto_total_distribuido),
            'estado': ej.estado,
            'estado_label': ej.get_estado_display(),
            'notas': ej.notas or '',
            'fecha_reversion': ej.fecha_reversion.strftime('%d/%m/%Y %H:%M') if ej.fecha_reversion else None,
            'usuario_reversion': (ej.usuario_reversion.get_full_name() or ej.usuario_reversion.username) if ej.usuario_reversion else None,
            'motivo_reversion': ej.motivo_reversion or '',
            'detalles': detalles_data
        })

    return JsonResponse({'success': True, 'historial': resultado})


