from django.contrib import admin
from .models import Producto, Categoria, Transaccion
from almacenes.models import Inventario, Almacen

# --- Para ver el stock directamente al editar un Producto ---
class InventarioInline(admin.TabularInline):
    model = Inventario
    extra = 0 # No mostrar filas vacías extra
    readonly_fields = ('fecha_actualizacion',)

class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_venta', 'stock_total', 'tipo', 'estado')
    search_fields = ('nombre', 'categoria')
    list_filter = ('estado', 'tipo')
    inlines = [InventarioInline] # <--- Mágico: muestra el inventario dentro del producto

# --- Registro de modelos ---
admin.site.register(Categoria)
admin.site.register(Producto, ProductoAdmin)
admin.site.register(Transaccion)