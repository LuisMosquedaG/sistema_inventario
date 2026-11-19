from django.urls import path
from . import views

app_name = 'centros_costos'

urlpatterns = [
    path('', views.dashboard_centros_costos, name='dashboard'),
    path('crear/', views.crear_centro_costo_ajax, name='crear_ajax'),
    path('<int:centro_id>/json/', views.obtener_centro_costo_json, name='obtener_json'),
    path('<int:centro_id>/actualizar/', views.actualizar_centro_costo_ajax, name='actualizar_ajax'),
    path('<int:centro_id>/toggle/', views.toggle_estado_centro_costo_ajax, name='toggle_ajax'),
    path('<int:centro_id>/eliminar/', views.eliminar_centro_costo_ajax, name='eliminar_ajax'),
    path('<int:centro_id>/movimientos/', views.api_movimientos_centro_costo, name='movimientos_api'),
]
