from django.urls import path
from . import views

urlpatterns = [
    path('cajas-bancos/', views.lista_cajas_bancos, name='lista_cajas_bancos'),
    path('ingresos/', views.lista_ingresos, name='lista_ingresos'),
    path('egresos/', views.lista_egresos, name='lista_egresos'),
    path('api/caja-banco/crear/', views.api_crear_caja_banco, name='api_crear_caja_banco'),
    path('api/caja-banco/<int:id>/', views.api_detalle_caja_banco, name='api_detalle_caja_banco'),
    path('api/caja-banco/actualizar/<int:id>/', views.api_actualizar_caja_banco, name='api_actualizar_caja_banco'),
    path('api/registrar-pago-pedido/', views.api_registrar_pago_pedido, name='api_registrar_pago_pedido'),
    path('api/registrar-pago-compra/', views.api_registrar_pago_compra, name='api_registrar_pago_compra'),
    path('api/ingreso/cancelar/<int:id>/', views.api_cancelar_ingreso, name='api_cancelar_ingreso'),
    path('api/ingreso/<int:id>/', views.api_detalle_ingreso, name='api_detalle_ingreso'),
    path('api/egreso/cancelar/<int:id>/', views.api_cancelar_egreso, name='api_cancelar_egreso'),
    path('api/egreso/<int:id>/', views.api_detalle_egreso, name='api_detalle_egreso'),
]
