from django.urls import path
from . import views

urlpatterns = [
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('api/crear-categoria/', views.api_crear_categoria, name='api_crear_categoria'),
    path('api/categoria/<int:id>/', views.api_detalle_categoria, name='api_detalle_categoria'),
    path('api/actualizar-categoria/<int:id>/', views.api_actualizar_categoria, name='api_actualizar_categoria'),
    path('api/subcategorias/', views.api_subcategorias_por_categoria, name='api_subcategorias'),
]