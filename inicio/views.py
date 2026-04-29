from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from cotizaciones.models import Cotizacion
from pedidos.models import Pedido
from ventas.models import OrdenVenta
from compras.models import OrdenCompra
from recepciones.models import Recepcion
from produccion.models import OrdenProduccion
from decimal import Decimal

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
    stats_cotizaciones = Cotizacion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id'))
    stats_pedidos = Pedido.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id'))
    stats_salidas = OrdenVenta.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id'))

    # --- DATOS PARA GRÁFICAS: COMPRAS ---
    stats_compras = OrdenCompra.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id'))
    stats_recepciones = Recepcion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id'))

    # --- DATOS PARA GRÁFICAS: PRODUCCIÓN ---
    stats_produccion = OrdenProduccion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id'))

    # --- RESUMEN OPERATIVO (VENTAS VS COMPRAS DEL MES) ---
    ahora = timezone.now()
    mes_actual = ahora.month
    anio_actual = ahora.year
    
    # 1. Ventas del mes (OrdenVenta / Salidas) en MXN
    ventas_mes = OrdenVenta.objects.filter(
        empresa=empresa_actual,
        fecha_creacion__year=anio_actual,
        fecha_creacion__month=mes_actual
    ).exclude(estado='cancelado').aggregate(
        total_mxn=Sum(F('detalles__cantidad') * F('detalles__precio_unitario'))
    )['total_mxn'] or Decimal('0.00')

    # 2. Compras del mes (OrdenCompra) en MXN (Monto * TC)
    compras_mes = OrdenCompra.objects.filter(
        empresa=empresa_actual,
        fecha__year=anio_actual,
        fecha__month=mes_actual
    ).exclude(estado='cancelada').aggregate(
        total_mxn=Sum(F('detalles__cantidad') * F('detalles__precio_costo') * F('tipo_cambio'))
    )['total_mxn'] or Decimal('0.00')

    # Obtener nombre del mes
    meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    nombre_mes = meses_es[mes_actual - 1]

    contexto = {
        'empresa': empresa_actual,
        'username_display': username_display,
        'section': 'inicio',
        'stats': {
            'cotizaciones': list(stats_cotizaciones),
            'pedidos': list(stats_pedidos),
            'salidas': list(stats_salidas),
            'compras': list(stats_compras),
            'recepciones': list(stats_recepciones),
            'produccion': list(stats_produccion),
        },
        'resumen_mes': {
            'mes': nombre_mes,
            'ventas': float(ventas_mes),
            'compras': float(compras_mes)
        }
    }
    return render(request, 'inicio/dashboard_inicio.html', contexto)
