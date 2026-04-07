from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from clientes.models import Cliente
from core.models import Producto

# ==========================================
# MODELO: ORDEN DE VENTA (CABECERA)
# ==========================================
class OrdenVenta(models.Model):
    """Representa una orden de venta formal derivada de un pedido"""

    ESTADO_CHOICES = (
        ('borrador', 'Borrador'),       # Recién creada desde pedido, editable
        ('aprobado', 'Aprobado'),       # Revisada y lista para surtir
        ('surtido', 'Surtido'),         # Enviada al cliente y stock descontado
        ('cancelado', 'Cancelado'),
    )

    # Referencias
    pedido_origen = models.OneToOneField(
        'pedidos.Pedido', 
        on_delete=models.CASCADE, 
        related_name='orden_venta',
        verbose_name="Pedido de Origen"
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Vendedor")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    
    # Fechas
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    fecha_surtido = models.DateTimeField(null=True, blank=True, verbose_name="Surtido el")
    
    # Estados y Datos de Envío
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    almacen = models.ForeignKey('almacenes.Almacen', on_delete=models.PROTECT, null=True, blank=True, verbose_name="Almacén de Salida")
    
    # Datos de envío (se llenan al momento de surtir)
    direccion_envio = models.TextField(blank=True, verbose_name="Dirección de Envío")
    contacto_envio = models.CharField(max_length=100, blank=True, verbose_name="Contacto / Email")
    notas_envio = models.TextField(blank=True, verbose_name="Notas de Paquetería")

    quien_recibe = models.CharField(max_length=150, blank=True, verbose_name="Quién Recibe")
    telefono_recibe = models.CharField(max_length=20, blank=True, verbose_name="Teléfono Recibe")
    guia = models.CharField(max_length=100, blank=True, verbose_name="Número de Guía")

    def __str__(self):
        return f"OS-{self.id:04d} | {self.cliente}"

    @property
    def total_orden(self):
        total = 0
        for detalle in self.detalles.all():
            total += detalle.subtotal
        return total

# ==========================================
# MODELO: DETALLE ORDEN DE VENTA
# ==========================================
class DetalleOrdenVenta(models.Model):
    orden_venta = models.ForeignKey('OrdenVenta', related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name="Producto")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario