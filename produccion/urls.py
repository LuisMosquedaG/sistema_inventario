from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_produccion, name='dashboard_produccion'),
    
    # Importador y Exportador
    path('descargar-plantilla/', views.descargar_plantilla_produccion, name='descargar_plantilla_produccion'),
    path('importar/', views.importar_produccion_ajax, name='importar_produccion_ajax'),
    path('exportar/', views.exportar_produccion_excel, name='exportar_produccion_excel'),

    path('crear/', views.crear_orden_produccion, name='crear_orden_produccion'),
    path('api/detalle/<int:orden_id>/', views.api_detalle_orden, name='api_detalle_orden'),
    path('api/obtener-test/<int:orden_id>/', views.api_obtener_test_orden, name='api_obtener_test_orden'),
    path('actualizar/<int:orden_id>/', views.actualizar_orden_produccion, name='actualizar_orden_produccion'),
    path('guardar-avance-test/<int:orden_id>/', views.guardar_avance_test_ajax, name='guardar_avance_test_ajax'), # NUEVA
    path('finalizar-con-test/<int:orden_id>/', views.finalizar_con_test_ajax, name='finalizar_con_test_ajax'),

    path('avanzar/<int:orden_id>/', views.avanzar_estado_produccion, name='avanzar_estado_produccion'),
    path('cancelar/<int:orden_id>/', views.cancelar_produccion, name='cancelar_produccion'),

    # CATÁLOGO DE TESTS
    path('tests/', views.lista_tests, name='lista_tests'),
    path('api/crear-test/', views.crear_test_ajax, name='crear_test_ajax'),
    path('api/detalle-test/<int:test_id>/', views.api_detalle_test, name='api_detalle_test'),
    path('api/actualizar-test/<int:test_id>/', views.actualizar_test_ajax, name='actualizar_test_ajax'),
    path('api/eliminar-test/<int:test_id>/', views.eliminar_test_ajax, name='eliminar_test_ajax'),
    path('api/receta/<int:producto_id>/', views.api_obtener_receta, name='api_obtener_receta'),
    path('api/stock-almacen/<int:almacen_id>/', views.api_stock_almacen, name='api_stock_almacen'),
    path('api/finalizar-completo/', views.finalizar_produccion_completo, name='finalizar_produccion_completo'),
    path('imprimir/<int:pk>/', views.imprimir_orden_produccion, name='imprimir_op'),
]
