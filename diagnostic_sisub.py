import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_inventario.settings')
django.setup()

from recursos_humanos.models import Empleado, Nomina, Contrato, Contratista
from django.db.models import Q
import re

def check_names(c_id=7):
    ct = Contratista.objects.get(id=c_id)
    emps = Empleado.objects.filter(contratos_asignados__contratista=ct).distinct()
    print(f"Analizando {emps.count()} empleados del contratista {ct.nombre_razon_social}...")
    
    matches = 0
    for e in emps:
        n1 = f"{e.nombre} {e.apellido_paterno} {e.apellido_materno}".strip().upper()
        n2 = f"{e.apellido_paterno} {e.apellido_materno} {e.nombre}".strip().upper()
        
        if Nomina.objects.filter(Q(nombre__icontains=n1) | Q(nombre__icontains=n2)).exists():
            matches += 1
            
    print(f"Resultado: {matches} de {emps.count()} empleados tienen al menos una nomina por coincidencia de NOMBRE.")

if __name__ == "__main__":
    check_names()
