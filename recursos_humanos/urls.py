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
    path('contratistas/', views.lista_contratistas, name='lista_contratistas'),
    path('contratistas/crear/', views.crear_contratista_ajax, name='crear_contratista_ajax'),
    path('contratistas/obtener/<int:id>/', views.obtener_contratista_json, name='obtener_contratista_json'),
    path('contratistas/editar/<int:id>/', views.editar_contratista_ajax, name='editar_contratista_ajax'),
    path('beneficiarios/', views.lista_beneficiarios, name='lista_beneficiarios'),
    path('beneficiarios/crear/', views.crear_beneficiario_ajax, name='crear_beneficiario_ajax'),
    path('beneficiarios/obtener/<int:id>/', views.obtener_beneficiario_json, name='obtener_beneficiario_json'),
    path('beneficiarios/editar/<int:id>/', views.editar_beneficiario_ajax, name='editar_beneficiario_ajax'),
    path('sua/', views.lista_sua, name='lista_sua'),
    path('sua/importar/', views.importar_sua_ajax, name='importar_sua_ajax'),
]
