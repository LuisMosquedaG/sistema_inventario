from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from django.http import JsonResponse
from cotizaciones.models import Cotizacion
from pedidos.models import Pedido
from ventas.models import OrdenVenta
from compras.models import OrdenCompra
from recepciones.models import Recepcion
from produccion.models import OrdenProduccion
from tesoreria.models import PagoPedido, PagoCompra
from clientes.models import Cliente
from decimal import Decimal
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
def dashboard_inicio(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Extraer nombre antes del @
    username_display = request.user.username.split('@')[0] if '@' in request.user.username else request.user.username

    # --- DATOS PARA GRÁFICAS: VENTAS ---
    stats_cotizaciones = list(Cotizacion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))
    stats_pedidos = list(Pedido.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))
    stats_salidas = list(OrdenVenta.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))
    
    # Conteos específicos por tipo para clientes ACTIVOS
    stats_clientes = [
        {'tipo': 'prospecto', 'total': Cliente.objects.filter(empresa=empresa_actual, estado='activo', tipo='prospecto').count()},
        {'tipo': 'nuevo', 'total': Cliente.objects.filter(empresa=empresa_actual, estado='activo', tipo='cliente_nuevo').count()},
        {'tipo': 'activo', 'total': Cliente.objects.filter(empresa=empresa_actual, estado='activo', tipo='cliente_activo').count()},
        {'tipo': 'inactivo', 'total': Cliente.objects.filter(empresa=empresa_actual, estado='activo', tipo='cliente_inactivo').count()},
        {'tipo': 'vip', 'total': Cliente.objects.filter(empresa=empresa_actual, estado='activo', tipo='vip').count()},
    ]

    # MONTO DE COBROS (VENTAS)
    pedidos_activos = Pedido.objects.filter(empresa=empresa_actual).exclude(estado='cancelado')
    # Total vendido (MXN)
    total_vendido = pedidos_activos.aggregate(
        total=Sum(F('detalles__cantidad_solicitada') * F('detalles__precio_unitario'))
    )['total'] or Decimal('0.00')
    # Total cobrado (MXN) - solo pagos aplicados
    total_cobrado = PagoPedido.objects.filter(
        empresa=empresa_actual, 
        estado='aplicado',
        pedido__in=pedidos_activos
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    monto_pendiente_cobro = total_vendido - total_cobrado
    stats_monetario_ventas = {
        'pagado': float(total_cobrado),
        'pendiente': float(monto_pendiente_cobro) if monto_pendiente_cobro > 0 else 0
    }

    # --- DATOS PARA GRÁFICAS: COMPRAS ---
    stats_compras = list(OrdenCompra.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))
    stats_recepciones = list(Recepcion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))

    # MONTO DE PAGOS (COMPRAS)
    compras_activas = OrdenCompra.objects.filter(empresa=empresa_actual).exclude(estado='cancelada')
    # Total comprado (MXN)
    total_comprado = compras_activas.aggregate(
        total=Sum(F('detalles__cantidad') * F('detalles__precio_costo') * F('tipo_cambio'))
    )['total'] or Decimal('0.00')
    # Total pagado (MXN) - solo pagos aplicados
    total_pagado_compras = PagoCompra.objects.filter(
        empresa=empresa_actual,
        estado='aplicado',
        orden_compra__in=compras_activas
    ).aggregate(total=Sum('monto_mxn'))['total'] or Decimal('0.00')
    
    monto_pendiente_pago = total_comprado - total_pagado_compras
    stats_monetario_compras = {
        'pagado': float(total_pagado_compras),
        'pendiente': float(monto_pendiente_pago) if monto_pendiente_pago > 0 else 0
    }

    # --- DATOS PARA GRÁFICAS: PRODUCCIÓN ---
    stats_produccion = list(OrdenProduccion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))

    ahora = timezone.now()

    # --- 2. PARETO DE VALOR: TOP 10 PRODUCTOS POR VALOR DE INVENTARIO ---
    from almacenes.models import Inventario
    from django.db.models.functions import Coalesce
    from django.db.models import DecimalField
    top_productos_valor = Inventario.objects.filter(
        empresa=empresa_actual,
        cantidad__gt=0
    ).values('producto__nombre').annotate(
        valor_total=Coalesce(Sum(F('cantidad') * F('costo_promedio')), 0, output_field=DecimalField())
    ).order_by('-valor_total')[:10]
    
    stats_pareto_valor = [
        {'nombre': p['producto__nombre'], 'valor': float(p['valor_total'])} 
        for p in top_productos_valor
    ]

    # --- 4. RENDIMIENTO DE VENTAS: TOP 5 CLIENTES (FACTURACIÓN ÚLTIMOS 30 DÍAS) ---
    hace_30_dias = ahora - timezone.timedelta(days=30)
    top_clientes = Pedido.objects.filter(
        empresa=empresa_actual,
        fecha_creacion__gte=hace_30_dias,
        estado__in=['revision', 'confirmado', 'completo']
    ).values(
        'cliente__razon_social', 
        'cliente__nombre', 
        'cliente__apellidos'
    ).annotate(
        total_venta=Coalesce(Sum(F('detalles__cantidad_solicitada') * F('detalles__precio_unitario')), 0, output_field=DecimalField())
    ).order_by('-total_venta')[:5]

    stats_top_clientes = []
    for c in top_clientes:
        nombre = c['cliente__razon_social']
        if not nombre:
            nombre = f"{c['cliente__nombre']} {c['cliente__apellidos']}".strip()
        if not nombre:
            nombre = "Cliente sin nombre"
        stats_top_clientes.append({'nombre': nombre, 'total': float(c['total_venta'])})

    # --- RESUMEN OPERATIVO (HISTÓRICO 6 MESES) ---
    ahora = timezone.now()
    mes_actual = ahora.month
    anio_actual = ahora.year
    meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    resumen_periodo = []
    for i in range(5, -1, -1):
        target_month = mes_actual - i
        target_year = anio_actual
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        # VENTAS: Pedidos que están en revisión, confirmados o completos
        # Se toma la fecha_creacion como referencia (o podrías usar fecha_confirmacion si aplica)
        v = Pedido.objects.filter(
            empresa=empresa_actual,
            fecha_creacion__year=target_year,
            fecha_creacion__month=target_month,
            estado__in=['revision', 'confirmado', 'completo']
        ).aggregate(
            total=Sum(F('detalles__cantidad_solicitada') * F('detalles__precio_unitario'))
        )['total'] or Decimal('0.00')

        # COMPRAS: Órdenes de compra aprobadas, recibidas o parciales
        c = OrdenCompra.objects.filter(
            empresa=empresa_actual,
            fecha__year=target_year,
            fecha__month=target_month,
            estado__in=['aprobada', 'recibida', 'parcial']
        ).aggregate(
            total=Sum(F('detalles__cantidad') * F('detalles__precio_costo') * F('tipo_cambio'))
        )['total'] or Decimal('0.00')

        resumen_periodo.append({
            'mes': meses_es[target_month - 1],
            'ventas': float(v),
            'compras': float(c),
            'es_actual': (i == 0)
        })

    contexto = {
        'empresa': empresa_actual,
        'username_display': username_display,
        'section': 'inicio',
        'stats_json': json.dumps({
            'cotizaciones': stats_cotizaciones,
            'pedidos': stats_pedidos,
            'salidas': stats_salidas,
            'clientes': stats_clientes,
            'compras': stats_compras,
            'recepciones': stats_recepciones,
            'produccion': stats_produccion,
            'monetario_ventas': stats_monetario_ventas,
            'monetario_compras': stats_monetario_compras,
            'pareto_valor': stats_pareto_valor,
            'top_clientes': stats_top_clientes,
        }),
        'resumen_json': json.dumps(resumen_periodo)
    }
    return render(request, 'inicio/dashboard_inicio.html', contexto)

