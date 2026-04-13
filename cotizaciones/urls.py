from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_cotizaciones, name='dashboard_cotizaciones'),
    path('crear/', views.crear_cotizacion, name='crear_cotizacion'), # NUEVA RUTA
    path('cancelar/<int:cotizacion_id>/', views.cancelar_cotizacion, name='cancelar_cotizacion'),
]