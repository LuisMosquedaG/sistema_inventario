from django.contrib import admin
from .models import Almacen, Inventario

class InventarioAdmin(admin.ModelAdmin):
    list_display = ('producto', 'almacen', 'cantidad', 'fecha_actualizacion')
    list_filter = ('almacen',)
    search_fields = ('producto__nombre',)

admin.site.register(Almacen)
admin.site.register(Inventario, InventarioAdmin)