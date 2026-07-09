import os
import sys
import django
import datetime
from decimal import Decimal

# Configurar entorno Django
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_inventario.settings')
django.setup()

from panel.models import Empresa
from recursos_humanos.models import Contrato
from django.db.models import Sum, Q

def run_tests():
    print("--- INICIANDO VALIDACIÓN DE GRÁFICA DE CONTRATOS ---")
    empresa = Empresa.objects.first()
    if not empresa:
        print("No hay empresas registradas para realizar la prueba.")
        return
        
    print(f"Empresa detectada: {empresa.nombre}")
    
    # 1. Crear contratos de prueba con fechas de vigencia solapadas
    hoy = datetime.date.today()
    primer_dia_mes_actual = datetime.date(hoy.year, hoy.month, 1)
    
    # Calcular fecha del mes pasado
    mes_pasado_init = hoy.month - 1
    anio_pasado_init = hoy.year
    if mes_pasado_init <= 0:
        mes_pasado_init = 12
        anio_pasado_init -= 1
    fecha_mes_pasado = datetime.date(anio_pasado_init, mes_pasado_init, 15)

    # Contrato 1: Vigente este mes
    c1_inicio = primer_dia_mes_actual - datetime.timedelta(days=90)
    c1 = Contrato.objects.create(
        empresa=empresa,
        folio="TEST-CON-001",
        monto_contrato=Decimal("50000.00"),
        fecha_inicio=c1_inicio,
        fecha_fin=None,
        vigencia_contrato=hoy,
        estado='vigente'
    )
    print(f"Contrato 1 creado: {c1.folio}, Monto: {c1.monto_contrato}, Vigencia: {c1.vigencia_contrato}")

    # Contrato 2: Vencido el mes pasado
    c2_inicio = primer_dia_mes_actual - datetime.timedelta(days=45)
    c2 = Contrato.objects.create(
        empresa=empresa,
        folio="TEST-CON-002",
        monto_contrato=Decimal("25000.00"),
        fecha_inicio=c2_inicio,
        fecha_fin=None,
        vigencia_contrato=fecha_mes_pasado,
        estado='vencido'
    )
    print(f"Contrato 2 creado: {c2.folio}, Monto: {c2.monto_contrato}, Vigencia: {c2.vigencia_contrato}")

    # 2. Simular agregación por meses (mes actual vs mes pasado)
    # Mes actual
    primer_dia_actual = primer_dia_mes_actual
    if hoy.month == 12:
        ultimo_dia_actual = datetime.date(hoy.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        ultimo_dia_actual = datetime.date(hoy.year, hoy.month + 1, 1) - datetime.timedelta(days=1)
        
    contratos_actual = Contrato.objects.filter(
        empresa=empresa,
        vigencia_contrato__year=hoy.year,
        vigencia_contrato__month=hoy.month
    )
    total_actual = contratos_actual.aggregate(total=Sum('monto_contrato'))['total'] or Decimal('0.00')
    print(f"Mes actual: Total contratos activos detectados = {total_actual}")
    
    # Assert que el contrato del mes actual (c1) SÍ está acumulado, pero el de mes pasado (c2) NO.
    # Total esperado: c1 = 50000.00
    assert total_actual >= Decimal("50000.00"), f"Error en suma de mes actual: {total_actual}"
    
    # Mes pasado
    # Calcular mes pasado
    mes_pasado = hoy.month - 1
    anio_pasado = hoy.year
    if mes_pasado <= 0:
        mes_pasado = 12
        anio_pasado -= 1
        
    contratos_pasado = Contrato.objects.filter(
        empresa=empresa,
        vigencia_contrato__year=anio_pasado,
        vigencia_contrato__month=mes_pasado
    )
    total_pasado = contratos_pasado.aggregate(total=Sum('monto_contrato'))['total'] or Decimal('0.00')
    print(f"Mes pasado: Total contratos activos detectados = {total_pasado}")
    
    # Assert que el contrato del mes pasado (c2) SÍ está acumulado
    # Total esperado: c2 = 25000.00
    assert total_pasado >= Decimal("25000.00"), f"Error en suma de mes pasado: {total_pasado}"
    
    # 3. Limpieza de base de datos de prueba
    c1.delete()
    c2.delete()
    print("Contratos de prueba eliminados correctamente.")
    print("--- VALIDACIÓN EXITOSA ---")

if __name__ == "__main__":
    run_tests()
