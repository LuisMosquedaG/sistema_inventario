from django.contrib import admin
from .models import Cotizacion, DetalleCotizacion

class DetalleInline(admin.TabularInline):
    model = DetalleCotizacion
    extra = 1
    readonly_fields = ('subtotal',)

@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_inicio', 'estado', 'creado_en')
    list_filter = ('estado', 'creado_en')
    search_fields = ('cliente__nombre', 'id')
    inlines = [DetalleInline] # Permite agregar productos dentro de la cotización