from django.urls import path
from . import views

urlpatterns = [
    # Almacenes
    path('almacenes/', views.lista_almacenes, name='lista_almacenes'),
    path('kardex/', views.dashboard_kardex, name='dashboard_kardex'),
    
    # APIs Almacén
    path('api/crear-almacen/', views.api_crear_almacen, name='api_crear_almacen'),
    path('api/almacen/<int:id>/', views.api_detalle_almacen, name='api_detalle_almacen'),
    path('api/actualizar-almacen/<int:id>/', views.api_actualizar_almacen, name='api_actualizar_almacen'),

    # APIs Traslados
    path('api/productos-con-stock/<int:almacen_id>/', views.api_productos_con_stock, name='api_productos_con_stock'),
    path('api/extras-producto/<int:almacen_id>/<int:producto_id>/', views.api_extras_producto, name='api_extras_producto'),
    path('api/ejecutar-traslado/', views.api_ejecutar_traslado, name='api_ejecutar_traslado'),
]
