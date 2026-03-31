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
    aprobar_cotizacion, recotizar
)
from clientes.views import dashboard_clientes, crear_cliente, obtener_cliente_json, actualizar_cliente, obtener_contactos_cliente, guardar_contactos_cliente
from preferencias.views import (
    dashboard_preferencias, crear_usuario_ajax, crear_moneda_ajax,
    api_detalle_usuario, actualizar_usuario_ajax
)
from django.contrib.auth import views as auth_views 
from django.contrib.auth import logout
from django.shortcuts import redirect

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

urlpatterns = [
    path('panel/', include('panel.urls')),
    
    path('preferencias/crear-usuario/', crear_usuario_ajax, name='crear_usuario_ajax'),
    path('preferencias/api/usuario/<int:user_id>/', api_detalle_usuario, name='api_detalle_usuario'),
    path('preferencias/actualizar-usuario/<int:user_id>/', actualizar_usuario_ajax, name='actualizar_usuario_ajax'),
    path('preferencias/crear-moneda/', crear_moneda_ajax, name='crear_moneda_ajax'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', vista_salir, name='logout'),
    
    path('', dashboard_inventario, name='home'),
    
    # --- RUTAS PRINCIPALES DE MÓDULOS ---
    path('inventario/', dashboard_inventario, name='dash_inventario'),
    path('inventario/api/detalle-producto/<int:producto_id>/', api_detalle_producto_inventario, name='api_detalle_producto_inventario'),
    path('inventario/api/detalle-documento/', api_detalle_documento, name='api_detalle_documento'),
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
    path('api/crear-producto/', crear_producto_ajax, name='crear_producto_ajax'),
    path('api/producto/<int:producto_id>/', obtener_producto_json, name='obtener_producto'),
    path('api/actualizar-producto/<int:producto_id>/', actualizar_producto_ajax, name='actualizar_producto'),
    path('api/actualizar-precio-producto/<int:producto_id>/', actualizar_precio_producto, name='actualizar_precio_producto'),
    path('inventario/api/detalle-producto/<int:producto_id>/', api_detalle_producto_inventario, name='api_detalle_producto_inventario'),
    path('inventario/api/detalle-documento/', api_detalle_documento, name='api_detalle_documento'),

    path('vender/', include('core.urls')),
    path('inventario/', include('core.urls')),
    path('actividades/', include('actividades.urls')),
    
    path('recepciones/', include('recepciones.urls')),
    path('solicitudes-compras/', include('solicitudcompras.urls')),
    path('produccion/', include('produccion.urls')),
    
    path('inventario/', include('almacenes.urls')), 
    path('inventario/', include('categorias.urls')),
]