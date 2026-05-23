from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_inicio, name='dashboard_inicio'),
    path('api/detalle-mes/', views.api_detalle_mes, name='api_detalle_mes'),
]
