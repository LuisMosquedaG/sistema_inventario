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

    # --- DATOS PARA GRÁFICAS: COMPRAS ---
    stats_compras = list(OrdenCompra.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))
    stats_recepciones = list(Recepcion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))

    # --- DATOS PARA GRÁFICAS: PRODUCCIÓN ---
    stats_produccion = list(OrdenProduccion.objects.filter(empresa=empresa_actual).values('estado').annotate(total=Count('id')))

    # --- RESUMEN OPERATIVO (HISTÓRICO 4 MESES) ---
    ahora = timezone.now()
    mes_actual = ahora.month
    anio_actual = ahora.year
    meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    resumen_periodo = []
    # Obtenemos los últimos 4 meses (3 anteriores + actual)
    for i in range(3, -1, -1):
        target_month = mes_actual - i
        target_year = anio_actual
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        # Ventas: Suma de subtotales de partidas de OrdenVenta
        v = OrdenVenta.objects.filter(
            empresa=empresa_actual,
            fecha_creacion__year=target_year,
            fecha_creacion__month=target_month
        ).exclude(estado='cancelado').aggregate(
            total=Sum(F('detalles__cantidad') * F('detalles__precio_unitario'))
        )['total'] or Decimal('0.00')

        # Compras: Suma de (cantidad * costo * TC) de partidas de OrdenCompra
        c = OrdenCompra.objects.filter(
            empresa=empresa_actual,
            fecha__year=target_year,
            fecha__month=target_month
        ).exclude(estado='cancelada').aggregate(
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
            'compras': stats_compras,
            'recepciones': stats_recepciones,
            'produccion': stats_produccion,
        }),
        'resumen_json': json.dumps(resumen_periodo)
    }
    return render(request, 'inicio/dashboard_inicio.html', contexto)
