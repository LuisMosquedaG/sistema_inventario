from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_produccion, name='dashboard_produccion'),
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
]
