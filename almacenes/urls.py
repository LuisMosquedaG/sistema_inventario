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
    path('api/detalle-reservas/<int:producto_id>/', views.api_detalle_reservas, name='api_detalle_reservas'),

    # Toma de Inventario Físico
    path('toma-inventario/', views.dashboard_toma_inventario, name='dashboard_toma_inventario'),
    path('toma-inventario/api/crear/', views.api_crear_toma_inventario, name='api_crear_toma_inventario'),
    path('toma-inventario/api/materiales/<int:toma_id>/', views.api_materiales_toma_inventario, name='api_materiales_toma_inventario'),
    path('toma-inventario/api/buscar-articulo/<int:toma_id>/', views.api_buscar_articulo_toma, name='api_buscar_articulo_toma'),
    path('toma-inventario/api/guardar-conteo/<int:toma_id>/', views.api_guardar_conteo_toma, name='api_guardar_conteo_toma'),
    path('toma-inventario/api/cambiar-estado/<int:toma_id>/', views.api_cambiar_estado_toma, name='api_cambiar_estado_toma'),
    path('toma-inventario/api/cerrar/<int:toma_id>/', views.api_cerrar_toma_inventario, name='api_cerrar_toma_inventario'),
    path('toma-inventario/api/eliminar/<int:toma_id>/', views.api_eliminar_toma_inventario, name='api_eliminar_toma_inventario'),
]
