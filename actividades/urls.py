from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_actividades, name='lista_actividades'),
    path('crear/', views.crear_actividad, name='crear_actividad'),
    path('importar/', views.importar_actividades_ajax, name='importar_actividades_ajax'),
    path('descargar-plantilla/', views.descargar_plantilla_actividades, name='descargar_plantilla_actividades'),
    path('exportar/', views.exportar_actividades_excel, name='exportar_actividades_excel'),
    path('api/cliente/<int:cliente_id>/datos/', views.api_cliente_datos, name='api_cliente_datos'),

    path('editar/<int:actividad_id>/', views.editar_actividad, name='editar_actividad'),
    path('cambiar-estado/<int:actividad_id>/', views.cambiar_estado_actividad, name='cambiar_estado_actividad'),
    path('reprogramar/<int:actividad_id>/', views.reprogramar_actividad, name='reprogramar_actividad'),
    path('cancelar/<int:actividad_id>/', views.cancelar_actividad, name='cancelar_actividad'),
    path('api/datos/<int:actividad_id>/', views.api_datos_actividad, name='api_datos_actividad'),

]