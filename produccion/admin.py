from django.contrib import admin
from .models import OrdenProduccion

@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    list_display = ('folio', 'producto', 'cantidad', 'estado', 'fecha_creacion', 'empresa')
    list_filter = ('estado', 'empresa', 'fecha_creacion')
    search_fields = ('id', 'producto__nombre', 'pedido_origen__id')
    readonly_fields = ('fecha_creacion',)
