from django.contrib import admin
from django.urls import path, include

# --- TUS IMPORTS EXISTENTES ---
from core.views import (
    dashboard_inventario, crear_producto_ajax, obtener_producto_json, actualizar_producto_ajax,
    api_detalle_producto_inventario,
    api_detalle_documento,
    actualizar_precio_producto
)
# NOTA: Eliminamos 'dashboard_compras' de aquí porque ahora vive en la app 'compras'
from ventas.views import dashboard_ventas     
from cotizaciones.views import (
    dashboard_cotizaciones, crear_cotizacion, 
    obtener_cotizacion_json, actualizar_cotizacion, 
    aprobar_cotizacion, recotizar, cancelar_cotizacion
)
from clientes.views import dashboard_clientes, crear_cliente, obtener_cliente_json, actualizar_cliente, obtener_contactos_cliente, guardar_contactos_cliente
from preferencias.views import (
    dashboard_preferencias, crear_usuario_ajax, crear_moneda_ajax,
    api_detalle_usuario, actualizar_usuario_ajax,
    api_detalle_moneda, actualizar_moneda_ajax,
    exportar_datos_zip, reiniciar_transacciones_ajax, reiniciar_catalogos_ajax
)
from django.contrib.auth import views as auth_views 
from django.contrib.auth import logout
from django.shortcuts import render, redirect

# --- IMPORT DE PROVEEDORES ---
from proveedores.views import (
    dashboard_proveedores, crear_proveedor, 
    obtener_proveedor_json, actualizar_proveedor, 
    desactivar_proveedor
)

from solicitudcompras import views as sc_views

def vista_salir(request):
    logout(request)
    return redirect('login')

from django.views.generic import TemplateView

def redirect_after_login(request):
    if request.user.username == 'madmin@crossoversuite':
        return redirect('dashboard_panel')
    return redirect('dashboard_inicio')

def index_view(request):
    if request.user.is_authenticated:
        return redirect_after_login(request)
    return render(request, 'landing.html')

urlpatterns = [
    path('', index_view, name='landing'),
    path('inicio/', include('inicio.urls')),
    path('login-redirect/', redirect_after_login, name='login_redirect'),
    path('panel/', include('panel.urls')),
    
    path('preferencias/crear-usuario/', crear_usuario_ajax, name='crear_usuario_ajax'),
    path('preferencias/api/usuario/<int:user_id>/', api_detalle_usuario, name='api_detalle_usuario'),
    path('preferencias/actualizar-usuario/<int:user_id>/', actualizar_usuario_ajax, name='actualizar_usuario_ajax'),
    path('preferencias/crear-moneda/', crear_moneda_ajax, name='crear_moneda_ajax'),
    path('preferencias/api/moneda/<int:moneda_id>/', api_detalle_moneda, name='api_detalle_moneda'),
    path('preferencias/actualizar-moneda/<int:moneda_id>/', actualizar_moneda_ajax, name='actualizar_moneda_ajax'),
    
    # --- RUTAS DE GESTIÓN DE DATOS ---
    path('preferencias/exportar-datos/', exportar_datos_zip, name='exportar_datos_zip'),
    path('preferencias/reiniciar-transacciones/', reiniciar_transacciones_ajax, name='reiniciar_transacciones_ajax'),
    path('preferencias/reiniciar-catalogos/', reiniciar_catalogos_ajax, name='reiniciar_catalogos_ajax'),
    
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', vista_salir, name='logout'),
    
    # --- RUTAS PRINCIPALES DE MÓDULOS ---
    path('inventario/', dashboard_inventario, name='dash_inventario'),
    path('ventas/', include('ventas.urls')),
    
    # --- CORRECCIÓN COMPRAS ---
    # Ahora apunta directamente al archivo urls.py de la app compras
    path('compras/', include('compras.urls')),
    path('pedidos/', include('pedidos.urls')),    
    path('preferencias/', dashboard_preferencias, name='dashboard_preferencias'),
    
    # --- RUTAS DE COTIZACIONES ---
    path('cotizaciones/crear/', crear_cotizacion, name='crear_cotizacion'),
    path('api/cotizaciones/<int:cotizacion_id>/', obtener_cotizacion_json, name='obtener_cotizacion'),
    path('cotizaciones/actualizar/<int:cotizacion_id>/', actualizar_cotizacion, name='actualizar_cotizacion'),
    path('cotizaciones/aprobar/<int:cotizacion_id>/', aprobar_cotizacion, name='aprobar_cotizacion'),
    path('cotizaciones/recotizar/<int:cotizacion_id>/', recotizar, name='recotizar'),
    path('cotizaciones/cancelar/<int:cotizacion_id>/', cancelar_cotizacion, name='cancelar_cotizacion'),
    path('cotizaciones/', dashboard_cotizaciones, name='dashboard_cotizaciones'),

    # --- RUTAS DE CLIENTES ---
    path('clientes/', dashboard_clientes, name='dashboard_clientes'),
    path('clientes/crear/', crear_cliente, name='crear_cliente'),
    path('api/clientes/<int:cliente_id>/', obtener_cliente_json, name='obtener_cliente'),
    path('clientes/actualizar/<int:cliente_id>/', actualizar_cliente, name='actualizar_cliente'),
    path('api/clientes/<int:cliente_id>/contactos/', obtener_contactos_cliente, name='obtener_contactos'),
    path('api/clientes/guardar/<int:cliente_id>/', guardar_contactos_cliente, name='guardar_contactos'),

    # --- RUTAS DE PROVEEDORES ---
    path('proveedores/', dashboard_proveedores, name='dashboard_proveedores'),
    path('proveedores/crear/', crear_proveedor, name='crear_proveedor'),
    path('api/proveedores/<int:proveedor_id>/', obtener_proveedor_json, name='obtener_proveedor'),
    path('proveedores/actualizar/<int:proveedor_id>/', actualizar_proveedor, name='actualizar_proveedor'),
    path('proveedores/desactivar/<int:proveedor_id>/', desactivar_proveedor, name='desactivar_proveedor'),

    # --- CORE Y OTROS INCLUDES ---
    # (Se eliminaron rutas duplicadas que ya vienen en core.urls)
    path('vender/', include('core.urls')),
    path('inventario/', include('core.urls')),
    path('actividades/', include('actividades.urls')),
    
    path('recepciones/', include('recepciones.urls')),
    path('solicitudes-compras/', include('solicitudcompras.urls')),
    path('produccion/', include('produccion.urls')),
    
    path('inventario/', include('almacenes.urls')), 
    path('inventario/', include('categorias.urls')),
]

# Servir archivos media en desarrollo
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
