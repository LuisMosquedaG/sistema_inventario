from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
from django.db.models import Count, Q, Sum, F, Max
from django.utils import timezone
from django.http import JsonResponse
from cotizaciones.models import Cotizacion
from pedidos.models import Pedido
from ventas.models import OrdenVenta
from compras.models import OrdenCompra
from recepciones.models import Recepcion
from produccion.models import OrdenProduccion
from tesoreria.models import PagoPedido, PagoCompra, Ingreso
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
    if hasattr(request.user, 'beneficiario'):
        return redirect('portal_beneficiarios')
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
    anio_corriente = ahora.year
    for m in range(1, 13):
        # VENTAS: Pedidos que están en revisión, confirmados o completos
        v = Pedido.objects.filter(
            empresa=empresa_actual,
            fecha_creacion__year=anio_corriente,
            fecha_creacion__month=m,
            estado__in=['revision', 'confirmado', 'completo']
        ).aggregate(
            total=Sum(F('detalles__cantidad_solicitada') * F('detalles__precio_unitario'))
        )['total'] or Decimal('0.00')

        # COMPRAS: Órdenes de compra aprobadas, recibidas o parciales
        c = OrdenCompra.objects.filter(
            empresa=empresa_actual,
            fecha__year=anio_corriente,
            fecha__month=m,
            estado__in=['aprobada', 'recibida', 'parcial']
        ).aggregate(
            total=Sum(F('detalles__cantidad') * F('detalles__precio_costo') * F('tipo_cambio'))
        )['total'] or Decimal('0.00')

        resumen_periodo.append({
            'mes': meses_es[m - 1],
            'ventas': float(v),
            'compras': float(c),
            'es_actual': (m == mes_actual)
        })

    # --- 2. COMPROBANTES VS INGRESOS (HISTÓRICO 6 MESES TRAILING) ---
    comprobantes_ingresos_periodo = []
    for i in range(5, -1, -1):
        target_month = mes_actual - i
        target_year = anio_actual
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        # 1. Pedidos en revisión o completo (sumando total_pedido)
        pedidos_mes = Pedido.objects.filter(
            empresa=empresa_actual,
            estado__in=['revision', 'completo'],
            fecha_creacion__year=target_year,
            fecha_creacion__month=target_month
        )
        total_comprobantes = sum(p.total_pedido for p in pedidos_mes)

        # 2. Ingresos aplicados (monto_mxn)
        total_ingresos = Ingreso.objects.filter(
            empresa=empresa_actual,
            estado='applied' if hasattr(Ingreso, 'applied') else 'aplicado',  # Por si acaso, usamos 'aplicado'
            fecha__year=target_year,
            fecha__month=target_month
        ).aggregate(total=Sum('monto_mxn'))['total'] or Decimal('0.00')

        comprobantes_ingresos_periodo.append({
            'mes': meses_es[target_month - 1],
            'comprobantes': float(total_comprobantes),
            'ingresos': float(total_ingresos)
        })

    # --- 3. CONTRATOS: Agrupación anual (enero a diciembre del año corriente) ---
    from recursos_humanos.models import Contrato
    contratos_periodo = []
    anio_corriente = ahora.year
    for m in range(1, 13):
        contratos_mes = Contrato.objects.filter(
            empresa=empresa_actual,
            vigencia_contrato__year=anio_corriente,
            vigencia_contrato__month=m
        )
        total_contratos_mes = contratos_mes.aggregate(
            total=Sum('monto_contrato')
        )['total'] or Decimal('0.00')

        contratos_periodo.append({
            'mes': meses_es[m - 1],
            'monto': float(total_contratos_mes)
        })

    # --- 5. OBLIGACIONES PATRONALES: ESTADOS POR CONTRATO Y SUAS POR CONTRATISTA ---
    from recursos_humanos.models import Contrato, Contratista, ImportacionSUA
    stats_contratos_estados = list(Contrato.objects.filter(
        empresa=empresa_actual
    ).values('estado').annotate(
        total=Count('id')
    ))

    contratistas = Contratista.objects.filter(empresa=empresa_actual)
    suas = list(ImportacionSUA.objects.filter(empresa=empresa_actual))
    stats_suas_contratistas = []
    stats_suas_empleados = []

    for con in contratistas:
        con_rfc_clean = con.rfc.replace('-', '').strip().upper() if con.rfc else ""
        con_rp_clean = con.registro_patronal.replace('-', '').strip().upper() if con.registro_patronal else ""
        con_name_clean = con.nombre_razon_social.strip().upper() if con.nombre_razon_social else ""
        
        total_contratista_rcv_inf = Decimal('0.00')
        unique_nss = set()
        for s in suas:
            s_rfc_clean = s.rfc_empresa.replace('-', '').strip().upper() if s.rfc_empresa else ""
            s_rp_clean = s.registro_patronal.replace('-', '').strip().upper() if s.registro_patronal else ""
            s_name_clean = s.nombre_razon_social.strip().upper() if s.nombre_razon_social else ""
            
            if (con_rfc_clean and con_rfc_clean == s_rfc_clean) or \
               (con_rp_clean and con_rp_clean == s_rp_clean) or \
               (con_name_clean and con_name_clean == s_name_clean):
                totales_sua = s.trabajadores.aggregate(
                    rcv=Sum('subtotal'),
                    inf=Sum('suma_infonavit')
                )
                total_contratista_rcv_inf += (totales_sua['rcv'] or Decimal('0.00')) + (totales_sua['inf'] or Decimal('0.00'))
                
                for t in s.trabajadores.all():
                    if t.nss:
                        unique_nss.add(t.nss.strip())
                
        stats_suas_contratistas.append({
            'contratista': con.nombre_razon_social,
            'monto': float(total_contratista_rcv_inf)
        })
        stats_suas_empleados.append({
            'contratista': con.nombre_razon_social,
            'cantidad': len(unique_nss)
        })

    # Ordenar por monto descendente y tomar los top 10
    stats_suas_contratistas = sorted(stats_suas_contratistas, key=lambda x: x['monto'], reverse=True)[:10]
    stats_suas_empleados = sorted(stats_suas_empleados, key=lambda x: x['cantidad'], reverse=True)[:10]

    # Contratos más caros por contratista (top 5 max_monto)
    contratos_caros = Contrato.objects.filter(
        empresa=empresa_actual,
        contratista__isnull=False
    ).values('contratista__nombre_razon_social').annotate(
        max_monto=Max('monto_contrato')
    ).order_by('-max_monto')[:5]

    stats_contratos_caros = []
    for c in contratos_caros:
        stats_contratos_caros.append({
            'contratista': c['contratista__nombre_razon_social'],
            'monto': float(c['max_monto'])
        })

    # Contratistas con más beneficiarios (top 5 distinct count)
    contratistas_beneficiarios = Contrato.objects.filter(
        empresa=empresa_actual,
        contratista__isnull=False,
        beneficiario__isnull=False
    ).values('contratista__nombre_razon_social').annotate(
        num_benef=Count('beneficiario', distinct=True)
    ).order_by('-num_benef')[:5]

    stats_contratistas_beneficiarios = []
    for cb in contratistas_beneficiarios:
        stats_contratistas_beneficiarios.append({
            'contratista': cb['contratista__nombre_razon_social'],
            'cantidad': cb['num_benef']
        })

    # Cálculo de espacio en disco real
    from panel.views import calcular_uso_disco_mb
    uso_actual_mb = calcular_uso_disco_mb(empresa_actual)
    limite_mb = empresa_actual.limite_espacio_disco
    porcentaje_uso_disco = round((uso_actual_mb / limite_mb) * 100, 1) if limite_mb > 0 else 0
    espacio_libre_mb = max(0.0, float(limite_mb) - float(uso_actual_mb))

    contexto = {
        'empresa': empresa_actual,
        'username_display': username_display,
        'section': 'inicio',
        'contratistas': contratistas,
        'uso_actual_mb': uso_actual_mb,
        'limite_espacio_disco': limite_mb,
        'porcentaje_uso_disco': porcentaje_uso_disco,
        'espacio_libre_mb': espacio_libre_mb,
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
            'contratos_estados': stats_contratos_estados,
            'suas_contratistas': stats_suas_contratistas,
            'suas_empleados': stats_suas_empleados,
            'contratos_caros': stats_contratos_caros,
            'contratistas_beneficiarios': stats_contratistas_beneficiarios,
        }),
        'resumen_json': json.dumps(resumen_periodo),
        'comprobantes_ingresos_json': json.dumps(comprobantes_ingresos_periodo),
        'contratos_json': json.dumps(contratos_periodo)
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

        elif tipo == 'contratos':
            from recursos_humanos.models import Contrato
            anio = timezone.now().year
            detalles = Contrato.objects.filter(
                empresa=empresa_actual,
                vigencia_contrato__year=anio,
                vigencia_contrato__month=mes_num
            ).select_related('contratista').order_by('-monto_contrato')
            
            data = []
            for c in detalles:
                nombre_contratista = c.contratista.nombre_razon_social if c.contratista else "Sin Contratista"
                folio_str = f" (Folio: {c.folio})" if c.folio else " (S/F)"
                data.append({
                    'entidad': f"{nombre_contratista}{folio_str}",
                    'monto': float(c.monto_contrato)
                })

        return JsonResponse({'data': data, 'mes': mes_nombre, 'anio': anio})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/login/')
