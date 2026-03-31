from django.contrib import admin
from .models import Pedido, DetallePedido

# Configuración para ver las líneas de pedido dentro del Pedido (en una tabla anidada)
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    readonly_fields = ('producto', 'cantidad_solicitada', 'precio_unitario', 'subtotal')
    can_delete = False

# Configuración del panel de Pedidos
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'fecha_creacion', 'total_pedido_display')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('id', 'cliente__nombre', 'cliente__razon_social')
    date_hierarchy = 'fecha_creacion'
    inlines = [DetallePedidoInline] # Muestra los detalles al entrar al pedido

    def total_pedido_display(self, obj):
        return f"${obj.total_pedido:.2f}"
    total_pedido_display.short_description = 'Total'

    # Para optimizar la carga de la lista
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cliente')

# Registro de DetallePedido (por si quieres verlos por separado, aunque no es muy común)
@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'producto', 'cantidad_solicitada', 'estado_linea')
    list_filter = ('estado_linea',)