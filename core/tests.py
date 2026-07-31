from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
from panel.models import Empresa
from preferencias.models import Sucursal
from core.models import Producto
from almacenes.models import Almacen, Inventario

class InventoryTotalsTestCase(TestCase):
    def setUp(self):
        # Create enterprise and user
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test",
            subdominio="testenv",
            modulo_inventarios=True
        )
        self.user = User.objects.create_superuser(username="admin@testenv", password="password")
        self.client = Client()
        self.client.force_login(self.user)
        
        # Set session variable for tenant/empresa
        session = self.client.session
        session['empresa_id'] = self.empresa.id
        session.save()
        
        # Create standard layout
        self.sucursal = Sucursal.objects.create(nombre="Sucursal Centro", empresa=self.empresa)
        self.almacen = Almacen.objects.create(nombre="Almacen Principal", empresa=self.empresa, sucursal=self.sucursal)
        
        # Create products
        self.prod_a = Producto.objects.create(
            clave="A01",
            nombre="Producto A",
            tipo="producto",
            estado="activo",
            precio_costo=Decimal('5.00'),
            precio_venta=Decimal('10.00'),
            empresa=self.empresa
        )
        self.prod_b = Producto.objects.create(
            clave="B02",
            nombre="Producto B",
            tipo="producto",
            estado="activo",
            precio_costo=Decimal('10.00'),
            precio_venta=Decimal('20.00'),
            empresa=self.empresa
        )
        
        # Configure inventory/stocks
        # Prod A: 10 units * $5.00 cost = $50.00 total value. 2 units reserved.
        Inventario.objects.create(
            producto=self.prod_a,
            almacen=self.almacen,
            cantidad=10,
            reservado=2,
            costo_promedio=Decimal('5.00'),
            empresa=self.empresa,
            sucursal=self.sucursal
        )
        
        # Prod B: 20 units * $10.00 cost = $200.00 total value. 5 units reserved.
        Inventario.objects.create(
            producto=self.prod_b,
            almacen=self.almacen,
            cantidad=20,
            reservado=5,
            costo_promedio=Decimal('10.00'),
            empresa=self.empresa,
            sucursal=self.sucursal
        )

    def test_dashboard_inventory_totals(self):
        # Request the inventory dashboard
        response = self.client.get('/inventario/')
        self.assertEqual(response.status_code, 200)
        
        # Verify totals in context
        resumen = response.context['resumen_totales']
        # Cost: 50.00 + 200.00 = 250.00
        self.assertEqual(resumen['costo_inventario'], 250.00)
        # Physical Stock: 10 + 20 = 30
        self.assertEqual(resumen['stock_fisico'], 30)
        # Reserved Stock: 2 + 5 = 7
        self.assertEqual(resumen['stock_reservado'], 7)
        # Available Stock: 8 + 15 = 23 (Phys - Reser)
        self.assertEqual(resumen['stock_disponible'], 23)
        
        # Assert totals are present in rendered HTML content
        self.assertContains(response, "$250.00")
        self.assertContains(response, "30 ")
        self.assertContains(response, "7 ")
        self.assertContains(response, "23 ")

class LotesYCaducidadesTestCase(TestCase):
    def setUp(self):
        # Create enterprise and user
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test S.A.",
            subdominio="testenv",
            modulo_inventarios=True
        )
        self.user = User.objects.create_superuser(username="admin@testenv", password="password")
        self.client = Client()
        self.client.force_login(self.user)
        
        session = self.client.session
        session['empresa_id'] = self.empresa.id
        session.save()
        
        self.sucursal = Sucursal.objects.create(nombre="Sucursal Norte", empresa=self.empresa)
        self.almacen = Almacen.objects.create(nombre="Almacen Norte", empresa=self.empresa, sucursal=self.sucursal)
        
        self.producto = Producto.objects.create(
            clave="EXP-99",
            nombre="Lacteo Especial",
            tipo="producto",
            estado="activo",
            precio_costo=Decimal('20.00'),
            precio_venta=Decimal('35.00'),
            maneja_lote=True,
            maneja_caducidad=True,
            empresa=self.empresa
        )

        # Create active lot/expiration in DetalleRecepcionExtra
        from recepciones.models import DetalleRecepcionExtra
        self.extra_lot = DetalleRecepcionExtra.objects.create(
            producto=self.producto,
            almacen=self.almacen,
            tipo="lote",
            lote="LOTE-007",
            fecha_caducidad="2026-12-31",
            cantidad_lote=15
        )

    def test_dashboard_lotes_y_caducidades_view(self):
        # Request the lotes y caducidades view
        response = self.client.get('/inventario/?vista=lotes_y_caducidades')
        self.assertEqual(response.status_code, 200)
        
        # Verify lot and quantity in rendered HTML table
        self.assertContains(response, "LOTE-007")
        self.assertContains(response, "2026-12-31")
        self.assertContains(response, "15 u.")
        
        # Verify calculations:
        # Physical Stock = 15
        # Total cost = 15 * 20.00 = $300.00
        resumen = response.context['resumen_totales']
        self.assertEqual(resumen['stock_fisico'], 15)
        self.assertEqual(resumen['costo_inventario'], 300.00)
        
        # Check totals display in HTML
        self.assertContains(response, "$300.00")
        self.assertContains(response, "15 u.")

    def test_dashboard_proximos_a_caducar(self):
        # Create additional lots with different expiration dates to test sorting
        from recepciones.models import DetalleRecepcionExtra
        
        # Lot A: expiring 2026-10-10 (earlier than self.extra_lot: 2026-12-31)
        lot_a = DetalleRecepcionExtra.objects.create(
            producto=self.producto,
            almacen=self.almacen,
            tipo="lote",
            lote="LOTE-AAA",
            fecha_caducidad="2026-10-10",
            cantidad_lote=10
        )
        # Lot B: expiring 2026-09-09 (even earlier)
        lot_b = DetalleRecepcionExtra.objects.create(
            producto=self.producto,
            almacen=self.almacen,
            tipo="lote",
            lote="LOTE-BBB",
            fecha_caducidad="2026-09-09",
            cantidad_lote=5
        )
        
        # Request
        response = self.client.get('/inventario/')
        self.assertEqual(response.status_code, 200)
        
        proximos = list(response.context['proximos_caducar'])
        
        # We expect at least these three lots (including self.extra_lot)
        # Ordered by expiration ascending: LOTE-BBB (09-09), LOTE-AAA (10-10), LOTE-007 (12-31)
        self.assertTrue(len(proximos) >= 3)
        self.assertEqual(proximos[0].lote, "LOTE-BBB")
        self.assertEqual(proximos[1].lote, "LOTE-AAA")
        self.assertEqual(proximos[2].lote, "LOTE-007")
        
        # Check annotated values
        # Lot B: 5 items * $20.00 cost = $100.00
        self.assertEqual(proximos[0].costo_valorizado, 100.00)
        # Lot A: 10 items * $20.00 cost = $200.00
        self.assertEqual(proximos[1].costo_valorizado, 200.00)
        
        # Verify text representation in HTML
        self.assertContains(response, "LOTE-BBB")
        self.assertContains(response, "2026-09-09")
        self.assertContains(response, "5 u.")
        self.assertContains(response, "$100.00")


