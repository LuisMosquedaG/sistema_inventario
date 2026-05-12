from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_cotizaciones, name='dashboard_cotizaciones'),
    path('crear/', views.crear_cotizacion, name='crear_cotizacion'),
    path('actualizar/<int:cotizacion_id>/', views.actualizar_cotizacion, name='actualizar_cotizacion'),
    path('aprobar/<int:cotizacion_id>/', views.aprobar_cotizacion, name='aprobar_cotizacion'),
    path('recotizar/<int:cotizacion_id>/', views.recotizar, name='recotizar_cotizacion'),
    path('cancelar/<int:cotizacion_id>/', views.cancelar_cotizacion, name='cancelar_cotizacion'),
    path('imprimir/<int:pk>/', views.imprimir_cotizacion, name='imprimir_cotizacion'),
]