from django.urls import path
from . import views

urlpatterns = [
    path('empleados/', views.lista_empleados, name='lista_empleados'),
    path('empleados/crear/', views.crear_empleado_ajax, name='crear_empleado_ajax'),
    path('empleados/obtener/<int:id>/', views.obtener_empleado_json, name='obtener_empleado_json'),
    path('empleados/editar/<int:id>/', views.editar_empleado_ajax, name='editar_empleado_ajax'),
    path('contratos/', views.lista_contratos, name='lista_contratos'),
    path('contratos/crear/', views.crear_contrato_ajax, name='crear_contrato_ajax'),
    path('contratos/obtener/<int:id>/', views.obtener_contrato_json, name='obtener_contrato_json'),
    path('contratos/editar/<int:id>/', views.editar_contrato_ajax, name='editar_contrato_ajax'),
]
