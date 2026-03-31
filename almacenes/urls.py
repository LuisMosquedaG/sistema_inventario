from django.urls import path
from . import views

urlpatterns = [
    # Nota que aquí solo ponemos 'almacenes/' porque el padre ya es 'inventario/'
    # La URL final será: /inventario/almacenes/
    path('almacenes/', views.lista_almacenes, name='lista_almacenes'),
    
    # APIs
    path('api/crear-almacen/', views.api_crear_almacen, name='api_crear_almacen'),
    path('api/almacen/<int:id>/', views.api_detalle_almacen, name='api_detalle_almacen'),
    path('api/actualizar-almacen/<int:id>/', views.api_actualizar_almacen, name='api_actualizar_almacen'),
]