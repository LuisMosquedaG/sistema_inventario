from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_inicio, name='dashboard_inicio'),
    path('api/detalle-mes/', views.api_detalle_mes, name='api_detalle_mes'),
    path('api/contratos-nightingale/', views.api_contratos_nightingale, name='api_contratos_nightingale'),
    path('api/contratos-totales-contratistas/', views.api_contratos_totales_contratistas, name='api_contratos_totales_contratistas'),
]
