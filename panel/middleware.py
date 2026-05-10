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
