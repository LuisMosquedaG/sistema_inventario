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

    def test_exportar_sisub_sdi_cero_fallback(self):
        from recursos_humanos.models import ImportacionSUA, TrabajadorSUA
        
        # Crear importación de SUA para Mayo 2026 (mes 5, Bimestre 3) con SDI > 0
        sua_mayo = ImportacionSUA.objects.create(
            empresa=self.empresa,
            periodo="MAYO 2026",
            tipo="mensual",
            rfc_empresa="CON010101AAA"
        )
        TrabajadorSUA.objects.create(
            importacion=sua_mayo,
            nss="12345678901",
            nombre="Pedro Perez",
            rfc_curp="PEPE000000HDFRXX01",
            sdi=Decimal('185.50')
        )
        
        # Crear importación de SUA para Junio 2026 (mes 6, Bimestre 3) con SDI = 0
        sua_junio = ImportacionSUA.objects.create(
            empresa=self.empresa,
            periodo="JUNIO 2026",
            tipo="mensual",
            rfc_empresa="CON010101AAA"
        )
        TrabajadorSUA.objects.create(
            importacion=sua_junio,
            nss="12345678901",
            nombre="Pedro Perez",
            rfc_curp="PEPE000000HDFRXX01",
            sdi=Decimal('0.00')
        )
        
        self.client.login(username="admin@prueba", password="password")
        from django.urls import reverse
        url = reverse('exportar_sisub_trabajadores', args=[self.contratista.id])
        response = self.client.get(url, {'cuatrimestre': 2, 'anio': 2026, 'formato': 'csv'})
        
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8-sig')
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        
        # La segunda línea (datos) debe tener el SDI de Mayo (185.50) en lugar del 0.00 de Junio
        row_data = lines[1].split(',')
        self.assertEqual(Decimal(row_data[18]), Decimal('185.50'))

    def test_exportar_nominas_excel(self):
        # Crear un recibo con percepciones para exportar
        Nomina.objects.create(
            empresa=self.empresa,
            empleado=self.empleado,
            periodo="SAT Bimestre 3 2026",
            fecha_pago="2026-06-15",
            rfc="PEPE000000XX1",
            curp="PEPE000000HDFRXX01",
            nss="12345678901",
            nombre="Pedro Perez",
            sueldo_gravado=Decimal('1200.00'),
            vacaciones_gravado=Decimal('300.00'),
            vacaciones_exento=Decimal('100.00'),
            vacaciones_dignas_gravado=Decimal('400.00'),
            vacaciones_dignas_exento=Decimal('200.00'),
            aguinaldo_gravado=Decimal('500.00'),
            aguinaldo_exento=Decimal('250.00')
        )
        self.client.login(username="admin@prueba", password="password")
        from django.urls import reverse
        url = reverse('exportar_nominas_excel')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # Leer el Excel generado en memoria
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(response.content), data_only=True)
        ws = wb.active
        
        # Verificar cabeceras
        headers = [cell.value for cell in ws[1]]
        self.assertIn("Sueldo (Gravado)", headers)
        self.assertIn("Vacaciones (Gravado)", headers)
        self.assertIn("Vacaciones (Exento)", headers)
        self.assertIn("Vacaciones Dignas (Gravado)", headers)
        self.assertIn("Vacaciones Dignas (Exento)", headers)
        self.assertIn("Aguinaldo (Gravado)", headers)
        self.assertIn("Aguinaldo (Exento)", headers)

class ContratoEstadosYVersionesTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Empresa de Prueba",
            subdominio="prueba",
            usuario_admin="admin",
            correo_contacto="prueba@test.com"
        )
        self.contratista = Contratista.objects.create(
            empresa=self.empresa,
            rfc="CON010101AAA",
            nombre_razon_social="Contratista Prueba",
            correo="contratista@test.com"
        )

    def test_contrato_estados_y_versiones(self):
        import datetime
        today = datetime.date.today()
        past_date = today - datetime.timedelta(days=10)
        future_date = today + datetime.timedelta(days=10)

        # 1. Contrato vigente en fechas y periodicidad
        contrato_vigente = Contrato.objects.create(
            empresa=self.empresa,
            contratista=self.contratista,
            fecha_inicio=past_date,
            fecha_fin=future_date,
            version="1",
            estado_periodicidad="vigente"
        )
        self.assertEqual(contrato_vigente.estado_vigencia, 'vigente')
        self.assertEqual(contrato_vigente.estado, 'vigente')
        self.assertEqual(contrato_vigente.version, '1')

        # 2. Contrato con periodicidad cerrado (se auto-calcula por fecha_fin en el pasado)
        contrato_cerrado = Contrato.objects.create(
            empresa=self.empresa,
            contratista=self.contratista,
            fecha_inicio=past_date - datetime.timedelta(days=5),
            fecha_fin=past_date,
            version="2",
            estado_periodicidad="vigente"
        )
        self.assertEqual(contrato_cerrado.estado_periodicidad, 'cerrado')
        self.assertEqual(contrato_cerrado.estado, 'cerrado')
        self.assertEqual(contrato_cerrado.version, '2')

        # 3. Contrato vencido en fechas (vigencia_contrato y fecha_fin en el pasado)
        contrato_vencido = Contrato.objects.create(
            empresa=self.empresa,
            contratista=self.contratista,
            fecha_inicio=past_date - datetime.timedelta(days=10),
            fecha_fin=past_date,
            vigencia_contrato=past_date,
            version="1",
            estado_periodicidad="vigente"
        )
        self.assertEqual(contrato_vencido.estado_vigencia, 'vencido')
        self.assertEqual(contrato_vencido.estado_periodicidad, 'cerrado')
        self.assertEqual(contrato_vencido.estado, 'cerrado')
