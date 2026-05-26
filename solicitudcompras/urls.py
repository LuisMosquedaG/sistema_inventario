from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_solicitudcompras, name='dashboard_solicitudcompras'),
    path('crear-desde-pedido/<int:detalle_id>/', views.crear_solicitud_desde_pedido, name='crear_solicitud_desde_pedido'),
    path('crear-manual/', views.crear_solicitud_manual, name='crear_solicitud_manual'),
    path('api/solicitud/<int:solicitud_id>/', views.obtener_solicitud_json, name='obtener_solicitud'),
    path('actualizar/<int:solicitud_id>/', views.actualizar_solicitud, name='actualizar_solicitud'),
    path('autorizar/<int:solicitud_id>/', views.autorizar_solicitud, name='autorizar_solicitud'),
    path('cancelar/<int:solicitud_id>/', views.cancelar_solicitud, name='cancelar_solicitud'),
    path('imprimir/<int:pk>/', views.imprimir_solicitud, name='imprimir_solicitud'),

    # Importador y Exportador
    path('descargar-plantilla/', views.descargar_plantilla_solicitudes, name='descargar_plantilla_solicitudes'),
    path('importar/', views.importar_solicitudes_ajax, name='importar_solicitudes_ajax'),
    path('exportar/', views.exportar_solicitudes_excel, name='exportar_solicitudes_excel'),
]