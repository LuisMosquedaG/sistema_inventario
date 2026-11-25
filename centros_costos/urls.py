from django.urls import path
from . import views

app_name = 'centros_costos'

urlpatterns = [
    path('', views.dashboard_centros_costos, name='dashboard'),
    path('crear/', views.crear_centro_costo_ajax, name='crear_ajax'),
    path('<int:centro_id>/json/', views.obtener_centro_costo_json, name='obtener_json'),
    path('<int:centro_id>/actualizar/', views.actualizar_centro_costo_ajax, name='actualizar_ajax'),
    path('<int:centro_id>/toggle/', views.toggle_estado_centro_costo_ajax, name='toggle_ajax'),
    path('<int:centro_id>/eliminar/', views.eliminar_centro_costo_ajax, name='eliminar_ajax'),
    path('<int:centro_id>/movimientos/', views.api_movimientos_centro_costo, name='movimientos_api'),
    path('<int:centro_id>/disponibilidad/', views.api_verificar_disponibilidad_centro, name='disponibilidad_api'),
    
    # Clases de Costo (Cost Elements - SAP CO)
    path('clases-costos/api/', views.api_clases_costos_list, name='clases_api_list'),
    path('clases-costos/crear/', views.crear_clase_costo_ajax, name='crear_clase_ajax'),
    path('clases-costos/<int:clase_id>/json/', views.obtener_clase_costo_json, name='obtener_clase_json'),
    path('clases-costos/<int:clase_id>/actualizar/', views.actualizar_clase_costo_ajax, name='actualizar_clase_ajax'),
    path('clases-costos/<int:clase_id>/toggle/', views.toggle_estado_clase_costo_ajax, name='toggle_clase_ajax'),
    path('clases-costos/<int:clase_id>/eliminar/', views.eliminar_clase_costo_ajax, name='eliminar_clase_ajax'),
    path('clases-costos/restablecer-estandar/', views.restablecer_catalogo_estandar_clases_ajax, name='restablecer_clases_estandar_ajax'),

    # Ciclos de Distribución y Prorrateos (SAP Allocation / Assessment)
    path('distribucion/ciclos/api/', views.listar_ciclos_distribucion_ajax, name='ciclos_distribucion_api'),
    path('distribucion/ciclos/guardar/', views.guardar_ciclo_distribucion_ajax, name='guardar_ciclo_distribucion_ajax'),
    path('distribucion/ciclos/<int:ciclo_id>/eliminar/', views.eliminar_ciclo_distribucion_ajax, name='eliminar_ciclo_distribucion_ajax'),
    path('distribucion/ciclos/<int:ciclo_id>/simular/', views.simular_ejecucion_ciclo_ajax, name='simular_ejecucion_ciclo_ajax'),
    path('distribucion/ciclos/<int:ciclo_id>/ejecutar/', views.ejecutar_ciclo_distribucion_ajax, name='ejecutar_ciclo_distribucion_ajax'),
    path('distribucion/ejecuciones/<int:ejecucion_id>/revertir/', views.revertir_ejecucion_ciclo_ajax, name='revertir_ejecucion_ciclo_ajax'),
    path('distribucion/historial/api/', views.historial_ejecuciones_distribucion_ajax, name='historial_distribucion_api'),

    # Cierre de Periodos Contables / Mensuales (SAP Period-End Closing)
    path('periodos/resumen/api/', views.api_resumen_periodo_contable, name='periodos_resumen_api'),
    path('periodos/cerrar/', views.api_cerrar_periodo_contable, name='cerrar_periodo_api'),
    path('periodos/reabrir/', views.api_reabrir_periodo_contable, name='reabrir_periodo_api'),
    path('periodos/historial/api/', views.api_historial_periodos_contables, name='periodos_historial_api'),

    # Asignación de Documentos (OC / Pedidos) a Centros de Costo
    path('documentos-sin-asignar/api/', views.api_documentos_sin_centro_costo, name='documentos_sin_asignar_api'),
    path('asignar-documento/', views.api_asignar_documento_centro_costo, name='asignar_documento_api'),
]
