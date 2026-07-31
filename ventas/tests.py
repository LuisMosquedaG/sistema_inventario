from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
from panel.models import Empresa
from clientes.models import Cliente, Credito
from pedidos.models import Pedido
from tesoreria.models import CajaBanco, PagoPedido
from preferencias.models import Moneda, Sucursal
from core.models import Producto
from almacenes.models import Almacen, Inventario
from ventas.models import CajaPOS, SesionCajaPOS

class CreditoPOSTestCase(TestCase):
    def setUp(self):
        # Create standard entities
        self.empresa = Empresa.objects.create(nombre="Test Empresa", subdominio="prueba")
        self.moneda = Moneda.objects.create(nombre="Peso Mexicano", siglas="MXN", empresa=self.empresa)
        self.sucursal = Sucursal.objects.create(nombre="Test Sucursal", empresa=self.empresa)
        self.almacen = Almacen.objects.create(nombre="Almacen POS", empresa=self.empresa, sucursal=self.sucursal)
        self.cliente = Cliente.objects.create(
            nombre="Juan",
            apellidos="Perez",
            tipo="individual",
            estado="activo",
            empresa=self.empresa
        )
        self.user = User.objects.create_user(username="testuser@prueba", password="password")
        
        # Configure CajaBanco accounts
        self.caja_efectivo = CajaBanco.objects.create(
            nombre="Caja Efectivo Test",
            tipo="caja",
            moneda=self.moneda,
            empresa=self.empresa,
            activo=True
        )
        self.banco_tarjeta = CajaBanco.objects.create(
            nombre="Banco Tarjeta Test",
            tipo="banco",
            moneda=self.moneda,
            empresa=self.empresa,
            activo=True
        )
        self.banco_transferencia = CajaBanco.objects.create(
            nombre="Banco Transferencia Test",
            tipo="banco",
            moneda=self.moneda,
            empresa=self.empresa,
            activo=True
        )
        
        # Configure CajaPOS and open Session
        self.caja_pos = CajaPOS.objects.create(
            nombre="Caja POS Test",
            usuario_asignado=self.user,
            caja_efectivo=self.caja_efectivo,
            banco_tarjeta=self.banco_tarjeta,
            banco_transferencia=self.banco_transferencia,
            sucursal=self.sucursal,
            empresa=self.empresa
        )
        self.sesion = SesionCajaPOS.objects.create(
            caja_pos=self.caja_pos,
            usuario=self.user,
            monto_inicial=100.00,
            estado='abierta'
        )
        
        # Create a product to sell
        self.producto = Producto.objects.create(
            clave="SKU-TEST-01",
            nombre="Producto Test",
            precio_costo=100.00,
            precio_venta=150.00,
            empresa=self.empresa,
            estado="activo"
        )
        
        # Create inventory stock
        Inventario.objects.create(
            producto=self.producto,
            almacen=self.almacen,
            cantidad=10,
            empresa=self.empresa,
            sucursal=self.sucursal
        )
        
        self.client = Client()
        self.client.login(username="testuser@prueba", password="password")
        
        # Set session variable for sucursal_id and empresa_id
        session = self.client.session
        session['sucursal_id'] = self.sucursal.id
        session['empresa_id'] = self.empresa.id
        session.save()

    def test_venta_pos_credito_y_abonos(self):
        # We will mock the POS checkout request body.
        # Total cost is 2 items * $150 = $300 base. No discount.
        # Split payment: $100 cash (efectivo), $200 credit (credito).
        import json
        payload = {
            'cliente_id': self.cliente.id,
            'items': [{
                'producto_id': self.producto.id,
                'cantidad': 2,
                'precio_unitario': 150.00,
                'lista_seleccionada': '',
                'modificadores': []
            }],
            'pagos': [
                {'forma_pago': 'efectivo', 'monto': 100.00},
                {'forma_pago': 'credito', 'monto': 200.00}
            ],
            'aplica_iva': False,
            'descuento': 0,
            'descuento_tipo': 'monto'
        }
        
        self.user.is_superuser = True
        self.user.save()
        
        # Call the pos checkout view
        response = self.client.post(
            '/ventas/pos/crear-venta/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        if not data.get('success'):
            print("POS Checkout failed with error:", data.get('error'))
        self.assertTrue(data['success'])
        
        # Check that Pedido was created
        pedido = Pedido.objects.latest('id')
        self.assertEqual(pedido.total_pedido, Decimal('300.00'))
        
        # Check that a cash PagoPedido was created for $100, but NO credit PagoPedido exists yet
        pagos_pedido = PagoPedido.objects.filter(pedido=pedido)
        self.assertEqual(pagos_pedido.count(), 1)
        self.assertEqual(pagos_pedido.first().monto, Decimal('100.00'))
        self.assertEqual(pagos_pedido.first().forma_pago, 'efectivo')
        
        # Check that a Credito record was created for $200
        creditos = Credito.objects.filter(pedido=pedido)
        self.assertEqual(creditos.count(), 1)
        credito = creditos.first()
        self.assertEqual(credito.cliente, self.cliente)
        self.assertEqual(credito.monto_total, Decimal('200.00'))
        self.assertEqual(credito.saldo, Decimal('200.00'))
        
        # Check that Pedido payment status is 'credito'
        self.assertEqual(pedido.pago_estado, 'credito')
        
        # Now let's register a partial payment (abono) of $50
        # Post to /api/registrar-pago-pedido/
        pago_payload = {
            'pedido_id': pedido.id,
            'caja_banco_id': self.caja_efectivo.id,
            'moneda_id': self.moneda.id,
            'monto': 50.00,
            'tipo_cambio': 1.0,
            'fecha_pago': '2026-07-30',
            'forma_pago': 'efectivo',
            'referencia': 'Abono 1',
            'es_abono_credito': 'true'
        }
        response = self.client.post('/tesoreria/api/registrar-pago-pedido/', data=pago_payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Reload models and verify
        credito.refresh_from_db()
        self.assertEqual(credito.saldo, Decimal('150.00'))
        pedido = Pedido.objects.get(id=pedido.id)
        self.assertEqual(pedido.pago_estado, 'credito')
        self.assertEqual(pedido.saldo_pendiente, Decimal('150.00'))
        
        # Now let's register the final payment of $150 to liquidate
        pago_payload['monto'] = 150.00
        pago_payload['referencia'] = 'Abono Final'
        response = self.client.post('/tesoreria/api/registrar-pago-pedido/', data=pago_payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Verify that Credito document is deleted
        self.assertFalse(Credito.objects.filter(pedido=pedido).exists())
        
        # Verify Pedido payment status is now 'pagado'
        pedido = Pedido.objects.get(id=pedido.id)
        self.assertEqual(pedido.pago_estado, 'pagado')
        self.assertEqual(pedido.saldo_pendiente, Decimal('0.00'))
