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

    ENTREGA_CHOICES = (
        ('pendiente', 'Pendiente'),
        ('listo', 'Listo para enviar'),
        ('transito', 'En tránsito'),
        ('entregado', 'Entregado'),
    )

    # REFERENCIAS
    pedido_origen = models.ForeignKey(
        'pedidos.Pedido', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ordenes_venta',
        verbose_name="Pedido de Origen"
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Vendedor")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # Jerarquía para entregas parciales
    parent_orden = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='hijas')
    secuencia = models.PositiveIntegerField(default=0)

    # Fechas
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    fecha_surtido = models.DateTimeField(null=True, blank=True, verbose_name="Surtido el")
    
    # Estados y Datos de Envío
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    estado_entrega = models.CharField(max_length=20, choices=ENTREGA_CHOICES, default='pendiente', verbose_name="Estado de Entrega")
    almacen = models.ForeignKey('almacenes.Almacen', on_delete=models.PROTECT, null=True, blank=True, verbose_name="Almacén de Salida")
    
    # Datos de envío (se llenan al momento de surtir)
    direccion_envio = models.TextField(blank=True, verbose_name="Dirección de Envío")
    contacto_envio = models.CharField(max_length=100, blank=True, verbose_name="Contacto / Email")
    notas_envio = models.TextField(blank=True, verbose_name="Notas de Paquetería")

    quien_recibe = models.CharField(max_length=150, blank=True, verbose_name="Quién Recibe")
    telefono_recibe = models.CharField(max_length=20, blank=True, verbose_name="Teléfono Recibe")
    guia = models.CharField(max_length=100, blank=True, verbose_name="Número de Guía")

    def __str__(self):
        return f"{self.folio_display} | {self.cliente}"

    @property
    def folio_display(self):
        if self.secuencia > 0 and self.parent_orden:
            return f"OS-{self.parent_orden.id:04d}.{self.secuencia}"
        return f"OS-{self.id:04d}"

    @property
    def total_orden(self):
        total = 0
        for detalle in self.detalles.all():
            total += detalle.subtotal
        return total

    @property
    def final_direccion_envio(self):
        """Devuelve la dirección de envío de la orden o el fallback del cliente"""
        if self.direccion_envio:
            return self.direccion_envio
        
        c = self.cliente
        parts = []
        if c.envio_calle: parts.append(c.envio_calle)
        if c.envio_numero_ext: parts.append(f"#{c.envio_numero_ext}")
        if c.envio_numero_int: parts.append(f"Int {c.envio_numero_int}")
        if c.envio_colonia: parts.append(c.envio_colonia)
        if c.envio_cp: parts.append(f"CP {c.envio_cp}")
        if c.envio_estado: parts.append(c.envio_estado)
        
        if not parts:
            # Fallback a dirección fiscal si no hay dirección de envío
            if c.calle: parts.append(c.calle)
            if c.numero_ext: parts.append(f"#{c.numero_ext}")
            if c.numero_int: parts.append(f"Int {c.numero_int}")
            if c.colonia: parts.append(c.colonia)
            if c.cp: parts.append(f"CP {c.cp}")
            if c.estado_dir: parts.append(c.estado_dir)
            
        return ", ".join(parts) if parts else "N/A"

    @property
    def final_quien_recibe(self):
        """Devuelve quién recibe o el nombre del cliente"""
        return self.quien_recibe or self.cliente.envio_quien_recibe or self.cliente.nombre_completo

    @property
    def final_telefono_recibe(self):
        """Devuelve el teléfono de quien recibe o el del cliente"""
        return self.telefono_recibe or self.cliente.envio_telefono or self.cliente.telefono or "N/A"

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
        if self.precio_unitario is None:
            return 0
        return self.cantidad * self.precio_unitario