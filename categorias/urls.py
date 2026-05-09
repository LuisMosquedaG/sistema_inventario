from django.urls import path
from . import views

urlpatterns = [
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('listas/', views.lista_maestra_dashboard, name='lista_maestra_dashboard'),
    path('api/crear-lista/', views.api_crear_lista, name='api_crear_lista'),
    path('api/lista/<int:id>/', views.api_detalle_lista, name='api_detalle_lista'),
    path('api/actualizar-lista/<int:id>/', views.api_actualizar_lista, name='api_actualizar_lista'),
    path('api/eliminar-lista/<int:id>/', views.api_eliminar_lista, name='api_eliminar_lista'),
    path('api/crear-categoria/', views.api_crear_categoria, name='api_crear_categoria'),
    path('api/categoria/<int:id>/', views.api_detalle_categoria, name='api_detalle_categoria'),
    path('api/actualizar-categoria/<int:id>/', views.api_actualizar_categoria, name='api_actualizar_categoria'),
    path('api/eliminar-categoria/<int:id>/', views.api_eliminar_categoria, name='api_eliminar_categoria'),
    path('api/subcategorias/', views.api_subcategorias_por_categoria, name='api_subcategorias'),
    ]