@login_required(login_url='/login/')
def api_detalle_mes(request):
    try:
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'error': 'Empresa no encontrada'}, status=403)
        
        tipo = request.GET.get('tipo') # 'ventas' o 'compras'
        mes_nombre = request.GET.get('mes')
        anio = timezone.now().year
        
        from django.db.models.functions import Coalesce
        from django.db.models import DecimalField

        meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        try:
            mes_num = meses_es.index(mes_nombre) + 1
        except ValueError:
            return JsonResponse({'error': f'Mes inválido: {mes_nombre}'}, status=400)

        ahora = timezone.now()
        if mes_num > ahora.month:
            anio -= 1

        data = []
        if tipo == 'ventas':
            detalles = Pedido.objects.filter(
                empresa=empresa_actual,
                fecha_creacion__year=anio,
                fecha_creacion__month=mes_num,
                estado__in=['revision', 'confirmado', 'completo']
            ).values(
                'cliente__razon_social', 
                'cliente__nombre', 
                'cliente__apellidos'
            ).annotate(
                total=Coalesce(Sum(F('detalles__cantidad_solicitada') * F('detalles__precio_unitario')), 0, output_field=DecimalField())
            ).order_by('-total')
            
            for d in detalles:
                nombre = d['cliente__razon_social']
                if not nombre:
                    nombre = f"{d['cliente__nombre']} {d['cliente__apellidos']}".strip()
                if not nombre:
                    nombre = "Cliente sin nombre"
                data.append({'entidad': nombre, 'monto': float(d['total'])})
            
        elif tipo == 'compras':
            detalles = OrdenCompra.objects.filter(
                empresa=empresa_actual,
                fecha__year=anio,
                fecha__month=mes_num,
                estado__in=['aprobada', 'recibida', 'parcial']
            ).values('proveedor__razon_social').annotate(
                total=Coalesce(Sum(F('detalles__cantidad') * F('detalles__precio_costo') * F('tipo_cambio')), 0, output_field=DecimalField())
            ).order_by('-total')
            
            data = [{'entidad': d['proveedor__razon_social'], 'monto': float(d['total'])} for d in detalles]

        return JsonResponse({'data': data, 'mes': mes_nombre, 'anio': anio})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
