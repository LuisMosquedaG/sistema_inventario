from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_panel, name='dashboard_panel'),
    path('crear/', views.crear_empresa, name='crear_empresa'),
    path('eliminar/<int:empresa_id>/', views.eliminar_empresa, name='eliminar_empresa'),
    path('api/<int:empresa_id>/', views.obtener_empresa_json, name='obtener_empresa'),
    path('actualizar/<int:empresa_id>/', views.actualizar_empresa, name='actualizar_empresa'),
]