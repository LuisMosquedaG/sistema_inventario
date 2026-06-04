from django.contrib import admin
from .models import SolicitudCompra, DetalleSolicitudCompra

class DetalleSolicitudCompraInline(admin.TabularInline):
    model = DetalleSolicitudCompra
    extra = 0
    autocomplete_fields = ['producto', 'proveedor']

@admin.register(SolicitudCompra)
class SolicitudCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'solicitante', 'fecha_creacion', 'estado', 'pedido_origen')
    list_filter = ('estado', 'empresa', 'sucursal')
    search_fields = ('id', 'solicitante__username', 'notas')
    inlines = [DetalleSolicitudCompraInline]
    date_hierarchy = 'fecha_creacion'

@admin.register(DetalleSolicitudCompra)
class DetalleSolicitudCompraAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'producto', 'cantidad_solicitada', 'proveedor', 'costo_unitario')
    list_filter = ('solicitud__empresa',)
    search_fields = ('producto__nombre', 'solicitud__id')
