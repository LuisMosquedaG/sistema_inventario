from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction # <--- ESTE FALTABA
from .models import Moneda
from panel.models import Empresa

# --- HELPER MULTI-TENANCY ---
def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

# --- VISTA PRINCIPAL (MODIFICADA) ---
@login_required(login_url='/login/')
def dashboard_preferencias(request):
    empresa_actual = get_empresa_actual(request)
    
    # El usuario Master (madmin) puede entrar aquí pero sin empresa asociada
    is_master = (request.user.username == 'madmin@crossoversuite')
    
    if not empresa_actual and not is_master:
        return render(request, 'error_sin_empresa.html', status=403)

    seccion_activa = request.GET.get('section', 'usuarios')
    
    contexto = {
        'seccion': seccion_activa,
        'empresa': empresa_actual,
    }

    if seccion_activa == 'usuarios':
        # --- REGLA 1 y 3: Filtrar por empresa, ocultar madmin y sadmins ---
        qs = User.objects.exclude(username='madmin@crossoversuite')
        
        # Ocultar todos los sadmin@...
        qs = qs.exclude(username__startswith='sadmin@')
        
        if not is_master:
            # Solo ver usuarios que tengan el prefijo de la empresa (ej: @demo)
            qs = qs.filter(username__contains=f"@{empresa_actual.subdominio}")
            
        contexto['usuarios'] = qs.order_by('-id')
    
    elif seccion_activa == 'monedas':
        contexto['monedas'] = Moneda.objects.filter(empresa=empresa_actual)

    return render(request, 'dashboard_preferencias.html', contexto)

# --- API: CREAR MONEDA ---
@login_required
def crear_moneda_ajax(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            nombre = request.POST.get('nombre')
            siglas = request.POST.get('siglas')
            simbolo = request.POST.get('simbolo')
            factor = request.POST.get('factor', 1.0)

            Moneda.objects.create(
                nombre=nombre,
                siglas=siglas,
                simbolo=simbolo,
                factor=factor,
                responsable=request.user,
                empresa=empresa_actual
            )
            return JsonResponse({'success': True, 'message': 'Moneda registrada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_detalle_moneda(request, moneda_id):
    empresa_actual = get_empresa_actual(request)
    moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
    return JsonResponse({
        'success': True,
        'id': moneda.id,
        'nombre': moneda.nombre,
        'siglas': moneda.siglas,
        'simbolo': moneda.simbolo,
        'factor': str(moneda.factor)
    })

@login_required
def actualizar_moneda_ajax(request, moneda_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
            moneda.nombre = request.POST.get('nombre')
            moneda.siglas = request.POST.get('siglas')
            moneda.simbolo = request.POST.get('simbolo')
            moneda.factor = request.POST.get('factor')
            moneda.save()
            return JsonResponse({'success': True, 'message': 'Moneda actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- VISTA: CREAR USUARIO (REGLA 2: PREFIJO AUTOMÁTICO) ---
@login_required(login_url='/login/')
def crear_usuario_ajax(request):
    if request.method == 'POST':
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'success': False, 'error': 'No se detectó empresa para asignar el prefijo.'})

        username_corto = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password1')
        rol = request.POST.get('rol')

        if not username_corto or not password:
            return JsonResponse({'success': False, 'error': 'El usuario y la contraseña son obligatorios.'})

        # --- REGLA 2: ASIGNAR PREFIJO AUTOMÁTICO ---
        # Si el usuario puso "juan", se guarda como "juan@demo"
        username_completo = f"{username_corto}@{empresa_actual.subdominio}"

        if User.objects.filter(username=username_completo).exists():
            return JsonResponse({'success': False, 'error': f'El usuario {username_completo} ya existe.'})

        try:
            user = User.objects.create_user(username=username_completo, email=email, password=password)
            
            if rol == 'admin':
                user.is_staff = True
                user.is_superuser = True
            else:
                user.is_staff = True
                user.is_superuser = False 

            user.save()
            return JsonResponse({'success': True, 'message': f'Usuario {username_completo} creado correctamente.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_detalle_usuario(request, user_id):
    empresa_actual = get_empresa_actual(request)
    user = get_object_or_404(User, id=user_id)
    
    if f"@{empresa_actual.subdominio}" not in user.username:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)

    return JsonResponse({
        'success': True,
        'id': user.id,
        'username_corto': user.username.split('@')[0],
        'email': user.email,
        'rol': 'admin' if user.is_superuser else 'staff'
    })

@login_required
@transaction.atomic
def actualizar_usuario_ajax(request, user_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            user = get_object_or_404(User, id=user_id)
            
            if f"@{empresa_actual.subdominio}" not in user.username:
                return JsonResponse({'success': False, 'error': 'Acceso denegado'})

            user.email = request.POST.get('email')
            rol = request.POST.get('rol')
            if rol == 'admin':
                user.is_staff = True; user.is_superuser = True
            else:
                user.is_staff = True; user.is_superuser = False
            
            passw = request.POST.get('password1')
            if passw: user.set_password(passw)
            
            user.save()
            return JsonResponse({'success': True, 'message': 'Usuario actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})