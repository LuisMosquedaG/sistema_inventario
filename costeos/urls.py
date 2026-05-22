from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_costeos, name='dashboard_costeos'),
    path('api/guardar/', views.api_guardar_costeo, name='api_guardar_costeo'),
    path('api/detalle/<int:costeo_id>/', views.api_detalle_costeo, name='api_detalle_costeo'),
    path('api/aprobar/<int:costeo_id>/', views.api_aprobar_costeo, name='api_aprobar_costeo'),
    path('api/duplicar/<int:costeo_id>/', views.api_duplicar_costeo, name='api_duplicar_costeo'),
    path('api/eliminar/<int:costeo_id>/', views.api_eliminar_costeo, name='api_eliminar_costeo'),
]
