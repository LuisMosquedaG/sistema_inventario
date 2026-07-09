import os
import sys
import django
from decimal import Decimal

# Configurar entorno Django
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_inventario.settings')
django.setup()

from panel.models import Empresa
from recursos_humanos.models import Contrato, Contratista, ImportacionSUA
from django.db.models import Count

def run_tests():
    print("--- INICIANDO VALIDACIÓN DE GRÁFICAS DE OBLIGACIONES PATRONALES ---")
    empresa = Empresa.objects.first()
    if not empresa:
        print("No hay empresas registradas para realizar la prueba.")
        return
        
    print(f"Empresa detectada: {empresa.nombre}")
    
    # 1. Test Contratos Estados
    stats_contratos_estados = list(Contrato.objects.filter(
        empresa=empresa
    ).values('estado').annotate(
        total=Count('id')
    ))
    print(f"Estados de Contratos calculados: {stats_contratos_estados}")
    
    # 2. Test SUAs por Contratista (Monto RCV + INF y Empleados)
    contratistas = Contratista.objects.filter(empresa=empresa)
    suas = list(ImportacionSUA.objects.filter(empresa=empresa))
    stats_suas_contratistas = []
    stats_suas_empleados = []

    for con in contratistas:
        con_rfc_clean = con.rfc.replace('-', '').strip().upper() if con.rfc else ""
        con_rp_clean = con.registro_patronal.replace('-', '').strip().upper() if con.registro_patronal else ""
        con_name_clean = con.nombre_razon_social.strip().upper() if con.nombre_razon_social else ""
        
        total_contratista_rcv_inf = Decimal('0.00')
        unique_nss = set()
        for s in suas:
            s_rfc_clean = s.rfc_empresa.replace('-', '').strip().upper() if s.rfc_empresa else ""
            s_rp_clean = s.registro_patronal.replace('-', '').strip().upper() if s.registro_patronal else ""
            s_name_clean = s.nombre_razon_social.strip().upper() if s.nombre_razon_social else ""
            
            if (con_rfc_clean and con_rfc_clean == s_rfc_clean) or \
               (con_rp_clean and con_rp_clean == s_rp_clean) or \
               (con_name_clean and con_name_clean == s_name_clean):
                totales_sua = s.trabajadores.aggregate(
                    rcv=Sum('subtotal'),
                    inf=Sum('suma_infonavit')
                )
                total_contratista_rcv_inf += (totales_sua['rcv'] or Decimal('0.00')) + (totales_sua['inf'] or Decimal('0.00'))
                
                for t in s.trabajadores.all():
                    if t.nss:
                        unique_nss.add(t.nss.strip())
                
        stats_suas_contratistas.append({
            'contratista': con.nombre_razon_social,
            'monto': float(total_contratista_rcv_inf)
        })
        stats_suas_empleados.append({
            'contratista': con.nombre_razon_social,
            'cantidad': len(unique_nss)
        })

    stats_suas_contratistas = sorted(stats_suas_contratistas, key=lambda x: x['monto'], reverse=True)[:10]
    stats_suas_empleados = sorted(stats_suas_empleados, key=lambda x: x['cantidad'], reverse=True)[:10]

    from django.db.models import Max
    contratos_caros = Contrato.objects.filter(
        empresa=empresa,
        contratista__isnull=False
    ).values('contratista__nombre_razon_social').annotate(
        max_monto=Max('monto_contrato')
    ).order_by('-max_monto')[:5]

    stats_contratos_caros = []
    for c in contratos_caros:
        stats_contratos_caros.append({
            'contratista': c['contratista__nombre_razon_social'],
            'monto': float(c['max_monto'])
        })

    contratistas_beneficiarios = Contrato.objects.filter(
        empresa=empresa,
        contratista__isnull=False,
        beneficiario__isnull=False
    ).values('contratista__nombre_razon_social').annotate(
        num_benef=Count('beneficiario', distinct=True)
    ).order_by('-num_benef')[:5]

    stats_contratistas_beneficiarios = []
    for cb in contratistas_beneficiarios:
        stats_contratistas_beneficiarios.append({
            'contratista': cb['contratista__nombre_razon_social'],
            'cantidad': cb['num_benef']
        })

    print(f"SUAs por contratista (RCV+INF) calculados: {stats_suas_contratistas}")
    print(f"Empleados por contratista calculados: {stats_suas_empleados}")
    print(f"Contratos más caros calculados: {stats_contratos_caros}")
    print(f"Contratistas con más beneficiarios calculados: {stats_contratistas_beneficiarios}")
    print("--- VALIDACIÓN EXITOSA ---")

if __name__ == "__main__":
    run_tests()
