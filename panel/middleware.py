from django.utils import timezone
from .models import Empresa
from datetime import date, timedelta

class LicenseAutoRenewalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            username = request.user.username
            if '@' in username:
                subdominio = username.split('@')[1]
                try:
                    empresa = Empresa.objects.get(subdominio=subdominio)
                    
                    if empresa.fecha_vencimiento_licencia:
                        today = date.today()
                        
                        # Si ya venció la licencia (hoy es estrictamente mayor al vencimiento)
                        while today > empresa.fecha_vencimiento_licencia:
                            # Avanzar al siguiente periodo automáticamente
                            old_vence = empresa.fecha_vencimiento_licencia
                            empresa.fecha_inicio_licencia = old_vence
                            
                            # Calcular siguiente mes
                            year = old_vence.year
                            month = old_vence.month + 1
                            if month > 12:
                                month = 1
                                year += 1
                            
                            # Manejar el día (si el día es 31 y el siguiente mes tiene 30, etc)
                            # Para simplificar y evitar errores de calendario, usamos el mismo día si es posible
                            day = old_vence.day
                            # Intentamos crear la fecha, si falla bajamos el día hasta que sea válida (ej: 31 de marzo -> 30 de abril)
                            import calendar
                            last_day = calendar.monthrange(year, month)[1]
                            if day > last_day:
                                day = last_day
                                
                            empresa.fecha_vencimiento_licencia = date(year, month, day)
                            empresa.save()
                            
                except Empresa.DoesNotExist:
                    pass
                except Exception:
                    pass

        response = self.get_response(request)
        return response

from django.shortcuts import render
from django.http import HttpResponseForbidden

class TenantStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. EXENTAR RUTAS CRÍTICAS (Siempre accesibles)
        exempt_paths = ['/panel/', '/admin/', '/login/', '/logout/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in exempt_paths):
            return self.get_response(request)

        if request.user.is_authenticated:
            username = request.user.username.lower()
            
            # 2. BYPASS: Solo el Administrador Maestro o los Súper Admins de cada empresa (sadmin@)
            # Esto cumple la regla: "solo el sadmin tiene acceso normal"
            if username == 'madmin@crossoversuite' or username.startswith('sadmin@'):
                return self.get_response(request)

            if '@' in username:
                parts = username.split('@')
                subdominio = parts[1]
                
                try:
                    empresa = Empresa.objects.get(subdominio=subdominio)
                    
                    # 3. REGLA: INACTIVA (Bloqueo Total)
                    if empresa.estado_servicio == 'inactiva':
                        return render(request, 'error_tenant_status.html', {
                            'empresa': empresa,
                            'mensaje': 'Esta cuenta se encuentra desactivada temporalmente. Favor de contactar a soporte.'
                        }, status=403)

                    # 4. REGLA: SUSPENDIDA (Bloqueo de Escritura)
                    elif empresa.estado_servicio == 'suspendida':
                        # Permitir solo navegación (GET)
                        if request.method != 'GET':
                            # Si es una petición AJAX/JSON, devolvemos un JSON con el código 403
                            # para que el frontend pueda manejar el redireccionamiento o mostrar el error.
                            is_ajax = (
                                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                                'application/json' in request.headers.get('Accept', '')
                            )
                            
                            if is_ajax:
                                from django.http import JsonResponse
                                return JsonResponse({
                                    'success': False, 
                                    'suspended': True,
                                    'error': 'SERVICIO SUSPENDIDO: El sistema se encuentra en modo de consulta (Solo Lectura).'
                                }, status=403)
                            
                            return render(request, 'error_tenant_status.html', {
                                'empresa': empresa,
                                'mensaje': 'Servicio Suspendido: El sistema se encuentra en modo de consulta (Solo Lectura). No se pueden realizar cambios.'
                            }, status=403)

                except Empresa.DoesNotExist:
                    pass
        
        return self.get_response(request)
