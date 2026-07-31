import json
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from panel.models import Empresa
from preferencias.models import Sucursal, Moneda
from compras.models import OrdenCompra, DetalleCompra
from almacenes.models import Almacen
from core.models import Producto, Transaccion
from recepciones.models import Recepcion, DetalleRecepcion, DetalleRecepcionExtra
from recepciones.services import procesar_recepcion_servicio

class ProductExpirationTestCase(TestCase):
    def setUp(self):
        # Setup basic company, sucursal, and user
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test S.A.",
            subdominio="testenv",
            modulo_inventarios=True
        )
        self.user = User.objects.create_superuser(username="admin@testenv", password="password")
        self.sucursal = Sucursal.objects.create(nombre="Sucursal Principal", empresa=self.empresa)
        self.moneda = Moneda.objects.create(nombre="Peso Mexicano", siglas="MXN", empresa=self.empresa)
        self.almacen = Almacen.objects.create(nombre="Almacen A", empresa=self.empresa, sucursal=self.sucursal)

        # Create a product with maneja_caducidad=True
        self.producto = Producto.objects.create(
            clave="CAD-101",
            nombre="Suplemento A",
            tipo="producto",
            precio_costo=Decimal("100.00"),
            precio_venta=Decimal("150.00"),
            maneja_caducidad=True,
            empresa=self.empresa
        )

        # Create a purchase order (OrdenCompra)
        self.orden_compra = OrdenCompra.objects.create(
            empresa=self.empresa,
            sucursal_empresa=self.sucursal,
            almacen_destino=self.almacen,
            moneda=self.moneda,
            tipo_cambio=Decimal("1.0000"),
            estado="aprobada"
        )
        self.detalle_compra = DetalleCompra.objects.create(
            orden_compra=self.orden_compra,
            producto=self.producto,
            cantidad=15,
            precio_costo=Decimal("100.00")
        )

    def test_recepcion_with_expiration_dates(self):
        # Prepare post data representing multiple expiration dates
        extra_data = [
            {"tipo": "caducidad", "fecha_caducidad": "2026-12-31", "cantidad_lote": 5},
            {"tipo": "caducidad", "fecha_caducidad": "2027-06-30", "cantidad_lote": 10}
        ]

        post_data = {
            "orden_compra": self.orden_compra.id,
            "almacen": self.almacen.id,
            "fecha": "2026-07-31",
            "factura": "F-9999",
            "detalle_compra_id[]": [self.detalle_compra.id],
            "cantidad_recibida[]": [15],
            "costo_unitario[]": ["100.00"],
            f"extra_data_{self.detalle_compra.id}": json.dumps(extra_data)
        }

        # Process the reception service
        recepcion = procesar_recepcion_servicio(post_data, self.empresa, self.user)

        # Assertions on Recepcion
        self.assertIsNotNone(recepcion)
        self.assertEqual(recepcion.estado, "completada")
        self.assertEqual(recepcion.factura, "F-9999")

        # Assertions on DetalleRecepcion
        detalles = recepcion.detalles.all()
        self.assertEqual(detalles.count(), 1)
        det_recep = detalles.first()
        self.assertEqual(det_recep.producto, self.producto)
        self.assertEqual(det_recep.cantidad_recibida, 15)

        # Assertions on DetalleRecepcionExtra (expiration entries)
        extras = det_recep.extras.all()
        self.assertEqual(extras.count(), 2)

        extra_1 = extras.filter(fecha_caducidad="2026-12-31").first()
        self.assertIsNotNone(extra_1)
        self.assertEqual(extra_1.tipo, "caducidad")
        self.assertEqual(extra_1.cantidad_lote, 5)

        extra_2 = extras.filter(fecha_caducidad="2027-06-30").first()
        self.assertIsNotNone(extra_2)
        self.assertEqual(extra_2.tipo, "caducidad")
        self.assertEqual(extra_2.cantidad_lote, 10)

        # Assertions on Transaccion (Kardex log)
        transacciones = Transaccion.objects.filter(
            producto=self.producto,
            referencia=f"REC-{recepcion.id:04d}"
        )
        self.assertEqual(transacciones.count(), 1)
        tx = transacciones.first()
        # Verify the first expiration date is logged as lote in the transaction
        self.assertEqual(tx.lote, "2026-12-31")

    def test_recepcion_with_both_lote_and_expiration(self):
        # Configure the product to manage both lot and expiration date
        self.producto.maneja_lote = True
        self.producto.save()

        extra_data = [
            {"tipo": "lote", "lote": "LOTE-AAA", "fecha_caducidad": "2026-12-31", "cantidad_lote": 8},
            {"tipo": "lote", "lote": "LOTE-BBB", "fecha_caducidad": "2027-06-30", "cantidad_lote": 7}
        ]

        post_data = {
            "orden_compra": self.orden_compra.id,
            "almacen": self.almacen.id,
            "fecha": "2026-07-31",
            "factura": "F-9999",
            "detalle_compra_id[]": [self.detalle_compra.id],
            "cantidad_recibida[]": [15],
            "costo_unitario[]": ["100.00"],
            f"extra_data_{self.detalle_compra.id}": json.dumps(extra_data)
        }

        # Process
        recepcion = procesar_recepcion_servicio(post_data, self.empresa, self.user)

        # Assertions on DetalleRecepcionExtra (both lote and expiration date saved)
        det_recep = recepcion.detalles.first()
        extras = det_recep.extras.all()
        self.assertEqual(extras.count(), 2)

        e1 = extras.filter(lote="LOTE-AAA").first()
        self.assertIsNotNone(e1)
        self.assertEqual(e1.fecha_caducidad.strftime("%Y-%m-%d"), "2026-12-31")
        self.assertEqual(e1.cantidad_lote, 8)

        e2 = extras.filter(lote="LOTE-BBB").first()
        self.assertIsNotNone(e2)
        self.assertEqual(e2.fecha_caducidad.strftime("%Y-%m-%d"), "2027-06-30")
        self.assertEqual(e2.cantidad_lote, 7)

