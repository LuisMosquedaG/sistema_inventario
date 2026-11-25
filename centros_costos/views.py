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
        gastado = c.calcular_gastos_mes(anio_actual, mes_actual)
        egresos_mes = c.calcular_egresos_mes(anio_actual, mes_actual)
        ingresos_mes = c.calcular_ingresos_mes(anio_actual, mes_actual)
        comprometido = c.calcular_comprometido_mes(anio_actual, mes_actual)
        
        # Porcentaje sobre presupuesto mensual
        pres = c.presupuesto_mensual or Decimal('0.00')
        pct = Decimal('0.0')
        pct_total = Decimal('0.0')
        if pres > 0:
            pct = (gastado / pres) * Decimal('100.0')
            pct_total = ((gastado + comprometido) / pres) * Decimal('100.0')

        gasto_global_mes += gastado
        remanente = pres - gastado

        # Alerta si supera 80% o está excedido
        if pres > 0 and (pct >= 80 or pct_total >= 80):
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
    anio_param = request.GET.get('anio')
    mes_param = request.GET.get('mes')

    MESES_MAP = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    if str(anio_param).lower() in ['0', 'todos', 'all']:
        anio = None
    else:
        try:
            anio = int(anio_param) if anio_param is not None and anio_param != '' else now.year
        except (ValueError, TypeError):
            anio = now.year

    if str(mes_param).lower() in ['0', 'todos', 'all']:
        mes = None
    else:
        try:
            mes = int(mes_param) if mes_param is not None and mes_param != '' else now.month
        except (ValueError, TypeError):
            mes = now.month

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
    filtro_rec = Q(orden_compra__centro_costo_id__in=centros_ids, empresa=empresa)
    if anio:
        filtro_rec &= Q(fecha__year=anio)
    if mes:
        filtro_rec &= Q(fecha__month=mes)

    recepciones = Recepcion.objects.filter(filtro_rec).select_related(
        'almacen', 'orden_compra', 'orden_compra__proveedor', 'orden_compra__centro_costo',
        'moneda', 'orden_compra__moneda'
    ).prefetch_related('detalles__producto').order_by('-fecha')

    lista_recepciones = []
    total_recepciones = Decimal('0.00')
    for rec in recepciones:
        oc_cc = (rec.orden_compra.centro_costo if rec.orden_compra else None) or cc
        cc_codigo = oc_cc.codigo if oc_cc else '--'
        cc_nombre = oc_cc.nombre if oc_cc else '--'
        rec_tc = rec.tipo_cambio or (rec.orden_compra.tipo_cambio if rec.orden_compra else Decimal('1.0000')) or Decimal('1.0000')
        rec_moneda = (rec.moneda.siglas if rec.moneda else (rec.orden_compra.moneda.siglas if rec.orden_compra and rec.orden_compra.moneda else 'MXN'))

        for det in rec.detalles.all():
            costo_total_orig = Decimal(str(det.total or det.subtotal or 0))
            costo_unitario_orig = Decimal(str(det.costo_unitario or 0))
            costo_total_mxn = costo_total_orig * rec_tc
            costo_unitario_mxn = costo_unitario_orig * rec_tc
            total_recepciones += costo_total_mxn

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
                'costo_unitario': float(costo_unitario_mxn),
                'subtotal': float(costo_total_mxn),
                'costo_unitario_origen': float(costo_unitario_orig),
                'subtotal_origen': float(costo_total_orig),
                'moneda': rec_moneda,
                'tipo_cambio': float(rec_tc),
                'estado': rec.get_estado_display() if hasattr(rec, 'get_estado_display') else rec.estado,
                'centro_costo': cc_codigo,
                'centro_costo_nombre': cc_nombre
            })

    # 1.B. SALIDAS: Salidas internas de almacén por uso / consumo
    filtro_spu = (Q(centro_costo_id__in=centros_ids) | Q(salida__centro_costo_id__in=centros_ids, centro_costo__isnull=True)) & Q(salida__empresa=empresa)
    if anio and mes:
        filtro_spu &= (Q(salida__fecha_salida__year=anio, salida__fecha_salida__month=mes) | Q(salida__fecha_salida__isnull=True, salida__fecha_creacion__year=anio, salida__fecha_creacion__month=mes))
    elif anio:
        filtro_spu &= (Q(salida__fecha_salida__year=anio) | Q(salida__fecha_salida__isnull=True, salida__fecha_creacion__year=anio))
    elif mes:
        filtro_spu &= (Q(salida__fecha_salida__month=mes) | Q(salida__fecha_salida__isnull=True, salida__fecha_creacion__month=mes))

    spu_detalles = DetalleSalidaPorUso.objects.filter(filtro_spu).exclude(salida__estado='cancelada').select_related(
        'salida', 'producto', 'salida__usuario_recibe', 'salida__almacen', 'centro_costo', 'salida__centro_costo'
    ).order_by('-salida__fecha_creacion')

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
    filtro_ov = Q(pedido_origen__centro_costo_id__in=centros_ids, empresa=empresa)
    if anio and mes:
        filtro_ov &= (Q(fecha_surtido__year=anio, fecha_surtido__month=mes) | Q(fecha_surtido__isnull=True, fecha_creacion__year=anio, fecha_creacion__month=mes))
    elif anio:
        filtro_ov &= (Q(fecha_surtido__year=anio) | Q(fecha_surtido__isnull=True, fecha_creacion__year=anio))
    elif mes:
        filtro_ov &= (Q(fecha_surtido__month=mes) | Q(fecha_surtido__isnull=True, fecha_creacion__month=mes))

    ordenes_venta = OrdenVenta.objects.filter(filtro_ov).exclude(estado='cancelada').select_related(
        'almacen', 'pedido_origen', 'cliente', 'pedido_origen__centro_costo'
    ).prefetch_related('detalles__producto').order_by('-fecha_creacion')

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

    # 1.D. PRODUCTOS Y SERVICIOS EN PEDIDOS DE VENTA (Pendientes de surtido / Comprometidos)
    # Refleja de inmediato los productos solicitados en pedidos del centro de costo que aún no han generado una Orden de Venta
    pedidos_con_ov_ids = OrdenVenta.objects.filter(
        pedido_origen__centro_costo_id__in=centros_ids,
        empresa=empresa
    ).exclude(estado='cancelada').values_list('pedido_origen_id', flat=True)

    filtro_ped_comp = Q(centro_costo_id__in=centros_ids, empresa=empresa)
    if anio:
        filtro_ped_comp &= Q(fecha_creacion__year=anio)
    if mes:
        filtro_ped_comp &= Q(fecha_creacion__month=mes)

    pedidos_pendientes_qs = Pedido.objects.filter(filtro_ped_comp).exclude(estado='cancelado').exclude(
        id__in=pedidos_con_ov_ids
    ).select_related('cliente', 'sucursal', 'centro_costo', 'moneda').prefetch_related('detalles__producto').order_by('-fecha_creacion')

    lista_pedidos_comprometidos = []
    total_pedidos_comprometidos = Decimal('0.00')
    for ped in pedidos_pendientes_qs:
        f_ped = ped.fecha_creacion.date() if hasattr(ped.fecha_creacion, 'date') else ped.fecha_creacion
        ped_cc = ped.centro_costo or cc
        tc_ped = ped.tipo_cambio or Decimal('1.0000')
        cli_nom = ped.cliente.nombre_completo if ped.cliente else '--'

        for det in ped.detalles.all():
            cant = det.cantidad_solicitada or Decimal('0.00')
            prec_orig = det.precio_unitario or Decimal('0.00')
            prec_mxn = prec_orig * tc_ped
            sub_orig = det.subtotal or (cant * prec_orig)
            sub_mxn = sub_orig * tc_ped
            total_pedidos_comprometidos += sub_mxn

            lista_pedidos_comprometidos.append({
                'tipo': 'pedido_comprometido',
                'movimiento': 'salida',
                'tipo_label': f"Comprometido ({ped.get_estado_display()})",
                'folio': f"PED-{ped.id:04d}",
                'doc_origen': 'Pedido de Venta',
                'fecha': f_ped.strftime('%d/%m/%Y'),
                'fecha_dt': f_ped,
                'almacen': ped.sucursal.nombre if ped.sucursal else '--',
                'recibe': cli_nom,
                'producto': det.producto.nombre,
                'cantidad': float(cant),
                'unidad': getattr(det.producto, 'unidad_medida', 'pza') or 'pza',
                'costo_unitario': float(prec_mxn),
                'subtotal': float(sub_mxn),
                'costo_unitario_origen': float(prec_orig),
                'subtotal_origen': float(sub_orig),
                'moneda': ped.moneda.siglas if ped.moneda else 'MXN',
                'tipo_cambio': float(tc_ped),
                'estado': ped.get_estado_display(),
                'centro_costo': ped_cc.codigo if ped_cc else '--',
                'centro_costo_nombre': ped_cc.nombre if ped_cc else '--'
            })

    # Combinamos todas las entradas y salidas de mercancía
    lista_salidas_totales = lista_spu + lista_salidas_ventas + lista_pedidos_comprometidos
    lista_mercancia = lista_recepciones + lista_salidas_totales
    lista_mercancia.sort(key=lambda x: x['fecha_dt'], reverse=True)
    for item in lista_mercancia:
        item.pop('fecha_dt', None)

    # 2. Egresos de tesorería
    filtro_egr = (Q(centro_costo_id__in=centros_ids) | Q(pago_compra__orden_compra__centro_costo_id__in=centros_ids)) & Q(empresa=empresa, estado='aplicado')
    if anio:
        filtro_egr &= Q(fecha__year=anio)
    if mes:
        filtro_egr &= Q(fecha__month=mes)

    egresos = Egreso.objects.filter(filtro_egr).select_related(
        'caja_banco', 'proveedor', 'pago_compra__orden_compra__proveedor',
        'centro_costo', 'pago_compra__orden_compra__centro_costo', 'clase_costo', 'moneda'
    ).prefetch_related(
        'pago_compra__orden_compra__detalles__clase_costo',
        'pago_compra__orden_compra__detalles__producto__clase_costo_predeterminada'
    ).distinct().order_by('-fecha')

    lista_egresos = []
    total_egresos = Decimal('0.00')
    for eg in egresos:
        m_mxn = eg.monto_mxn if (eg.monto_mxn and eg.monto_mxn > 0) else (eg.monto * (eg.tipo_cambio or Decimal('1.0000')))
        total_egresos += m_mxn

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
            'monto': float(m_mxn),
            'monto_mxn': float(m_mxn),
            'monto_origen': float(eg.monto),
            'moneda': eg.moneda.siglas if eg.moneda else 'MXN',
            'tipo_cambio': float(eg.tipo_cambio or 1.0),
            'caja_banco': eg.caja_banco.nombre if eg.caja_banco else '--',
            'forma_pago': forma_pago_desc,
            'referencia': eg.referencia or '--',
            'proveedor': prov_nombre,
            'centro_costo': eg_cc.codigo if eg_cc else '--',
            'centro_costo_nombre': eg_cc.nombre if eg_cc else '--'
        })

    # 3. Órdenes de compra
    filtro_oc = Q(centro_costo_id__in=centros_ids, empresa=empresa)
    if anio:
        filtro_oc &= Q(fecha__year=anio)
    if mes:
        filtro_oc &= Q(fecha__month=mes)

    ordenes = OrdenCompra.objects.filter(filtro_oc).select_related('proveedor', 'centro_costo', 'moneda').prefetch_related(
        'detalles__clase_costo',
        'detalles__producto__clase_costo_predeterminada'
    ).order_by('-fecha')

    lista_oc = []
    total_oc = Decimal('0.00')
    total_comprometido_oc = Decimal('0.00')
    for oc in ordenes:
        oc_cc = oc.centro_costo or cc
        tc = oc.tipo_cambio or Decimal('1.0000')
        sub = oc.calcular_total or Decimal('0.00')
        sub_mxn = sub * tc
        total_oc += sub_mxn

        saldo = oc.saldo_pendiente or Decimal('0.00')
        saldo_mxn = saldo * tc
        if oc.estado in ['aprobada', 'recibida', 'parcial'] and saldo > 0:
            total_comprometido_oc += saldo_mxn

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
            'total': float(sub_mxn),
            'total_origen': float(sub),
            'saldo_pendiente': float(saldo_mxn),
            'saldo_pendiente_origen': float(saldo),
            'moneda': oc.moneda.siglas if oc.moneda else 'MXN',
            'tipo_cambio': float(tc),
            'pago_estado': oc.pago_estado,
            'estado': oc.get_estado_display(),
            'centro_costo': oc_cc.codigo if oc_cc else '--',
            'centro_costo_nombre': oc_cc.nombre if oc_cc else '--'
        })

    # 4. Pedidos de venta
    filtro_ped = Q(centro_costo_id__in=centros_ids, empresa=empresa)
    if anio:
        filtro_ped &= Q(fecha_creacion__year=anio)
    if mes:
        filtro_ped &= Q(fecha_creacion__month=mes)

    pedidos = Pedido.objects.filter(filtro_ped).select_related('cliente', 'vendedor', 'centro_costo', 'moneda').order_by('-fecha_creacion')

    lista_pedidos = []
    total_pedidos = Decimal('0.00')
    total_saldo_pedidos = Decimal('0.00')
    for ped in pedidos:
        ped_cc = ped.centro_costo or cc
        tc = ped.tipo_cambio or Decimal('1.0000')
        tot = ped.total_pedido or Decimal('0.00')
        tot_mxn = tot * tc
        total_pedidos += tot_mxn

        saldo = ped.saldo_pendiente or Decimal('0.00')
        saldo_mxn = saldo * tc
        if ped.estado != 'cancelado':
            total_saldo_pedidos += saldo_mxn

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
            'total': float(tot_mxn),
            'total_origen': float(tot),
            'saldo_pendiente': float(saldo_mxn),
            'saldo_pendiente_origen': float(saldo),
            'moneda': ped.moneda.siglas if ped.moneda else 'MXN',
            'tipo_cambio': float(tc),
            'vendedor': (ped.vendedor.get_full_name() or ped.vendedor.username) if ped.vendedor else '--',
            'centro_costo': ped_cc.codigo if ped_cc else '--',
            'centro_costo_nombre': ped_cc.nombre if ped_cc else '--'
        })

    # 5. Ingresos de tesorería
    filtro_ing = (Q(centro_costo_id__in=centros_ids) | Q(pago_pedido__pedido__centro_costo_id__in=centros_ids)) & Q(empresa=empresa, estado='aplicado')
    if anio:
        filtro_ing &= Q(fecha__year=anio)
    if mes:
        filtro_ing &= Q(fecha__month=mes)

    ingresos = Ingreso.objects.filter(filtro_ing).select_related(
        'caja_banco', 'cliente', 'pago_pedido__pedido__cliente', 'centro_costo', 'pago_pedido__pedido__centro_costo', 'moneda'
    ).distinct().order_by('-fecha')

    lista_ingresos = []
    total_ingresos = Decimal('0.00')
    for ing in ingresos:
        m_mxn = ing.monto_mxn if (ing.monto_mxn and ing.monto_mxn > 0) else (ing.monto * (ing.tipo_cambio or Decimal('1.0000')))
        total_ingresos += m_mxn

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
            'monto': float(m_mxn),
            'monto_mxn': float(m_mxn),
            'monto_origen': float(ing.monto),
            'moneda': ing.moneda.siglas if ing.moneda else 'MXN',
            'tipo_cambio': float(ing.tipo_cambio or 1.0),
            'caja_banco': ing.caja_banco.nombre if ing.caja_banco else '--',
            'forma_pago': forma_pago_desc,
            'referencia': ing.referencia or '--',
            'cliente': cli_nom,
            'centro_costo': ing_cc.codigo if ing_cc else '--',
            'centro_costo_nombre': ing_cc.nombre if ing_cc else '--'
        })

    # 6. Distribuciones y Prorrateos (SAP Allocation / Assessment)
    # A) Como centro emisor (distribuciones realizadas hacia otros centros)
    filtro_ejec_em = Q(ciclo__centro_emisor_id__in=centros_ids, empresa=empresa, estado='aplicado')
    if anio:
        filtro_ejec_em &= Q(anio=anio)
    if mes:
        filtro_ejec_em &= Q(mes=mes)

    ejecuciones_emitidas = EjecucionCicloDistribucion.objects.filter(filtro_ejec_em).select_related(
        'ciclo', 'ciclo__centro_emisor', 'ciclo__clase_costo_secundaria', 'usuario'
    ).prefetch_related('detalles__centro_receptor')

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
    filtro_ejec_rec = Q(centro_receptor_id__in=centros_ids, ejecucion__empresa=empresa, ejecucion__estado='aplicado')
    if anio:
        filtro_ejec_rec &= Q(ejecucion__anio=anio)
    if mes:
        filtro_ejec_rec &= Q(ejecucion__mes=mes)

    detalles_recibidos = DetalleEjecucionCiclo.objects.filter(filtro_ejec_rec).select_related(
        'ejecucion', 'ejecucion__ciclo', 'ejecucion__ciclo__centro_emisor', 'ejecucion__ciclo__clase_costo_secundaria', 'centro_receptor'
    )

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
            'anio': anio if anio else 'Todos',
            'mes': mes if mes else 'Todos',
            'mes_nombre': MESES_MAP.get(mes, 'Todos los meses') if mes else 'Todos los meses',
            'filtro_modo': 'mes' if (anio and mes) else ('anio' if anio else 'historico')
        },
        'resumen': {
            'total_spu': float(total_spu),
            'total_salidas_ventas': float(total_salidas_ventas),
            'total_pedidos_comprometidos': float(total_pedidos_comprometidos),
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
            'pedidos_pendientes_cobro': len([p for p in pedidos if (p.saldo_pendiente or 0) > 0 and p.estado != 'cancelado']),
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
    tipo_cambio_raw = request.GET.get('tipo_cambio') or request.POST.get('tipo_cambio') or 1
    orden_id = request.GET.get('orden_id') or request.POST.get('orden_id') or None
    try:
        monto_val = Decimal(str(monto_raw)) * Decimal(str(tipo_cambio_raw or 1))
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
    """
    Elimina un ciclo de distribución.
    Si tiene ejecuciones de prorrateo aplicadas, las revierte automáticamente
    deshaciendo los prorrateos aplicados en los centros de costo antes de eliminar el ciclo.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)

    # Revertir automáticamente cualquier ejecución aplicada
    ejecuciones_aplicadas = ciclo.ejecuciones.filter(estado='aplicado')
    count_revertidas = 0
    now = timezone.now()
    for ej in ejecuciones_aplicadas:
        ej.estado = 'revertido'
        ej.fecha_reversion = now
        ej.usuario_reversion = request.user
        ej.motivo_reversion = f'Reversión automática por eliminación del ciclo {ciclo.codigo}'
        ej.save(update_fields=['estado', 'fecha_reversion', 'usuario_reversion', 'motivo_reversion'])
        count_revertidas += 1

    codigo = ciclo.codigo
    ciclo.delete()

    msg = f'Ciclo de distribución "{codigo}" eliminado correctamente.'
    if count_revertidas > 0:
        msg += f' Se deshicieron {count_revertidas} prorrateo(s) previamente aplicado(s), restaurando los saldos de los centros.'

    return JsonResponse({
        'success': True,
        'message': msg
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def simular_ejecucion_ciclo_ajax(request, ciclo_id):
    """
    Calcula una vista previa del prorrateo para un periodo (año y mes) dado.
    Detecta de forma inteligente los comprobantes aplicados en ciclos anteriores y determina
    únicamente el saldo y comprobantes pendientes (movimientos posteriores) para evitar duplicar montos.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)

    now = timezone.now()
    anio = int(request.GET.get('anio', now.year))
    mes = int(request.GET.get('mes', now.month))

    emisor = ciclo.centro_emisor
    # Analizar comprobantes del emisor en el periodo
    analisis = emisor.obtener_estado_prorrateo_mes(anio, mes)

    # Verificar si este ciclo específico ya tiene ejecuciones aplicadas
    ejecucion_este_ciclo = ciclo.ejecuciones.filter(anio=anio, mes=mes, estado='aplicado').first()

    from centros_costos.models import PeriodoContable
    periodo_cerrado = PeriodoContable.esta_cerrado(empresa, anio, mes)

    # El monto base sugerido es exclusivamente el saldo de movimientos posteriores no prorrateados
    gasto_base_emisor = Decimal(str(analisis['total_pendiente']))

    # Permitir monto manual si el usuario lo especifica o usar el saldo posterior no prorrateado
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
        'ya_ejecutado': bool(ejecucion_este_ciclo),
        'ejecucion_previa_id': ejecucion_este_ciclo.id if ejecucion_este_ciclo else None,
        'gasto_total_mes': analisis['total_egresos_mes'],
        'monto_ya_prorrateado': analisis['monto_ya_prorrateado'],
        'gasto_base_emisor': float(gasto_base_emisor),
        'monto_a_distribuir': float(monto_distribuir),
        'total_prorrateado': float(total_calculado),
        'detalles': segmentos_simulacion,
        'comprobantes_pendientes': analisis['comprobantes_pendientes'],
        'comprobantes_prorrateados': analisis['comprobantes_prorrateados'],
        'cant_pendientes': analisis['cant_pendientes'],
        'cant_prorrateados': analisis['cant_prorrateados'],
        'ejecuciones_previas': analisis['ejecuciones_previas'],
        'tiene_pendientes': analisis['tiene_pendientes'],
        'todos_prorrateados': analisis['todos_prorrateados'],
        'periodo_cerrado': bool(periodo_cerrado)
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'crear', json_response=True)
def ejecutar_ciclo_distribucion_ajax(request, ciclo_id):
    """
    Aplica formalmente el prorrateo del ciclo en el periodo seleccionado.
    Detecta los comprobantes aplicados en ciclos previos e incluye exclusivamente
    los comprobantes y movimientos posteriores para evitar duplicar montos.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    ciclo = get_object_or_404(CicloDistribucion, id=ciclo_id, empresa=empresa)
    emisor = ciclo.centro_emisor

    try:
        data = json.loads(request.body)
        anio = int(data.get('anio'))
        mes = int(data.get('mes'))
        monto_distribuir_in = data.get('monto')
        notas = (data.get('notas') or '').strip()

        # Validar si el periodo contable se encuentra cerrado
        from centros_costos.models import PeriodoContable
        if PeriodoContable.esta_cerrado(empresa, anio, mes):
            return JsonResponse({
                'success': False,
                'error': f'El periodo {mes:02d}/{anio} se encuentra CERRADO. No se pueden aplicar prorrateos mientras permanezca cerrado. Si requiere realizar ajustes, primero reabra el periodo.'
            }, status=400)

        # Analizar comprobantes del centro emisor en el mes
        analisis = emisor.obtener_estado_prorrateo_mes(anio, mes)

        # Si ya se prorrateó todo y no hay nuevos comprobantes pendientes
        if analisis['todos_prorrateados'] or (analisis['total_pendiente'] <= 0 and not monto_distribuir_in):
            return JsonResponse({
                'success': False,
                'error': f'Todos los comprobantes del centro emisor [{emisor.codigo}] para el periodo {mes:02d}/{anio} ya fueron aplicados en ciclos previos (${analisis["monto_ya_prorrateado"]:,.2f} MXN). No existen movimientos posteriores pendientes para prorratear.'
            }, status=400)

        # Determinar monto a prorratear (usa el saldo pendiente posterior si no se fuerza manualmente)
        if monto_distribuir_in is not None and monto_distribuir_in != '':
            monto_distribuir = Decimal(str(monto_distribuir_in))
        else:
            monto_distribuir = Decimal(str(analisis['total_pendiente']))

        if monto_distribuir <= 0:
            return JsonResponse({
                'success': False,
                'error': 'El monto a distribuir debe ser mayor a cero. No hay saldo pendiente de prorratear para este periodo.'
            }, status=400)

        # Crear ejecución
        ejecucion = EjecucionCicloDistribucion.objects.create(
            ciclo=ciclo,
            empresa=empresa,
            anio=anio,
            mes=mes,
            usuario=request.user,
            monto_base_emisor=Decimal(str(analisis['total_egresos_mes'])),
            monto_total_distribuido=monto_distribuir,
            estado='aplicado',
            notas=notas
        )

        # Asociar los comprobantes posteriores que se absorben en este ciclo
        from tesoreria.models import Egreso
        ids_pendientes = [c['id'] for c in analisis['comprobantes_pendientes']]
        if ids_pendientes:
            egresos_a_vincular = Egreso.objects.filter(id__in=ids_pendientes)
            ejecucion.comprobantes_egresos.set(egresos_a_vincular)

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

        cant_comprobantes = len(ids_pendientes)
        es_adicional = analisis['monto_ya_prorrateado'] > 0
        tipo_ejec_txt = "complementario (movimientos posteriores)" if es_adicional else "de periodo"

        return JsonResponse({
            'success': True,
            'message': f'Prorrateo {tipo_ejec_txt} del ciclo "{ciclo.codigo}" ejecutado exitosamente por ${total_asignado:,.2f} MXN ({cant_comprobantes} comprobantes) para el periodo {mes:02d}/{anio}.',
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

    from centros_costos.models import PeriodoContable
    if PeriodoContable.esta_cerrado(empresa, ejecucion.anio, ejecucion.mes):
        return JsonResponse({
            'success': False,
            'error': f'El periodo {ejecucion.mes:02d}/{ejecucion.anio} se encuentra CERRADO. No se pueden revertir prorrateos en periodos contables cerrados.'
        }, status=400)

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


# ===================================================================================
# CIERRE DE PERIODOS CONTABLES Y MENSUALES
# ===================================================================================

@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def api_resumen_periodo_contable(request):
    """
    Devuelve las métricas consolidadas y el estado de cierre de un periodo (año y mes) específico.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    now = timezone.now()
    anio = int(request.GET.get('anio', now.year))
    mes = int(request.GET.get('mes', now.month))

    from centros_costos.models import PeriodoContable, EjecucionCicloDistribucion, CentroCosto
    from tesoreria.models import Egreso

    periodo_obj = PeriodoContable.objects.filter(empresa=empresa, anio=anio, mes=mes).select_related(
        'usuario_cierre', 'usuario_reapertura'
    ).first()

    esta_cerrado = periodo_obj.estado == 'cerrado' if periodo_obj else False

    # Métricas del mes
    egresos_qs = Egreso.objects.filter(
        empresa=empresa,
        estado='aplicado',
        fecha__year=anio,
        fecha__month=mes
    ).select_related('moneda')
    total_egresos = sum([Decimal(str(e.monto_mxn if (e.monto_mxn and e.monto_mxn > 0) else (e.monto * (e.tipo_cambio or Decimal('1.0000'))))) for e in egresos_qs], Decimal('0.00'))

    ejecuciones_qs = EjecucionCicloDistribucion.objects.filter(
        empresa=empresa,
        anio=anio,
        mes=mes,
        estado='aplicado'
    )
    total_prorrateado = sum([Decimal(str(ej.monto_total_distribuido or 0)) for ej in ejecuciones_qs], Decimal('0.00'))

    # Centros emisores con remanente sin prorratear
    emisores_pendientes = []
    centros_emisores = CentroCosto.objects.filter(empresa=empresa, activo=True, ciclos_como_emisor__isnull=False).distinct()
    for emisor in centros_emisores:
        st = emisor.obtener_estado_prorrateo_mes(anio, mes)
        if st['tiene_pendientes']:
            emisores_pendientes.append({
                'codigo': emisor.codigo,
                'nombre': emisor.nombre,
                'pendiente': st['total_pendiente'],
                'cant_comprobantes': st['cant_pendientes']
            })

    info_auditoria = None
    if periodo_obj:
        info_auditoria = {
            'estado': periodo_obj.estado,
            'estado_label': periodo_obj.get_estado_display(),
            'fecha_cierre': periodo_obj.fecha_cierre.strftime('%d/%m/%Y %H:%M') if periodo_obj.fecha_cierre else None,
            'usuario_cierre': (periodo_obj.usuario_cierre.get_full_name() or periodo_obj.usuario_cierre.username) if periodo_obj.usuario_cierre else None,
            'notas_cierre': periodo_obj.notas_cierre or '',
            'fecha_reapertura': periodo_obj.fecha_reapertura.strftime('%d/%m/%Y %H:%M') if periodo_obj.fecha_reapertura else None,
            'usuario_reapertura': (periodo_obj.usuario_reapertura.get_full_name() or periodo_obj.usuario_reapertura.username) if periodo_obj.usuario_reapertura else None,
            'motivo_reapertura': periodo_obj.motivo_reapertura or '',
        }

    # Línea de tiempo de movimientos y seguimiento del periodo
    historial_seguimiento = []
    if periodo_obj and periodo_obj.fecha_cierre and periodo_obj.estado == 'cerrado':
        historial_seguimiento.append({
            'tipo': 'cierre',
            'tipo_label': 'Periodo Cerrado',
            'icono': 'bi-lock-fill',
            'color': 'cancelada',
            'fecha': periodo_obj.fecha_cierre.strftime('%d/%m/%Y %H:%M'),
            'fecha_raw': periodo_obj.fecha_cierre,
            'usuario': (periodo_obj.usuario_cierre.get_full_name() or periodo_obj.usuario_cierre.username) if periodo_obj.usuario_cierre else 'Sistema',
            'detalle': periodo_obj.notas_cierre or 'Cierre formal de periodo mensual.'
        })

    if periodo_obj and periodo_obj.fecha_reapertura:
        historial_seguimiento.append({
            'tipo': 'reapertura',
            'tipo_label': 'Periodo Reabierto',
            'icono': 'bi-unlock-fill',
            'color': 'parcial',
            'fecha': periodo_obj.fecha_reapertura.strftime('%d/%m/%Y %H:%M'),
            'fecha_raw': periodo_obj.fecha_reapertura,
            'usuario': (periodo_obj.usuario_reapertura.get_full_name() or periodo_obj.usuario_reapertura.username) if periodo_obj.usuario_reapertura else 'Sistema',
            'detalle': periodo_obj.motivo_reapertura or 'Reapertura para ajustes contables.'
        })

    ejecuciones_todas = EjecucionCicloDistribucion.objects.filter(
        empresa=empresa,
        anio=anio,
        mes=mes
    ).select_related('ciclo', 'usuario', 'usuario_reversion')

    for ej in ejecuciones_todas:
        if ej.fecha_ejecucion:
            historial_seguimiento.append({
                'tipo': 'prorrateo_ejecutado',
                'tipo_label': f'Prorrateo {ej.ciclo.codigo}',
                'icono': 'bi-play-circle-fill',
                'color': 'recibida',
                'fecha': ej.fecha_ejecucion.strftime('%d/%m/%Y %H:%M'),
                'fecha_raw': ej.fecha_ejecucion,
                'usuario': (ej.usuario.get_full_name() or ej.usuario.username) if ej.usuario else '--',
                'detalle': f'Prorrateo de ${ej.monto_total_distribuido:,.2f} MXN aplicado a centros receptores.'
            })
        if ej.estado == 'revertido' and ej.fecha_reversion:
            historial_seguimiento.append({
                'tipo': 'prorrateo_revertido',
                'tipo_label': f'Reversión {ej.ciclo.codigo}',
                'icono': 'bi-arrow-counterclockwise',
                'color': 'cancelada',
                'fecha': ej.fecha_reversion.strftime('%d/%m/%Y %H:%M'),
                'fecha_raw': ej.fecha_reversion,
                'usuario': (ej.usuario_reversion.get_full_name() or ej.usuario_reversion.username) if ej.usuario_reversion else '--',
                'detalle': f'Reversión de prorrateo: {ej.motivo_reversion or "Sin motivo especificado."}'
            })

    historial_seguimiento.sort(key=lambda x: x['fecha_raw'], reverse=True)
    for h in historial_seguimiento:
        h.pop('fecha_raw', None)

    return JsonResponse({
        'success': True,
        'periodo': {'anio': anio, 'mes': mes},
        'esta_cerrado': esta_cerrado,
        'info_auditoria': info_auditoria,
        'historial': historial_seguimiento,
        'metricas': {
            'total_egresos': float(total_egresos),
            'total_prorrateado': float(total_prorrateado),
            'cant_egresos': egresos_qs.count(),
            'cant_ejecuciones': ejecuciones_qs.count(),
            'emisores_pendientes': emisores_pendientes,
            'tiene_pendientes': len(emisores_pendientes) > 0
        }
    })


