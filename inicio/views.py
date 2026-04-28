from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from panel.models import Empresa

def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

@login_required(login_url='/login/')
def dashboard_inicio(request):
    empresa_actual = get_empresa_actual(request)
    
    # Extraer nombre antes del @
    username_display = request.user.username.split('@')[0] if '@' in request.user.username else request.user.username

    contexto = {
        'empresa': empresa_actual,
        'username_display': username_display,
        'section': 'inicio'
    }
    return render(request, 'inicio/dashboard_inicio.html', contexto)
