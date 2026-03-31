from django.urls import path
from . import views

urlpatterns = [
    # Esta ruta mantiene activo el Punto de Venta que creamos al principio (en core)
    path('vender/', views.punto_de_venta, name='punto_de_venta'),
    path('api/crear-producto/', views.crear_producto_ajax, name='crear_producto_ajax'),
    path('api/detalle-producto/<int:producto_id>/', views.api_detalle_producto_inventario, name='api_detalle_producto'),
    path('api/guardar-receta/', views.guardar_receta, name='guardar_receta'),
    path('api/ejecutar-prod/', views.ejecutar_produccion, name='ejecutar_produccion'),
    path('api/receta/<int:producto_id>/', views.obtener_receta, name='obtener_receta'),
]