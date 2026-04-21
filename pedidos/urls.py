from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_pedidos, name='dashboard_pedidos'),
    path('crear/', views.crear_pedido_manual, name='crear_pedido_manual'),
    path('crear-desde-cotizacion/<int:cotizacion_id>/', views.crear_pedido_desde_cotizacion, name='crear_pedido_desde_cotizacion'),
    path('validar/<int:pedido_id>/', views.validar_pedido, name='validar_pedido'),
    path('api/detalle/<int:pedido_id>/', views.api_detalle_pedido, name='api_detalle_pedido'),
    path('completar-linea/<int:detalle_id>/', views.completar_linea_pedido, name='completar_linea_pedido'),
    path('ejecutar-reserva/<int:detalle_id>/', views.ejecutar_reserva, name='ejecutar_reserva'),
    path('generar-solicitud-global/<int:pedido_id>/', views.generar_solicitud_global, name='generar_solicitud_global'),
    path('api/ver/<int:pedido_id>/', views.obtener_pedido_json, name='obtener_pedido_json'),
]