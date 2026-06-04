from django.contrib import admin
from .models import Proveedor

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'rfc', 'contacto_nombre', 'contacto_telefono')
    search_fields = ('razon_social', 'rfc', 'contacto_nombre')