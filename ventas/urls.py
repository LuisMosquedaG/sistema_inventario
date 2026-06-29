from django.urls import path
from . import views

urlpatterns = [
    # 1. Dashboard Principal de Ventas
    path('', views.dashboard_ventas, name='dashboard_ventas'),

    # 2. Creación de Orden de Venta (directa)
    path('crear-directa/', views.crear_salida_directa, name='crear_salida_directa'),

    # 3. Creación de Orden de Venta (desde un Pedido)
    path('crear-desde-pedido/<int:pedido_id>/', views.crear_orden_venta, name='crear_orden_venta'),

    # 3. Cambio de Estado simple (Borrador -> Aprobado)
    path('cambiar-estado/<int:ov_id>/<str:nuevo_estado>/', views.cambiar_estado_ov, name='cambiar_estado_ov'),

    # 4. API para preparar el modal de surtido
    path('api/preparar-surtido/<int:ov_id>/', views.api_preparar_surtido, name='api_preparar_surtido'),

    # 5. Ejecución del surtido (POST)
    path('surtir/<int:ov_id>/', views.ejecutar_surtido, name='ejecutar_surtido'),
    
    # 6. Actualización de estado de entrega
    path('actualizar-entrega/<int:ov_id>/', views.actualizar_estado_entrega, name='actualizar_estado_entrega'),

    # 7. Impresión de Orden de Salida
    path('imprimir/<int:pk>/', views.imprimir_salida, name='imprimir_salida'),

    # 8. Importador y Exportador
    path('descargar-plantilla/', views.descargar_plantilla_salidas, name='descargar_plantilla_salidas'),
    path('importar/', views.importar_salidas_ajax, name='importar_salidas_ajax'),
    path('exportar/', views.exportar_salidas_excel, name='exportar_salidas_excel'),

    # 9. Punto de Venta (POS)
    path('pos/', views.punto_de_venta, name='punto_de_venta'),
    path('pos/crear-venta/', views.crear_venta_pos_ajax, name='crear_venta_pos_ajax'),
]