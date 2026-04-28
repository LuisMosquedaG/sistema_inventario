from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Proveedor, SucursalProveedor
from compras.models import OrdenCompra  # <--- PARA VERIFICAR HISTORIAL
from panel.models import Empresa
from django.utils import timezone
import json

# --- 1. FUNCIÓN AYUDANTE RESTAURADA (Igual a Clientes) ---
def get_empresa_actual(request):
    """
    Detecta la empresa basándose en el username del usuario logueado.
    Ejemplo: usuario@empresa.com -> detecta subdominio 'empresa'
    """
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

from django.db.models import Q
from django.core.paginator import Paginator

# --- 2. DASHBOARD PRINCIPAL (LISTADO) ---
@login_required(login_url='/login/')
def dashboard_proveedores(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # --- LÓGICA DE FILTRADO ---
    q = request.GET.get('q', '')
    proveedor_id = request.GET.get('proveedor_id', '')
    sucursal = request.GET.get('sucursal', '')
    email = request.GET.get('email', '')
    estado = request.GET.get('estado', '')

    proveedores_qs = Proveedor.objects.filter(empresa=empresa_actual).prefetch_related('sucursales').order_by('-creado_en')

    if q:
        proveedores_qs = proveedores_qs.filter(
            Q(razon_social__icontains=q) |
            Q(rfc__icontains=q) |
            Q(contacto_nombre__icontains=q) |
            Q(contacto_email__icontains=q) |
            Q(domicilio__icontains=q)
        ).distinct()

    if proveedor_id and proveedor_id != 'all':
        proveedores_qs = proveedores_qs.filter(id=proveedor_id)
    
    if sucursal:
        proveedores_qs = proveedores_qs.filter(sucursales__nombre__icontains=sucursal).distinct()

    if email:
        proveedores_qs = proveedores_qs.filter(contacto_email__icontains=email)

    if estado:
        proveedores_qs = proveedores_qs.filter(estado=estado)

    # Para el buscador visual de proveedor
    proveedor_nombre_display = ""
    if proveedor_id and proveedor_id != 'all':
        try:
            p_obj = Proveedor.objects.get(id=proveedor_id, empresa=empresa_actual)
            proveedor_nombre_display = p_obj.razon_social
        except:
            pass

    filtros = {
        'q': q,
        'proveedor_id': proveedor_id,
        'proveedor_nombre': proveedor_nombre_display,
        'sucursal': sucursal,
        'email': email,
        'estado': estado
    }
    # --- FIN LÓGICA DE FILTRADO ---

    paginator = Paginator(proveedores_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    todos_los_proveedores = Proveedor.objects.filter(empresa=empresa_actual)

    contexto = {
        'page_obj': page_obj,
        'todos_los_proveedores': todos_los_proveedores,
        'filtros': filtros,
        'section': 'proveedores',
        'titulo': 'Gestión de Proveedores'
    }
    return render(request, 'dashboard_proveedores.html', contexto)

# --- 3. CREAR PROVEEDOR ---
@login_required
@transaction.atomic
def crear_proveedor(request):
    if request.method == 'POST':
        try:
            # Usamos la función helper
            empresa_actual = get_empresa_actual(request)

            # VALIDACIÓN CRÍTICA
            if not empresa_actual:
                return JsonResponse({
                    'success': False, 
                    'error': 'El sistema no pudo detectar tu empresa basándose en tu usuario.'
                })

            # 1. Recibir datos
            razon_social = request.POST.get('razon_social')
            rfc = request.POST.get('rfc')
            cp = request.POST.get('cp')
            domicilio = request.POST.get('domicilio')
            contacto_nombre = request.POST.get('contacto_nombre')
            contacto_telefono = request.POST.get('contacto_telefono')
            contacto_email = request.POST.get('contacto_email')
            
            # Validar RFC duplicado DENTRO de esta empresa (aislamiento correcto)
            if Proveedor.objects.filter(rfc=rfc, empresa=empresa_actual).exists():
                return JsonResponse({'success': False, 'error': 'Ya existe un proveedor con ese RFC en tu empresa.'})

            # 2. Crear el proveedor asignando la empresa detectada
            proveedor = Proveedor.objects.create(
                razon_social=razon_social,
                rfc=rfc,
                cp=cp,
                domicilio=domicilio,
                contacto_nombre=contacto_nombre,
                contacto_telefono=contacto_telefono,
                contacto_email=contacto_email,
                empresa=empresa_actual  # <--- ASIGNACIÓN EXPLÍCITA
            )

            # 3. Guardar sucursales dinámicas
            sucursal_nombres = request.POST.getlist('sucursal_nombre[]')
            sucursal_direcciones = request.POST.getlist('sucursal_direccion[]')

            for nom, dir in zip(sucursal_nombres, sucursal_direcciones):
                if nom.strip():
                    SucursalProveedor.objects.create(
                        proveedor=proveedor,
                        nombre=nom.strip(),
                        direccion=dir.strip()
                    )

            return JsonResponse({'success': True, 'message': 'Proveedor creado correctamente.'})

        except Exception as e:
            print(f"ERROR AL CREAR PROVEEDOR: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- 4. OBTENER DATOS (JSON PARA EDITAR) ---
def obtener_proveedor_json(request, proveedor_id):
    try:
        # Obtenemos empresa por el usuario
        empresa_actual = get_empresa_actual(request)
        
        proveedor = get_object_or_404(Proveedor, id=proveedor_id, empresa=empresa_actual)
        
        # Jalar sucursales
        sucursales = list(proveedor.sucursales.all().values('id', 'nombre', 'direccion'))
        
        data = {
            'id': proveedor.id,
            'razon_social': proveedor.razon_social,
            'rfc': proveedor.rfc,
            'cp': proveedor.cp,
            'domicilio': proveedor.domicilio,
            'contacto_nombre': proveedor.contacto_nombre,
            'contacto_telefono': proveedor.contacto_telefono,
            'contacto_email': proveedor.contacto_email,
            'estado': proveedor.estado,
            'sucursales': sucursales
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

# --- 5. ACTUALIZAR PROVEEDOR ---
@login_required
@transaction.atomic
def actualizar_proveedor(request, proveedor_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            proveedor = get_object_or_404(Proveedor, id=proveedor_id, empresa=empresa_actual)
            
            proveedor.razon_social = request.POST.get('razon_social')
            proveedor.rfc = request.POST.get('rfc')
            proveedor.cp = request.POST.get('cp')
            proveedor.domicilio = request.POST.get('domicilio')
            proveedor.contacto_nombre = request.POST.get('contacto_nombre')
            proveedor.contacto_telefono = request.POST.get('contacto_telefono')
            proveedor.contacto_email = request.POST.get('contacto_email')
            proveedor.estado = request.POST.get('estado', proveedor.estado)
            
            proveedor.save()

            # Actualizar sucursales (Limpiar y recrear)
            proveedor.sucursales.all().delete()
            sucursal_nombres = request.POST.getlist('sucursal_nombre[]')
            sucursal_direcciones = request.POST.getlist('sucursal_direccion[]')

            for nom, dir in zip(sucursal_nombres, sucursal_direcciones):
                if nom.strip():
                    SucursalProveedor.objects.create(
                        proveedor=proveedor,
                        nombre=nom.strip(),
                        direccion=dir.strip()
                    )
            
            return JsonResponse({'success': True, 'message': 'Proveedor actualizado correctamente.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})

# --- 6. ELIMINAR O DESACTIVAR PROVEEDOR ---
def desactivar_proveedor(request, proveedor_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            proveedor = get_object_or_404(Proveedor, id=proveedor_id, empresa=empresa_actual)
            
            # Verificar si tiene Órdenes de Compra
            tiene_historial = OrdenCompra.objects.filter(proveedor=proveedor).exists()

            if tiene_historial:
                # Solo desactivar
                proveedor.estado = 'inactivo'
                proveedor.save()
                return JsonResponse({
                    'success': True, 
                    'message': 'El proveedor tiene órdenes de compra asociadas, por lo que ha sido marcado como INACTIVO.'
                })
            else:
                # Borrado físico
                proveedor.delete()
                return JsonResponse({
                    'success': True, 
                    'message': 'El proveedor no tiene historial y ha sido ELIMINADO permanentemente.'
                })
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})
