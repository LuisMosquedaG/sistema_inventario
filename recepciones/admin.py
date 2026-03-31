from django.contrib import admin
from .models import Recepcion, DetalleRecepcion

# Configuración para ver los ítems dentro de la Recepción (Inline)
class DetalleRecepcionInline(admin.TabularInline):
    model = DetalleRecepcion
    extra = 0
    readonly_fields = ('subtotal',)

# Registro de la Recepción (Cabecera)
@admin.register(Recepcion)
class RecepcionAdmin(admin.ModelAdmin):
    list_display = ('id', 'orden_compra', 'almacen', 'fecha', 'estado', 'total_display')
    list_filter = ('estado', 'fecha', 'almacen')
    search_fields = ('orden_compra__proveedor', 'orden_compra__id')
    inlines = [DetalleRecepcionInline] # Muestra los ítems aquí mismo
    readonly_fields = ('total_display',)

    def total_display(self, obj):
        return f"${obj.total}"
    total_display.short_description = 'Total'

# Registro del Detalle (Opcional, para verlos por separado si se requiere)
@admin.register(DetalleRecepcion)
class DetalleRecepcionAdmin(admin.ModelAdmin):
    list_display = ('recepcion', 'producto', 'cantidad_recibida', 'subtotal')
    list_filter = ('recepcion',)