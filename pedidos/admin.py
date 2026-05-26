from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Pedido, DetallePedido
from almacenes.models import Inventario

# Configuración para ver las líneas de pedido dentro del Pedido (en una tabla anidada)
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    fields = ('producto', 'cantidad_solicitada', 'estado_linea', 'precio_unitario', 'subtotal')
    readonly_fields = ('producto', 'cantidad_solicitada', 'precio_unitario', 'subtotal')
    can_delete = False

# Configuración del panel de Pedidos
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'fecha_creacion', 'total_pedido_display')
    list_filter = ('estado', 'fecha_creacion', 'sucursal')
    search_fields = ('id', 'cliente__nombre', 'cliente__razon_social')
    date_hierarchy = 'fecha_creacion'
    inlines = [DetallePedidoInline] # Muestra los detalles al entrar al pedido
    actions = ['resetear_partidas_solicitud']

    def total_pedido_display(self, obj):
        return f"${obj.total_pedido:.2f}"
    total_pedido_display.short_description = 'Total'

    @admin.action(description="Resetear partidas para nueva solicitud (Libera stock y cambia a Compra/Prod)")
    def resetear_partidas_solicitud(self, request, queryset):
        for pedido in queryset:
            detalles = pedido.detalles.all()
            for det in detalles:
                # 1. Liberar stock si estaba reservado
                if det.estado_linea == 'reservado':
                    inv = Inventario.objects.filter(producto=det.producto, reservado__gt=0).first()
                    if inv:
                        inv.reservado = max(0, inv.reservado - det.cantidad_solicitada)
                        inv.save()
                
                # 2. Revertir estado a Compra o Producción
                if det.producto.tipo_abastecimiento == 'produccion':
                    det.estado_linea = 'produccion'
                else:
                    det.estado_linea = 'compra'
                det.save()
            
            # 3. Regresar pedido a revisión si estaba completo
            if pedido.estado == 'completo':
                pedido.estado = 'revision'
                pedido.save()
        
        self.message_user(request, "Las partidas de los pedidos seleccionados han sido reseteadas correctamente.", messages.SUCCESS)

    # Para optimizar la carga de la lista
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cliente')

# Registro de DetallePedido (por si quieres verlos por separado, aunque no es muy común)
@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'producto', 'cantidad_solicitada', 'estado_linea')
    list_filter = ('estado_linea',)