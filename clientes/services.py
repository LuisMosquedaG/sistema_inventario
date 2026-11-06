from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Max, Q
from .models import Cliente

def sincronizar_tipos_clientes(empresa=None):
    """
    Sincroniza masivamente el tipo de los clientes según su historial de pedidos y antigüedad:
    1. Si es VIP, se respeta la categoría VIP.
    2. Si lleva más de 1 mes (30 días) sin ventas (o creado hace más de 30 días sin ventas) -> 'cliente_inactivo'.
    3. Si un cliente inactivo compró en los últimos 30 días -> 'cliente_activo'.
    4. Si tiene 2 o más pedidos válidos y el último fue en los últimos 30 días -> 'cliente_activo'.
    5. Si tiene 0 o 1 pedido y fue creado o compró en los últimos 30 días (y no es inactivo) -> 'cliente_nuevo'.
    """
    ahora = timezone.now()
    limite_30_dias = ahora - timedelta(days=30)

    qs = Cliente.objects.all()
    if empresa:
        qs = qs.filter(empresa=empresa)

    # Respetar categoría VIP
    qs = qs.exclude(tipo='vip')

    # Anotamos agregados en una sola consulta
    qs_anotado = qs.annotate(
        total_pedidos=Count('pedido', filter=~Q(pedido__estado='cancelado')),
        ultima_compra=Max('pedido__fecha_creacion', filter=~Q(pedido__estado='cancelado'))
    )

    # 1. Pasar a 'cliente_inactivo':
    # Caso A: Con pedidos, pero último pedido < hace 30 días
    ids_inactivos_con_pedidos = list(qs_anotado.filter(
        total_pedidos__gt=0,
        ultima_compra__lt=limite_30_dias
    ).exclude(tipo='cliente_inactivo').values_list('id', flat=True))

    # Caso B: Sin pedidos y creado hace más de 30 días
    ids_inactivos_sin_pedidos = list(qs_anotado.filter(
        total_pedidos=0,
        creado_en__lt=limite_30_dias
    ).exclude(tipo='cliente_inactivo').values_list('id', flat=True))

    ids_a_inactivo = ids_inactivos_con_pedidos + ids_inactivos_sin_pedidos
    if ids_a_inactivo:
        Cliente.objects.filter(id__in=ids_a_inactivo).update(tipo='cliente_inactivo')

    # 2. Pasar a 'cliente_activo':
    # Caso A: Inactivo que volvió a comprar en los últimos 30 días
    ids_inactivos_reactivados = list(qs_anotado.filter(
        tipo='cliente_inactivo',
        total_pedidos__gte=1,
        ultima_compra__gte=limite_30_dias
    ).values_list('id', flat=True))

    # Caso B: 2 o más pedidos válidos con compra en los últimos 30 días
    ids_activos_recurrentes = list(qs_anotado.filter(
        total_pedidos__gte=2,
        ultima_compra__gte=limite_30_dias
    ).exclude(tipo='cliente_activo').values_list('id', flat=True))

    ids_a_activo = set(ids_inactivos_reactivados + ids_activos_recurrentes)
    if ids_a_activo:
        Cliente.objects.filter(id__in=ids_a_activo).update(tipo='cliente_activo')

    # 3. Regularizar clientes nuevos / prospectos recientes:
    # Aquellos con 0 o 1 pedido reciente (creados en los últimos 30 días) que estuvieran marcados erróneamente
    ids_a_nuevo = list(qs_anotado.filter(
        total_pedidos__lte=1,
        creado_en__gte=limite_30_dias
    ).filter(tipo__in=['prospecto']).values_list('id', flat=True))
    if ids_a_nuevo:
        Cliente.objects.filter(id__in=ids_a_nuevo).update(tipo='cliente_nuevo')


def actualizar_tipo_cliente_por_pedido(cliente):
    """
    Actualiza inmediatamente el tipo de cliente tras un pedido.
    """
    if not cliente:
        return
    cliente.actualizar_tipo_cliente()
