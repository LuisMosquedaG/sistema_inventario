from .models import Empresa
from preferencias.models import Sucursal

def empresa_actual(request):
    """
    Context processor para inyectar la empresa actual y sus sucursales en todos los templates.
    """
    if not request.user.is_authenticated:
        return {}
    
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            empresa = Empresa.objects.get(subdominio=subdominio)
            sucursales = Sucursal.objects.filter(empresa=empresa).order_by('nombre')
            
            # Obtener sucursal seleccionada de la sesión
            sucursal_id = request.session.get('sucursal_id')
            sucursal_actual = None
            if sucursal_id:
                sucursal_actual = sucursal_id # Podríamos buscar el objeto, pero el ID suele bastar para la UI
            elif sucursales.exists():
                # Si no hay en sesión, tomar la primera por defecto
                sucursal_actual = sucursales.first().id
                request.session['sucursal_id'] = sucursal_actual
            
            return {
                'empresa': empresa,
                'sucursales_list': sucursales,
                'sucursal_actual_id': sucursal_actual
            }
        except Empresa.DoesNotExist:
            return {}
    return {}
