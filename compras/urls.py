from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_compras, name='dashboard_compras'),
    path('crear/', views.crear_compra, name='crear_compra'),
    path('api/compras/<int:compra_id>/', views.obtener_compra_json, name='obtener_compra'),
    path('api/compras/<int:compra_id>/', views.obtener_compra_json, name='obtener_compra'),
    path('cambiar-estado/<int:compra_id>/', views.cambiar_estado_compra, name='cambiar_estado_compra'),
    path('actualizar/<int:compra_id>/', views.actualizar_compra, name='actualizar_compra'),
    path('consolidar/', views.consolidar_compras_ajax, name='consolidar_compras_ajax'),
    path('api/info-pago/<int:compra_id>/', views.api_info_pago_compra, name='api_info_pago_compra'),
    path('imprimir/<int:pk>/', views.imprimir_compra, name='imprimir_compra'),
]