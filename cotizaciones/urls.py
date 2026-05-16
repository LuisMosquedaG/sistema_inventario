from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_cotizaciones, name='dashboard_cotizaciones'),
    path('crear/', views.crear_cotizacion, name='crear_cotizacion'),
    path('importar/', views.importar_cotizaciones_ajax, name='importar_cotizaciones_ajax'),
    path('descargar-plantilla/', views.descargar_plantilla_cotizaciones, name='descargar_plantilla_cotizaciones'),
    path('exportar/', views.exportar_cotizaciones_excel, name='exportar_cotizaciones_excel'),
    
    # Se mantiene /cotizaciones/api/ por consistencia con el include('cotizaciones.urls')
    # Pero el JS busca /api/cotizaciones/. 
    # Para no romper el JS, agregamos una ruta que coincida con lo que espera.
    path('api/<int:cotizacion_id>/', views.obtener_cotizacion_json, name='obtener_cotizacion'),
    path('actualizar/<int:cotizacion_id>/', views.actualizar_cotizacion, name='actualizar_cotizacion'),
    
    path('aprobar/<int:cotizacion_id>/', views.aprobar_cotizacion, name='aprobar_cotizacion'),
    path('recotizar/<int:cotizacion_id>/', views.recotizar, name='recotizar'),
    path('cancelar/<int:cotizacion_id>/', views.cancelar_cotizacion, name='cancelar_cotizacion'),
    path('imprimir/<int:pk>/', views.imprimir_cotizacion, name='imprimir_cotizacion'),
]
