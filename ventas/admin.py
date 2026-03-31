from django.contrib import admin
from .models import OrdenVenta, DetalleOrdenVenta

# Configuración para ver las partidas dentro de la orden en el admin
class DetalleOrdenVentaInline(admin.TabularInline):
    model = DetalleOrdenVenta
    extra = 0
    readonly_fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')

# Registro de la Orden de Venta
@admin.register(OrdenVenta)
class OrdenVentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_creacion', 'cliente', 'estado', 'total_orden')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('cliente__nombre', 'id')
    readonly_fields = ('fecha_creacion', 'total_orden')
    inlines = [DetalleOrdenVentaInline]

    def total_orden(self, obj):
        return f"${obj.total_orden:.2f}"
    total_orden.short_description = 'Total'

# Registro opcional del detalle por separado
admin.site.register(DetalleOrdenVenta)