from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse  # <--- FALTABA ESTE (Para eliminar_empresa)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User  # <--- FALTABA ESTE (Para crear los usuarios sadmin/admin)
from .models import Empresa
from django.contrib import messages

# --- FUNCIÓN DE VERIFICACIÓN ---
# Solo permite entrar si el username coincide exactamente
def check_master_admin(user):
    return user.username == 'madmin@crossoversuite'

# --- VISTA DASHBOARD DEL PANEL ---
@login_required(login_url='/login/')
@user_passes_test(check_master_admin, login_url='/inventario/')
def dashboard_panel(request):
    empresas = Empresa.objects.all().order_by('-fecha_alta')
    
    contexto = {
        'empresas': empresas
    }
    return render(request, 'panel/dashboard_panel.html', contexto)

@login_required(login_url='/login/')
@user_passes_test(check_master_admin, login_url='/inventario/')
def crear_empresa(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        subdominio = request.POST.get('subdominio').strip().lower() 
        correo = request.POST.get('correo_contacto')
        estado_str = request.POST.get('activa', 'True')
        
        # Nuevos campos
        nombre_contacto = request.POST.get('nombre_contacto')
        telefono_contacto = request.POST.get('telefono_contacto')
        logo = request.FILES.get('logo')

        # Campos de dirección
        calle = request.POST.get('calle')
        numero = request.POST.get('numero')
        colonia = request.POST.get('colonia')
        estado = request.POST.get('estado')
        cp = request.POST.get('cp')

        try:
            # 1. Crear la Empresa (Tenant)
            nueva_empresa = Empresa.objects.create(
                nombre=nombre,
                subdominio=subdominio,
                correo_contacto=correo,
                nombre_contacto=nombre_contacto,
                telefono_contacto=telefono_contacto,
                logo=logo,
                calle=calle,
                numero=numero,
                colonia=colonia,
                estado=estado,
                cp=cp,
                activa=(estado_str == 'True')
            )

            # 2. Lógica para crear usuarios automáticamente
            # Definimos las contraseñas
            pass_defecto = "paso1234"
            
            usuarios_creados = []
            errores_usuarios = []

            # --- CREAR SUPER ADMIN (sadmin@prefijo) ---
            username_sadmin = f"sadmin@{subdominio}"
            if not User.objects.filter(username=username_sadmin).exists():
                try:
                    sadmin = User.objects.create_user(
                        username=username_sadmin,
                        password=pass_defecto,
                        email=correo
                    )
                    sadmin.is_superuser = True
                    sadmin.is_staff = True
                    sadmin.save()
                    usuarios_creados.append(username_sadmin)
                except Exception as e:
                    errores_usuarios.append(f"Error creando {username_sadmin}: {str(e)}")
            else:
                errores_usuarios.append(f"El usuario {username_sadmin} ya existe.")

            # --- CREAR ADMIN ESTÁNDAR (admin@prefijo) ---
            username_admin = f"admin@{subdominio}"
            if not User.objects.filter(username=username_admin).exists():
                try:
                    admin = User.objects.create_user(
                        username=username_admin,
                        password=pass_defecto
                    )
                    admin.is_staff = True
                    admin.is_superuser = False
                    admin.save()
                    usuarios_creados.append(username_admin)
                except Exception as e:
                    errores_usuarios.append(f"Error creando {username_admin}: {str(e)}")
            else:
                errores_usuarios.append(f"El usuario {username_admin} ya existe.")

            # Mensajes de feedback
            if errores_usuarios:
                messages.warning(request, f'Empresa creada, pero hubo advertencias: {", ".join(errores_usuarios)}')
            
            if usuarios_creados:
                messages.success(request, f'Empresa "{nombre}" creada. Usuarios generados: {", ".join(usuarios_creados)} (Pass: {pass_defecto})')
            else:
                messages.info(request, 'Empresa creada, pero no se generaron usuarios nuevos (ya existían).')

            return redirect('dashboard_panel')
            
        except Exception as e:
            messages.error(request, f'Error al crear empresa: {str(e)}')
            
    return redirect('dashboard_panel')

@login_required(login_url='/login/')
@user_passes_test(check_master_admin, login_url='/inventario/')
def eliminar_empresa(request, empresa_id):
    if request.method == 'POST':
        try:
            empresa = get_object_or_404(Empresa, id=empresa_id)
            
            # --- NOTA PARA FUTURO: MULTI-TENANCIA COMPLETA ---
            # Cuando tus modelos Cliente, Venta, etc. tengan un campo ForeignKey a 'Empresa',
            # aquí agregarías la lógica para borrarlos en cascada manualmente si no usas on_delete=CASCADE.
            # Ejemplo:
            # Cliente.objects.filter(empresa=empresa).delete()
            # Venta.objects.filter(empresa=empresa).delete()
            
            nombre = empresa.nombre
            empresa.delete()
            
            return JsonResponse({'success': True, 'message': f'Empresa {nombre} eliminada.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

# --- VISTA OBTENER DATOS (Para llenar el modal) ---
@login_required(login_url='/login/')
@user_passes_test(check_master_admin, login_url='/inventario/')
def obtener_empresa_json(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id)
    data = {
        'id': empresa.id,
        'nombre': empresa.nombre,
        'subdominio': empresa.subdominio,
        'correo_contacto': empresa.correo_contacto,
        'nombre_contacto': empresa.nombre_contacto or '',
        'telefono_contacto': empresa.telefono_contacto or '',
        'logo_url': empresa.logo.url if empresa.logo else '',
        'calle': empresa.calle or '',
        'numero': empresa.numero or '',
        'colonia': empresa.colonia or '',
        'estado': empresa.estado or '',
        'cp': empresa.cp or '',
        'activa': 'True' if empresa.activa else 'False',
    }
    return JsonResponse(data)

# --- VISTA ACTUALIZAR EMPRESA ---
@login_required(login_url='/login/')
@user_passes_test(check_master_admin, login_url='/inventario/')
def actualizar_empresa(request, empresa_id):
    if request.method == 'POST':
        try:
            empresa = get_object_or_404(Empresa, id=empresa_id)

            # Actualizamos los campos
            empresa.nombre = request.POST.get('nombre')
            empresa.subdominio = request.POST.get('subdominio').strip().lower()
            empresa.correo_contacto = request.POST.get('correo_contacto')

            # Nuevos campos
            empresa.nombre_contacto = request.POST.get('nombre_contacto')
            empresa.telefono_contacto = request.POST.get('telefono_contacto')
            
            # Campos de dirección
            empresa.calle = request.POST.get('calle')
            empresa.numero = request.POST.get('numero')
            empresa.colonia = request.POST.get('colonia')
            empresa.estado = request.POST.get('estado')
            empresa.cp = request.POST.get('cp')

            if request.FILES.get('logo'):
                empresa.logo = request.FILES.get('logo')

            empresa.activa = (request.POST.get('activa') == 'True')
            empresa.save()
            return JsonResponse({'success': True, 'message': 'Empresa actualizada correctamente.'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})