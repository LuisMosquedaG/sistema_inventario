from django.urls import path
from . import views

urlpatterns = [
    path('empleados/', views.lista_empleados, name='lista_empleados'),
    path('empleados/crear/', views.crear_empleado_ajax, name='crear_empleado_ajax'),
    path('empleados/obtener/<int:id>/', views.obtener_empleado_json, name='obtener_empleado_json'),
    path('empleados/editar/<int:id>/', views.editar_empleado_ajax, name='editar_empleado_ajax'),
]
