from django.contrib import admin
from .models import OrdenCompra, DetalleCompra

# Configuración para ver los ítems dentro de la Orden de Compra (Inline)
class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 0
    readonly_fields = ('subtotal',)

# Registro de la Orden de Compra (Cabecera)
@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'proveedor', 'fecha', 'estado', 'total_display')
    list_filter = ('estado', 'fecha')
    search_fields = ('proveedor',)
    inlines = [DetalleCompraInline] # Muestra los ítems aquí mismo
    readonly_fields = ('fecha',)

    def total_display(self, obj):
        return f"${obj.total}"
    total_display.short_description = 'Total'

# Registro del Detalle (Opcional, por si quieres verlos por separado)
@admin.register(DetalleCompra)
class DetalleCompraAdmin(admin.ModelAdmin):
    list_display = ('orden_compra', 'producto', 'cantidad', 'precio_costo', 'subtotal')
    list_filter = ('orden_compra',)