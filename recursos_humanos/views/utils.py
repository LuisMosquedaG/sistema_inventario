import re
from panel.models import Empresa

def limpiar_basura_header(texto):
    """Elimina textos innecesarios del encabezado del SUA como convenios y versiones."""
    if not texto: return ""
    patrones = [
        r'Convenio\s+de\s+Re?mbolso:.*',
        r'Aportación\s+Patronal:.*',
        r'V\s?\d\.\d\.\d.*',
        r'Página:.*',
        r'Hoja:.*'
    ]
    for p in patrones:
        texto = re.sub(p, '', texto, flags=re.I)
    return texto.strip()

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

def get_sucursal_actual_id(request):
    """Auxiliar para obtener la sucursal de la sesión o el filtro."""
    suc_id = request.POST.get('sucursal') or request.GET.get('sucursal') or request.session.get('sucursal_id')
    return suc_id
