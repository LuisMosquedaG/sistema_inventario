from .models import Empresa
from preferencias.models import Sucursal, AsignacionSucursalUsuario

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
            
            # Filtrar sucursales si el usuario tiene asignaciones específicas
            asignadas = AsignacionSucursalUsuario.objects.filter(usuario=request.user)
            default_sucursal_id = None
            if asignadas.exists():
                sucursales_ids = list(asignadas.values_list('sucursal_id', flat=True))
                sucursales = sucursales.filter(id__in=sucursales_ids)
                
                # Buscar la predeterminada
                pred = asignadas.filter(es_predeterminada=True).first()
                if pred and pred.sucursal_id in sucursales_ids:
                    default_sucursal_id = pred.sucursal_id
                else:
                    default_sucursal_id = sucursales_ids[0]
            else:
                if sucursales.exists():
                    default_sucursal_id = sucursales.first().id
            
            # Obtener sucursal seleccionada de la sesión
            sucursal_id = request.session.get('sucursal_id')
            sucursal_actual = None
            
            if sucursal_id and sucursales.filter(id=sucursal_id).exists():
                sucursal_actual = int(sucursal_id)
            elif default_sucursal_id:
                sucursal_actual = default_sucursal_id
                request.session['sucursal_id'] = sucursal_actual
            
            return {
                'empresa': empresa,
                'sucursales_list': sucursales,
                'sucursal_actual_id': sucursal_actual
            }
        except Empresa.DoesNotExist:
            return {}
    return {}
