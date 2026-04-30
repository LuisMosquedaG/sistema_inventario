from django.urls import path
from . import views

urlpatterns = [
    path('api/recientes/', views.api_notificaciones_recientes, name='api_notificaciones_recientes'),
    path('historial/', views.lista_notificaciones, name='historial_notificaciones'),
]
