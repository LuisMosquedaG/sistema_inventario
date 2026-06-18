from django.test import TestCase
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from panel.models import Empresa
from recursos_humanos.models import Nomina, Empleado, Contrato, Contratista
from recursos_humanos.sat_service import SATService

class XMLPayrollParsingTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa de Prueba",
            subdominio="prueba",
            usuario_admin="admin",
            correo_contacto="prueba@test.com"
        )
        
    @patch('recursos_humanos.sat_service.CFDI')
    def test_parsear_y_guardar_xml_percepciones(self, mock_cfdi):
        # Configurar el mock de CFDI
        mock_cfdi.from_string.return_value = "mock_cfdi_instance"
        
        xml_content = """<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" xmlns:nomina12="http://www.sat.gob.mx/nomina12" Version="3.3" Total="2000.00" Folio="999" Serie="N">
  <cfdi:Emisor Rfc="XAXX010101000"/>
  <cfdi:Receptor Rfc="POT120101XYZ" Nombre="PEDRO PEREZ"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="e07b8b2e-1111-2222-3333-444455556666"/>
    <nomina12:Nomina FechaPago="2026-06-15" FechaInicialPago="2026-06-01" FechaFinalPago="2026-06-15" NumDiasPagados="15.00" TipoNomina="O">
      <nomina12:Receptor Curp="PEPE000000HDFRXX01" NumSeguridadSocial="12345678901"/>
      <nomina12:Percepciones>
        <nomina12:Percepcion TipoPercepcion="001" Clave="P001" Concepto="SUELDO QUINCENAL" ImporteGravado="1200.00" ImporteExento="0.00"/>
        <nomina12:Percepcion TipoPercepcion="002" Clave="P004" Concepto="AGUINALDO ANUAL" ImporteGravado="0.00" ImporteExento="500.00"/>
        <nomina12:Percepcion TipoPercepcion="001" Clave="P009" Concepto="PRIMA DE VACACIONES" ImporteGravado="250.00" ImporteExento="0.00"/>
        <nomina12:Percepcion TipoPercepcion="001" Clave="P009" Concepto="VACACIONES DIGNAS EX" ImporteGravado="0.00" ImporteExento="150.00"/>
      </nomina12:Percepciones>
    </nomina12:Nomina>
  </cfdi:Complemento>
</cfdi:Comprobante>"""
        
        class DummySATService(SATService):
            def __init__(self):
                pass
                
        service = DummySATService()
        
        # Ejecutar el parser
        resultado = service._parsear_y_guardar_xml(xml_content.encode('utf-8'), self.empresa, None)
        self.assertTrue(resultado)
        
        # Verificar que la nómina se guardó en la base de datos con desglose de percepciones
        nomina = Nomina.objects.get(uuid="e07b8b2e-1111-2222-3333-444455556666")
        
        self.assertEqual(nomina.nombre, "PEDRO PEREZ")
        self.assertEqual(nomina.rfc, "POT120101XYZ")
        self.assertEqual(nomina.curp, "PEPE000000HDFRXX01")
        self.assertEqual(nomina.nss, "12345678901")
        self.assertEqual(nomina.rfc_contratista, "XAXX010101000")
        self.assertEqual(nomina.periodo, "SAT Bimestre 3 2026")
        
        # Totales de percepciones desglosados
        self.assertEqual(nomina.sueldo_gravado, Decimal('1200.00'))
        self.assertEqual(nomina.aguinaldo_exento, Decimal('500.00'))
        self.assertEqual(nomina.aguinaldo_gravado, Decimal('0.00'))
        self.assertEqual(nomina.vacaciones_gravado, Decimal('250.00'))
        self.assertEqual(nomina.vacaciones_exento, Decimal('0.00'))
        self.assertEqual(nomina.vacaciones_dignas_gravado, Decimal('0.00'))
        self.assertEqual(nomina.vacaciones_dignas_exento, Decimal('150.00'))

class SISUBExportTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa de Prueba",
            subdominio="prueba",
            usuario_admin="admin",
            correo_contacto="prueba@test.com"
        )
        # Habilitar el módulo de Recursos Humanos para la empresa
        self.empresa.modulo_recursos_humanos = True
        self.empresa.save()
        
        self.user = User.objects.create_superuser(
            username="admin@prueba",
            email="admin@prueba.com",
            password="password"
        )
        self.contratista = Contratista.objects.create(
            empresa=self.empresa,
            rfc="CON010101AAA",
            nombre_razon_social="Contratista Prueba",
            correo="contratista@test.com"
        )
        self.empleado = Empleado.objects.create(
            empresa=self.empresa,
            num_empleado="E001",
            nss="12345678901",
            curp="PEPE000000HDFRXX01",
            rfc="PEPE000000XX1",
            nombre="Pedro",
            apellido_paterno="Perez",
            estado="activo"
        )
        # Crear un contrato con beneficiario = None
        self.contrato = Contrato.objects.create(
            empresa=self.empresa,
            contratista=self.contratista,
            beneficiario=None,
            fecha_inicio="2026-06-01",
            estado="vigente"
        )
        self.contrato.empleados.add(self.empleado)
        
        # Crear un recibo de nómina que caiga en el mes de Junio (Cuatrimestre 2)
        self.nomina = Nomina.objects.create(
            empresa=self.empresa,
            empleado=self.empleado,
            periodo="SAT Bimestre 3 2026",
            fecha_pago="2026-06-15",
            rfc="PEPE000000XX1",
            curp="PEPE000000HDFRXX01",
            nss="12345678901",
            nombre="Pedro Perez",
            sueldo_gravado=Decimal('1000.00'),
            dias_pagados=Decimal('15.00')
        )
        
    def test_exportar_sisub_sin_beneficiario(self):
        self.client.login(username="admin@prueba", password="password")
        from django.urls import reverse
        url = reverse('exportar_sisub_trabajadores', args=[self.contratista.id])
        response = self.client.get(url, {'cuatrimestre': 2, 'anio': 2026, 'formato': 'excel'})
        # Si tiene el error de ben.calle, responderá con error 500 (o lanzará una excepción en tests)
        self.assertEqual(response.status_code, 200)

    def test_exportar_sisub_consolida_percepciones(self):
        # Crear segunda nomina en el mismo bimestre (Junio 2026 -> Bimestre 3)
        Nomina.objects.create(
            empresa=self.empresa,
            empleado=self.empleado,
            periodo="SAT Bimestre 3 2026",
            fecha_pago="2026-06-30",
            rfc="PEPE000000XX1",
            curp="PEPE000000HDFRXX01",
            nss="12345678901",
            nombre="Pedro Perez",
            sueldo_gravado=Decimal('1500.00'),
            dias_pagados=Decimal('15.00')
        )
        
        self.client.login(username="admin@prueba", password="password")
        from django.urls import reverse
        url = reverse('exportar_sisub_trabajadores', args=[self.contratista.id])
        response = self.client.get(url, {'cuatrimestre': 2, 'anio': 2026, 'formato': 'csv'})
        
        self.assertEqual(response.status_code, 200)
        
        # Analizar el contenido del CSV
        content = response.content.decode('utf-8-sig') # Decodificar omitiendo el BOM
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        
        # Deben haber 2 líneas: 1 de cabecera y 1 de datos (por consolidación)
        self.assertEqual(len(lines), 2)
        
        # La línea de datos debe contener la suma de percepciones (1000 + 1500 = 2500)
        row_data = lines[1].split(',')
        self.assertEqual(row_data[15], '2500')

