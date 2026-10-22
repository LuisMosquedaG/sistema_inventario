from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_recepciones, name='dashboard_recepciones'),
    
    # Importador y Exportador
    path('descargar-plantilla/', views.descargar_plantilla_recepciones, name='descargar_plantilla_recepciones'),
    path('importar/', views.importar_recepciones_ajax, name='importar_recepciones_ajax'),
    path('exportar/', views.exportar_recepciones_excel, name='exportar_recepciones_excel'),

    # API y Acciones (Sincronizado con recepciones.js)
    path('api/obtener-items-oc/<int:oc_id>/', views.obtener_items_orden_compra, name='obtener_items_orden_compra'),
    path('api/detalle-recepcion/<int:recepcion_id>/', views.api_detalle_recepcion, name='obtener_detalle_recepcion'),
    path('crear/', views.crear_recepcion, name='crear_recepcion'),
    path('cambiar-estado/<int:recepcion_id>/', views.cambiar_estado_recepcion, name='cambiar_estado_recepcion'),
    path('cancelar/<int:recepcion_id>/', views.cancelar_recepcion, name='cancelar_recepcion'),
    path('imprimir/<int:pk>/', views.imprimir_recepcion, name='imprimir_recepcion'),

    # Devoluciones de Recepción
    path('devoluciones/', views.dashboard_devoluciones, name='dashboard_devoluciones'),
    path('devoluciones/exportar/', views.exportar_devoluciones_excel, name='exportar_devoluciones_excel'),
    path('api/devolucion/<int:recepcion_id>/', views.crear_devolucion_recepcion, name='crear_devolucion_recepcion'),
    path('api/detalle-devolucion/<int:devolucion_id>/', views.api_detalle_devolucion, name='api_detalle_devolucion'),
]
