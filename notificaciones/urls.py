from django.urls import path
from . import views

urlpatterns = [
    path('api/recientes/', views.api_notificaciones_recientes, name='api_notificaciones_recientes'),
    path('historial/', views.lista_notificaciones, name='historial_notificaciones'),
    path('enviar-mensaje-ventas/', views.enviar_mensaje_ventas_ajax, name='enviar_mensaje_ventas_ajax'),
]