def api_contratos_nightingale(request):
    try:
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'error': 'Empresa no encontrada'}, status=403)
        
        contratista_id = request.GET.get('contratista_id')
        if not contratista_id:
            return JsonResponse({'error': 'Debe especificar el contratista_id'}, status=400)
            
        from recursos_humanos.models import Contrato
        contratos = Contrato.objects.filter(
            empresa=empresa_actual,
            contratista_id=contratista_id,
            estado='vigente'
        ).select_related('beneficiario').order_by('-monto_contrato')
        
        total_monto = sum(float(c.monto_contrato) for c in contratos)
        data = []
        for c in contratos:
            benef_str = f" ({c.beneficiario.nombre_razon_social})" if c.beneficiario else ""
            folio_str = c.folio if c.folio else f"Folio: S/F (#{c.id})"
            porcentaje = (float(c.monto_contrato) / total_monto * 100) if total_monto > 0 else 0
            
            data.append({
                'label': f"{folio_str}{benef_str}",
                'monto': float(c.monto_contrato),
                'porcentaje': round(porcentaje, 1),
                'objeto': c.objeto_contrato or ''
            })
            
        return JsonResponse({'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def api_contratos_totales_contratistas(request):
    try:
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'error': 'No se encontró la empresa actual'}, status=403)
            
        from recursos_humanos.models import Contrato
        contratos = Contrato.objects.filter(
            empresa=empresa_actual,
            estado='vigente',
            contratista__isnull=False
        ).select_related('contratista')
        
        # Agrupar montos por contratista
        from collections import defaultdict
        monto_por_contratista = defaultdict(float)
        for c in contratos:
            nombre = c.contratista.nombre_razon_social
            monto_por_contratista[nombre] += float(c.monto_contrato)
            
        total_monto = sum(monto_por_contratista.values())
        data = []
        for nombre, monto in monto_por_contratista.items():
            porcentaje = (monto / total_monto * 100) if total_monto > 0 else 0
            data.append({
                'label': nombre,
                'monto': monto,
                'porcentaje': round(porcentaje, 1)
            })
            
        # Ordenar por monto descendente
        data.sort(key=lambda x: x['monto'], reverse=True)
        
        return JsonResponse({'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
