from django.contrib import admin
from .models import CajaBanco, PagoPedido, Ingreso, PagoCompra, Egreso

@admin.register(CajaBanco)
class CajaBancoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'tipo', 'moneda', 'sucursal', 'activo')
    list_filter = ('tipo', 'moneda', 'activo', 'sucursal')
    search_fields = ('nombre', 'banco_nombre', 'cuenta')

@admin.register(PagoPedido)
class PagoPedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'fecha_pago', 'forma_pago', 'caja_banco', 'monto', 'moneda', 'estado')
    list_filter = ('forma_pago', 'moneda', 'estado', 'sucursal')
    search_fields = ('pedido__id', 'referencia')

@admin.register(Ingreso)
class IngresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'concepto', 'monto', 'moneda', 'forma_pago', 'caja_banco', 'estado')
    list_filter = ('forma_pago', 'moneda', 'estado', 'sucursal')
    search_fields = ('concepto', 'referencia')

@admin.register(PagoCompra)
class PagoCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'orden_compra', 'fecha_pago', 'forma_pago', 'caja_banco', 'monto', 'moneda', 'estado')
    list_filter = ('forma_pago', 'moneda', 'estado', 'sucursal')
    search_fields = ('orden_compra__id', 'referencia')

@admin.register(Egreso)
class EgresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'concepto', 'monto', 'moneda', 'forma_pago', 'caja_banco', 'estado')
    list_filter = ('forma_pago', 'moneda', 'estado', 'sucursal')
    search_fields = ('concepto', 'referencia')
