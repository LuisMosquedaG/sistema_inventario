from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Cliente, ContactoCliente
from .forms import ClienteForm
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from panel.models import Empresa

# --- 1. FUNCIÓN AYUDANTE ESTÁNDAR ---
def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

from core.models import Producto

@login_required(login_url='/login/')
def dashboard_clientes(request):
    empresa_actual = get_empresa_actual(request)
    
    # --- SEGURIDAD: Bloquear si no hay empresa (Eliminar fallback a 'all') ---
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    lista_clientes = Cliente.objects.filter(empresa=empresa_actual).order_by('-creado_en')
    todos_los_productos = Producto.objects.filter(empresa=empresa_actual)
    form = ClienteForm()
    
    contexto = {
        'clientes': lista_clientes,
        'productos': todos_los_productos,
        'form': form
    }
    return render(request, 'dashboard_clientes.html', contexto)

@login_required(login_url='/login/')
def crear_cliente(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'No se pudo detectar tu empresa.'}, status=403)
    
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.empresa = empresa_actual
            cliente.save()
            
            # --- SOPORTE PARA AJAX (MODAL RÁPIDO) ---
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'id': cliente.id, 
                    'nombre_completo': cliente.nombre_completo
                })
            
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('dashboard_clientes')
        else:
            lista_clientes = Cliente.objects.filter(empresa=empresa_actual)
            return render(request, 'dashboard_clientes.html', {'clientes': lista_clientes, 'form': form})
    
    # GET
    lista_clientes = Cliente.objects.filter(empresa=empresa_actual)
    form = ClienteForm()
    return render(request, 'dashboard_clientes.html', {'clientes': lista_clientes, 'form': form})

def obtener_cliente_json(request, cliente_id):
    """Devuelve los datos de un cliente para el modal de edición"""
    try:
        empresa_actual = get_empresa_actual(request)
        
        # --- MEJORA: Filtrar por empresa directo en la query ---
        # Si no existe el cliente con ese ID Y esa empresa, lanza 404 automáticamente.
        cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)

        data = model_to_dict(cliente)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': 'Cliente no encontrado'}, status=404)

def actualizar_cliente(request, cliente_id):
    """Guarda los cambios de un cliente existente"""
    empresa_actual = get_empresa_actual(request)
    
    # --- MEJORA: Validación en la query ---
    cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('dashboard_clientes')
        else:
            messages.error(request, 'Por favor corrige los errores.')
            return redirect('dashboard_clientes')
            
    return redirect('dashboard_clientes')

def obtener_contactos_cliente(request, cliente_id):
    """Lista los contactos de un cliente"""
    empresa_actual = get_empresa_actual(request)
    
    try:
        # --- MEJORA: Validar cliente en la query ---
        cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)

        contactos = ContactoCliente.objects.filter(cliente_id=cliente_id)
        data = []
        for c in contactos:
            data.append({
                'id': c.id,
                'nombre': c.nombre_completo,
                't1': c.telefono_1,
                't2': c.telefono_2,
                'e1': c.correo_1,
                'e2': c.correo_2,
                'notas': c.notas
            })
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse([], safe=False)

def guardar_contactos_cliente(request, cliente_id):
    """Guarda la lista de contactos"""
    empresa_actual = get_empresa_actual(request)
    
    try:
        # --- MEJORA: Validar cliente en la query ---
        cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa_actual)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'Cliente no encontrado o acceso denegado'})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            contactos_list = data.get('contactos', [])
            
            ids_recibidos = [int(c['id']) for c in contactos_list if c.get('id')]

            # Eliminar los que no vinieron en la lista (pero solo de este cliente validado)
            if ids_recibidos:
                ContactoCliente.objects.filter(cliente=cliente).exclude(id__in=ids_recibidos).delete()
            else:
                ContactoCliente.objects.filter(cliente=cliente).delete()
            
            count = 0
            for cont_data in contactos_list:
                if cont_data.get('id'):
                    contacto = ContactoCliente.objects.get(id=cont_data['id'], cliente=cliente)
                    contacto.nombre_completo = cont_data['nombre']
                    contacto.telefono_1 = cont_data['t1']
                    contacto.telefono_2 = cont_data['t2']
                    contacto.correo_1 = cont_data['e1']
                    contacto.correo_2 = cont_data['e2']
                    contacto.notas = cont_data['notas']
                    contacto.save()
                else:
                    ContactoCliente.objects.create(
                        cliente=cliente,
                        nombre_completo=cont_data['nombre'],
                        telefono_1=cont_data['t1'],
                        telefono_2=cont_data['t2'],
                        correo_1=cont_data['e1'],
                        correo_2=cont_data['e2'],
                        notas=cont_data['notas']
                    )
                count += 1
            
            return JsonResponse({'success': True, 'count': count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})