@login_required(login_url='/login/')
def api_cerrar_periodo_contable(request):
    """
    Cierra formalmente un periodo contable/mensual para la empresa.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    from preferencias.permissions import is_admin_or_superuser, user_has_centros_costos_permission
    puede_cerrar = is_admin_or_superuser(request.user) or user_has_centros_costos_permission(request, 'centros_costos', 'cerrar_periodo')
    if not puede_cerrar:
        return JsonResponse({'success': False, 'error': 'No cuenta con permisos para cerrar periodos contables.'}, status=403)

    try:
        data = json.loads(request.body)
        anio = int(data.get('anio'))
        mes = int(data.get('mes'))
        notas = (data.get('notas') or '').strip()

        from centros_costos.models import PeriodoContable
        periodo_obj, created = PeriodoContable.objects.get_or_create(
            empresa=empresa,
            anio=anio,
            mes=mes,
            defaults={'estado': 'abierto'}
        )

        if periodo_obj.estado == 'cerrado':
            return JsonResponse({'success': False, 'error': f'El periodo {mes:02d}/{anio} ya se encuentra cerrado.'}, status=400)

        periodo_obj.estado = 'cerrado'
        periodo_obj.fecha_cierre = timezone.now()
        periodo_obj.usuario_cierre = request.user
        periodo_obj.notas_cierre = notas
        periodo_obj.save(update_fields=['estado', 'fecha_cierre', 'usuario_cierre', 'notas_cierre'])

        return JsonResponse({
            'success': True,
            'message': f'El periodo {mes:02d}/{anio} ha sido CERRADO exitosamente. Quedan bloqueadas las imputaciones y cancelaciones en este mes.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al cerrar periodo: {str(e)}'}, status=400)


@login_required(login_url='/login/')
def api_reabrir_periodo_contable(request):
    """
    Reabre un periodo contable previamente cerrado, requiriendo motivo de reapertura.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    from preferencias.permissions import is_admin_or_superuser, user_has_centros_costos_permission
    puede_reabrir = is_admin_or_superuser(request.user) or user_has_centros_costos_permission(request, 'centros_costos', 'cerrar_periodo')
    if not puede_reabrir:
        return JsonResponse({'success': False, 'error': 'No cuenta con permisos para reabrir periodos contables.'}, status=403)

    try:
        data = json.loads(request.body)
        anio = int(data.get('anio'))
        mes = int(data.get('mes'))
        motivo = (data.get('motivo') or '').strip()

        if not motivo:
            return JsonResponse({'success': False, 'error': 'Debe ingresar el motivo de reapertura del periodo.'}, status=400)

        from centros_costos.models import PeriodoContable
        periodo_obj = PeriodoContable.objects.filter(empresa=empresa, anio=anio, mes=mes).first()

        if not periodo_obj or periodo_obj.estado == 'abierto':
            return JsonResponse({'success': False, 'error': f'El periodo {mes:02d}/{anio} ya se encuentra abierto.'}, status=400)

        periodo_obj.estado = 'abierto'
        periodo_obj.fecha_reapertura = timezone.now()
        periodo_obj.usuario_reapertura = request.user
        periodo_obj.motivo_reapertura = motivo
        periodo_obj.save(update_fields=['estado', 'fecha_reapertura', 'usuario_reapertura', 'motivo_reapertura'])

        return JsonResponse({
            'success': True,
            'message': f'El periodo {mes:02d}/{anio} ha sido REABIERTO exitosamente.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al reabrir periodo: {str(e)}'}, status=400)


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def api_historial_periodos_contables(request):
    """
    Devuelve la matriz de estado de los 12 meses para el año consultado.
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    now = timezone.now()
    anio = int(request.GET.get('anio', now.year))

    from centros_costos.models import PeriodoContable
    periodos = {p.mes: p for p in PeriodoContable.objects.filter(empresa=empresa, anio=anio).select_related('usuario_cierre', 'usuario_reapertura')}

    nombres_meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    matriz = []
    for mes_idx in range(1, 13):
        p = periodos.get(mes_idx)
        esta_cerrado = p.estado == 'cerrado' if p else False
        matriz.append({
            'mes': mes_idx,
            'nombre': nombres_meses[mes_idx - 1],
            'anio': anio,
            'estado': 'cerrado' if esta_cerrado else 'abierto',
            'esta_cerrado': esta_cerrado,
            'fecha_cierre': p.fecha_cierre.strftime('%d/%m/%Y %H:%M') if p and p.fecha_cierre else None,
            'usuario_cierre': (p.usuario_cierre.get_full_name() or p.usuario_cierre.username) if p and p.usuario_cierre else None,
            'notas_cierre': p.notas_cierre if p else '',
            'fecha_reapertura': p.fecha_reapertura.strftime('%d/%m/%Y %H:%M') if p and p.fecha_reapertura else None,
            'usuario_reapertura': (p.usuario_reapertura.get_full_name() or p.usuario_reapertura.username) if p and p.usuario_reapertura else None,
        })

    return JsonResponse({'success': True, 'anio': anio, 'periodos': matriz})


# ==============================================================================
# ASIGNACIÓN DE DOCUMENTOS (OC / PEDIDOS) AL CENTRO DE COSTOS
# ==============================================================================

@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'ver', json_response=True)
def api_documentos_sin_centro_costo(request):
    """
    Devuelve las órdenes de compra o pedidos de venta que no tienen
    un Centro de Costos asignado (centro_costo__isnull=True).
    """
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    tipo = (request.GET.get('tipo') or 'orden_compra').strip().lower()
    q = request.GET.get('q', '').strip()

    documentos = []

    if tipo in ['orden_compra', 'oc', 'compras']:
        ocs = OrdenCompra.objects.filter(
            empresa=empresa,
            centro_costo__isnull=True
        ).exclude(estado='cancelada').select_related('proveedor', 'moneda').order_by('-fecha', '-id')

        if q:
            clean_q = q.replace('OC-', '').replace('oc-', '').strip()
            ocs = ocs.filter(
                Q(id__icontains=clean_q) |
                Q(proveedor__razon_social__icontains=q) |
                Q(proveedor__rfc__icontains=q)
            )

        for oc in ocs[:150]:
            tc = oc.tipo_cambio or Decimal('1.0000')
            tot = oc.total or Decimal('0.00')
            tot_mxn = oc.total_en_pesos if hasattr(oc, 'total_en_pesos') else (tot * tc)
            mon_siglas = oc.moneda.siglas if oc.moneda else 'MXN'
            prov_nom = oc.proveedor.razon_social if oc.proveedor else 'Sin proveedor'

            documentos.append({
                'id': oc.id,
                'folio': f"OC-{oc.id:04d}",
                'fecha': oc.fecha.strftime('%d/%m/%Y'),
                'beneficiario': prov_nom,
                'total': float(tot),
                'total_mxn': float(tot_mxn),
                'moneda': mon_siglas,
                'tipo_cambio': float(tc),
                'estado': oc.get_estado_display(),
                'pago_estado': oc.pago_estado,
                'items_count': oc.cantidad_items,
            })

    elif tipo in ['pedido', 'pedidos', 'ventas']:
        peds = Pedido.objects.filter(
            empresa=empresa,
            centro_costo__isnull=True
        ).exclude(estado='cancelado').select_related('cliente', 'moneda').order_by('-fecha_creacion', '-id')

        if q:
            clean_q = q.replace('PED-', '').replace('ped-', '').strip()
            peds = peds.filter(
                Q(id__icontains=clean_q) |
                Q(cliente__nombre__icontains=q) |
                Q(cliente__apellidos__icontains=q) |
                Q(cliente__razon_social__icontains=q) |
                Q(cliente__rfc__icontains=q)
            )

        for ped in peds[:150]:
            tc = ped.tipo_cambio or Decimal('1.0000')
            tot = ped.total_pedido or Decimal('0.00')
            tot_mxn = ped.total_en_pesos if hasattr(ped, 'total_en_pesos') else (tot * tc)
            mon_siglas = ped.moneda.siglas if ped.moneda else 'MXN'
            cli_nom = ped.cliente.nombre_completo if ped.cliente else 'Sin cliente'

            documentos.append({
                'id': ped.id,
                'folio': f"PED-{ped.id:04d}",
                'fecha': ped.fecha_creacion.strftime('%d/%m/%Y'),
                'beneficiario': cli_nom,
                'total': float(tot),
                'total_mxn': float(tot_mxn),
                'moneda': mon_siglas,
                'tipo_cambio': float(tc),
                'estado': ped.get_estado_display(),
                'pago_estado': ped.pago_estado,
                'items_count': ped.detalles.count(),
            })

    count_oc = OrdenCompra.objects.filter(empresa=empresa, centro_costo__isnull=True).exclude(estado='cancelada').count()
    count_ped = Pedido.objects.filter(empresa=empresa, centro_costo__isnull=True).exclude(estado='cancelado').count()

    return JsonResponse({
        'success': True,
        'tipo': tipo,
        'count_oc': count_oc,
        'count_ped': count_ped,
        'documentos': documentos
    })


@login_required(login_url='/login/')
@require_centros_costos_permission('centros_costos', 'editar', json_response=True)
def api_asignar_documento_centro_costo(request):
    """
    Asigna una o varias Órdenes de Compra o Pedidos sin centro de costos a un Centro de Costos,
    vinculando automáticamente todos los registros y movimientos contables asociados (Egresos o Ingresos).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=400)

    try:
        from django.db import transaction
        from centros_costos.models import PeriodoContable
        from compras.models import HistorialOrdenCompra

        data = json.loads(request.body)
        centro_costo_id = data.get('centro_costo_id')
        tipo = (data.get('tipo') or '').strip().lower()
        
        # Soportar asignación individual o múltiple
        documento_ids = data.get('documento_ids')
        if not documento_ids and data.get('documento_id'):
            documento_ids = [data.get('documento_id')]

        if not centro_costo_id or not tipo or not documento_ids:
            return JsonResponse({'success': False, 'error': 'Parámetros incompletos para la asignación.'}, status=400)

        cc = get_object_or_404(CentroCosto, id=centro_costo_id, empresa=empresa)

        if not cc.activo:
            return JsonResponse({'success': False, 'error': 'El centro de costos seleccionado no se encuentra activo.'}, status=400)

        folios_asignados = []
        total_movimientos_vinculados = 0

        with transaction.atomic():
            if tipo in ['orden_compra', 'oc', 'compras']:
                ocs = OrdenCompra.objects.filter(id__in=documento_ids, empresa=empresa)
                if not ocs.exists():
                    return JsonResponse({'success': False, 'error': 'No se encontraron las órdenes de compra solicitadas.'}, status=404)

                for oc in ocs:
                    # Validar que el periodo contable no esté cerrado
                    valido_per, err_per = PeriodoContable.validar_fecha_no_cerrada(empresa, oc.fecha)
                    if not valido_per:
                        return JsonResponse({'success': False, 'error': f"No se puede asignar OC-{oc.id:04d}: {err_per}"}, status=400)

                    # Asignar centro de costos a la OC
                    oc.centro_costo = cc
                    oc.save(update_fields=['centro_costo'])

                    # Asignar centro de costos a todos los egresos vinculados a sus pagos
                    egresos_actualizados = Egreso.objects.filter(
                        pago_compra__orden_compra=oc,
                        empresa=empresa
                    ).update(centro_costo=cc)

                    total_movimientos_vinculados += egresos_actualizados
                    folios_asignados.append(f"OC-{oc.id:04d}")

                    # Registrar en historial
                    HistorialOrdenCompra.objects.create(
                        orden_compra=oc,
                        usuario=request.user,
                        accion='edicion',
                        comentario=f"Asignado al Centro de Costos: {cc.codigo} - {cc.nombre}. Egresos vinculados: {egresos_actualizados}"
                    )

                msg = f"Se asignaron exitosamente {len(folios_asignados)} Orden(es) de Compra ({', '.join(folios_asignados)}) y {total_movimientos_vinculados} egreso(s) de tesorería al Centro de Costos {cc.codigo}."

            elif tipo in ['pedido', 'pedidos', 'ventas']:
                peds = Pedido.objects.filter(id__in=documento_ids, empresa=empresa)
                if not peds.exists():
                    return JsonResponse({'success': False, 'error': 'No se encontraron los pedidos solicitados.'}, status=404)

                for ped in peds:
                    # Validar que el periodo contable no esté cerrado
                    f_ped = ped.fecha_creacion.date() if hasattr(ped.fecha_creacion, 'date') else ped.fecha_creacion
                    valido_per, err_per = PeriodoContable.validar_fecha_no_cerrada(empresa, f_ped)
                    if not valido_per:
                        return JsonResponse({'success': False, 'error': f"No se puede asignar PED-{ped.id:04d}: {err_per}"}, status=400)

                    # Asignar centro de costos al Pedido
                    ped.centro_costo = cc
                    ped.save(update_fields=['centro_costo'])

                    # Asignar centro de costos a todos los ingresos vinculados a sus pagos
                    ingresos_actualizados = Ingreso.objects.filter(
                        pago_pedido__pedido=ped,
                        empresa=empresa
                    ).update(centro_costo=cc)

                    total_movimientos_vinculados += ingresos_actualizados
                    folios_asignados.append(f"PED-{ped.id:04d}")

                msg = f"Se asignaron exitosamente {len(folios_asignados)} Pedido(s) ({', '.join(folios_asignados)}) y {total_movimientos_vinculados} ingreso(s) de tesorería al Centro de Costos {cc.codigo}."

            else:
                return JsonResponse({'success': False, 'error': f"Tipo de documento '{tipo}' no soportado."}, status=400)

        return JsonResponse({
            'success': True,
            'message': msg,
            'folios': folios_asignados,
            'movimientos_vinculados': total_movimientos_vinculados,
            'centro_id': cc.id,
            'centro_codigo': cc.codigo,
            'centro_nombre': cc.nombre
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



