from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Categoria, Subcategoria, ListaPrecioCosto
from panel.models import Empresa  # <--- IMPORTANTE

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

from preferencias.permissions import require_inventory_permission

# --- VISTA PRINCIPAL (LISTADO) ---
@login_required(login_url='/login/')
@require_inventory_permission('categorias', 'ver')
def lista_categorias(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # Filtrar por empresa
    categorias = Categoria.objects.filter(empresa=empresa_actual).prefetch_related('subcategorias').order_by('nombre')
    contexto = {
        'categorias': categorias
    }
    return render(request, 'dashboard_categorias.html', contexto)

# --- VISTA LISTAS MAESTRAS ---
@login_required(login_url='/login/')
@require_inventory_permission('listas', 'ver')
def lista_maestra_dashboard(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    listas = ListaPrecioCosto.objects.filter(empresa=empresa_actual).order_by('nombre')
    return render(request, 'dashboard_listas.html', {'listas': listas})

# --- API: CREAR LISTA ---
@login_required
@require_inventory_permission('listas', 'crear', json_response=True)
def api_crear_lista(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            nombre = request.POST.get('nombre')
            tipo = request.POST.get('tipo')
            porc = request.POST.get('porcentaje_extra', 0)
            monto = request.POST.get('monto_extra', 0)

            ListaPrecioCosto.objects.create(
                nombre=nombre, tipo=tipo,
                porcentaje_extra=porc, monto_extra=monto,
                empresa=empresa_actual
            )
            return JsonResponse({'success': True, 'message': 'Lista creada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- API: DETALLE LISTA ---
@login_required
@require_inventory_permission('listas', 'ver', json_response=True)
def api_detalle_lista(request, id):
    empresa_actual = get_empresa_actual(request)
    lista = get_object_or_404(ListaPrecioCosto, id=id, empresa=empresa_actual)
    return JsonResponse({
        'id': lista.id, 'nombre': lista.nombre, 'tipo': lista.tipo,
        'porcentaje_extra': str(lista.porcentaje_extra),
        'monto_extra': str(lista.monto_extra)
    })

# --- API: ACTUALIZAR LISTA ---
@login_required
@require_inventory_permission('listas', 'editar', json_response=True)
def api_actualizar_lista(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            lista = get_object_or_404(ListaPrecioCosto, id=id, empresa=empresa_actual)
            lista.nombre = request.POST.get('nombre')
            lista.tipo = request.POST.get('tipo')
            lista.porcentaje_extra = request.POST.get('porcentaje_extra', 0)
            lista.monto_extra = request.POST.get('monto_extra', 0)
            lista.save()
            return JsonResponse({'success': True, 'message': 'Lista actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- API: ELIMINAR LISTA ---
@login_required
@require_inventory_permission('listas', 'eliminar', json_response=True)
def api_eliminar_lista(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            lista = get_object_or_404(ListaPrecioCosto, id=id, empresa=empresa_actual)
            lista.delete()
            return JsonResponse({'success': True, 'message': 'Lista eliminada.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- API: CREAR CATEGORÍA ---
@login_required
@require_inventory_permission('categorias', 'crear', json_response=True)
def api_crear_categoria(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no detectada'})

            data = request.POST
            nombre_cat = data.get('nombre')
            lista_subcats = request.POST.getlist('subcategorias[]') 

            # 1. Crear Categoría asignando la empresa
            nueva_categoria = Categoria.objects.create(
                nombre=nombre_cat, 
                empresa=empresa_actual
            )

            # 2. Crear Subcategorías asignando la empresa
            for sub_nombre in lista_subcats:
                if sub_nombre.strip(): 
                    Subcategoria.objects.create(
                        categoria=nueva_categoria,
                        nombre=sub_nombre.strip(),
                        empresa=empresa_actual  # <--- ASIGNAR EMPRESA A LA SUBCATEGORÍA
                    )

            return JsonResponse({'success': True, 'message': 'Categoría creada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})

# --- API: DETALLE CATEGORÍA ---
@login_required
@require_inventory_permission('categorias', 'ver', json_response=True)
def api_detalle_categoria(request, id):
    try:
        empresa_actual = get_empresa_actual(request)
        
        # Seguridad: Verificar que la categoría pertenezca a la empresa
        categoria = get_object_or_404(Categoria, id=id, empresa=empresa_actual)
        
        subcats_data = [{'id': s.id, 'nombre': s.nombre} for s in categoria.subcategorias.all()]
        
        data = {
            'id': categoria.id,
            'nombre': categoria.nombre,
            'subcategorias': subcats_data
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': 'Categoría no encontrada o acceso denegado'}, status=404)

# --- API: ACTUALIZAR CATEGORÍA ---
@login_required
@require_inventory_permission('categorias', 'editar', json_response=True)
def api_actualizar_categoria(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            
            # Seguridad: Verificar propiedad
            categoria = get_object_or_404(Categoria, id=id, empresa=empresa_actual)
            
            data = request.POST
            categoria.nombre = data.get('nombre')
            categoria.save()
            
            # 1. Borrar subcategorías actuales
            categoria.subcategorias.all().delete()
            
            # 2. Crear las nuevas con la empresa correcta
            lista_subcats = request.POST.getlist('subcategorias[]')
            for sub_nombre in lista_subcats:
                if sub_nombre.strip():
                    Subcategoria.objects.create(
                        categoria=categoria,
                        nombre=sub_nombre.strip(),
                        empresa=empresa_actual
                    )

            return JsonResponse({'success': True, 'message': 'Categoría actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})

# --- API: ELIMINAR CATEGORÍA ---
@login_required
@require_inventory_permission('categorias', 'eliminar', json_response=True)
def api_eliminar_categoria(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            categoria = get_object_or_404(Categoria, id=id, empresa=empresa_actual)
            
            # Validar si tiene productos asociados antes de eliminar
            from core.models import Producto
            if Producto.objects.filter(categoria=categoria.nombre, empresa=empresa_actual).exists():
                return JsonResponse({'success': False, 'error': 'No se puede eliminar la categoría porque tiene productos asociados.'})
            
            categoria.delete()
            return JsonResponse({'success': True, 'message': 'Categoría eliminada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido.'})

# --- API: OBTENER SUBCATEGORÍAS POR NOMBRE DE CATEGORÍA ---
@login_required
@require_inventory_permission('categorias', 'ver', json_response=True)
def api_subcategorias_por_categoria(request):
    empresa_actual = get_empresa_actual(request)
    nombre_categoria = request.GET.get('categoria_nombre')
    subcategorias = []
    
    try:
        # Seguridad: Buscar categoría que coincida con NOMBRE Y EMPRESA
        # Esto evita confundir "Tecnología" de la Empresa A con "Tecnología" de la Empresa B
        cat = Categoria.objects.get(nombre=nombre_categoria, empresa=empresa_actual)
        subs = cat.subcategorias.all().values('nombre')
        subcategorias = list(subs)
    except Categoria.DoesNotExist:
        pass 

    return JsonResponse(subcategorias, safe=False)