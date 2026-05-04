from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_recepciones, name='dashboard_recepciones'),
    path('crear/', views.crear_recepcion, name='crear_recepcion'),
    path('api/obtener-items-oc/<int:oc_id>/', views.obtener_items_orden_compra, name='obtener_items_oc'),
    path('cambiar-estado/<int:recepcion_id>/', views.cambiar_estado_recepcion, name='cambiar_estado_recepcion'),
    path('api/detalle-recepcion/<int:recepcion_id>/', views.api_detalle_recepcion, name='api_detalle_recepcion'),
    path('cancelar/<int:recepcion_id>/', views.cancelar_recepcion, name='cancelar_recepcion'),
    path('imprimir/<int:pk>/', views.imprimir_recepcion, name='imprimir_recepcion'),
]