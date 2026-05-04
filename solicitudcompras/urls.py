from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_solicitudcompras, name='dashboard_solicitudcompras'),
    path('crear-desde-pedido/<int:detalle_id>/', views.crear_solicitud_desde_pedido, name='crear_solicitud_desde_pedido'),
    path('crear-manual/', views.crear_solicitud_manual, name='crear_solicitud_manual'),
    path('api/solicitud/<int:solicitud_id>/', views.obtener_solicitud_json, name='obtener_solicitud'),
    path('actualizar/<int:solicitud_id>/', views.actualizar_solicitud, name='actualizar_solicitud'),
    path('autorizar/<int:solicitud_id>/', views.autorizar_solicitud, name='autorizar_solicitud'),
    path('imprimir/<int:pk>/', views.imprimir_solicitud, name='imprimir_solicitud'),
]