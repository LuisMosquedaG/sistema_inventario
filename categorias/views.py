from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Categoria, Subcategoria
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

# --- VISTA PRINCIPAL (LISTADO) ---
@login_required(login_url='/login/')
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

# --- API: CREAR CATEGORÍA ---
@login_required
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

# --- API: OBTENER SUBCATEGORÍAS POR NOMBRE DE CATEGORÍA ---
@login_required
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