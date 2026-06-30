from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from clientes.models import Cliente
from core.models import Producto
from decimal import Decimal

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
    def es_hija(self):
        return self.parent_orden is not None

    @property
    def tiene_hijas(self):
        return self.hijas.exists()

    @property
    def total_orden(self):
        return self.calcular_total

    @property
    def calcular_subtotal(self):
        total = Decimal('0')
        for detalle in self.detalles.all():
            total += detalle.subtotal
        return total

    @property
    def calcular_iva(self):
        total = Decimal('0')
        for detalle in self.detalles.all():
            total += detalle.iva_monto
        return total

    @property
    def calcular_total(self):
        return self.calcular_subtotal + self.calcular_iva

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
            return Decimal('0')
        return Decimal(str(self.cantidad)) * self.precio_unitario

    @property
    def iva_monto(self):
        porc = self.producto.iva or Decimal('0')
        return self.subtotal * (porc / 100)

    @property
    def total(self):
        return self.subtotal + self.iva_monto


# ==========================================
# MODELO: CAJA PUNTO DE VENTA (POS)
# ==========================================
class CajaPOS(models.Model):
    ESTADO_CHOICES = (
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
    )

    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Caja")
    usuario_asignado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cajas_pos', verbose_name="Usuario Asignado")
    caja_efectivo = models.ForeignKey('tesoreria.CajaBanco', on_delete=models.PROTECT, related_name='cajas_pos_efectivo', verbose_name="Caja (Efectivo)")
    banco_tarjeta = models.ForeignKey('tesoreria.CajaBanco', on_delete=models.PROTECT, related_name='cajas_pos_tarjeta', verbose_name="Banco Tarjeta")
    banco_transferencia = models.ForeignKey('tesoreria.CajaBanco', on_delete=models.PROTECT, related_name='cajas_pos_transferencia', verbose_name="Banco Transferencias")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='cerrada', verbose_name="Estado")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")

    class Meta:
        verbose_name = "Caja POS"
        verbose_name_plural = "Cajas POS"

    def __str__(self):
        return f"{self.nombre} - {self.usuario_asignado.username} ({self.get_estado_display()})"

    @property
    def username_display(self):
        if '@' in self.usuario_asignado.username:
            return self.usuario_asignado.username.split('@')[0]
        return self.usuario_asignado.username


# ==========================================
# MODELO: SESION DE CAJA POS
# ==========================================
class SesionCajaPOS(models.Model):
    ESTADO_CHOICES = (
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
    )

    caja_pos = models.ForeignKey(CajaPOS, on_delete=models.CASCADE, related_name='sesiones', verbose_name="Caja POS")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sesiones_pos', verbose_name="Usuario")
    monto_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Monto Inicial (Efectivo)")
    fecha_apertura = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Apertura")
    
    # Cierre
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Cierre")
    monto_final_efectivo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Monto Final Efectivo (Contado)")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='abierta', verbose_name="Estado")
    
    # Totales calculados por sistema
    total_ventas_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Ventas Efectivo")
    total_ventas_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Ventas Tarjeta")
    total_ventas_transferencia = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Ventas Transferencia")
    
    class Meta:
        verbose_name = "Sesión de Caja POS"
        verbose_name_plural = "Sesiones de Caja POS"

    def __str__(self):
        return f"Sesión {self.caja_pos.nombre} - {self.fecha_apertura.strftime('%d/%m/%Y %H:%M')}"

    @property
    def username_display(self):
        if '@' in self.usuario.username:
            return self.usuario.username.split('@')[0]
        return self.usuario.username

    @property
    def total_ventas(self):
        return self.total_ventas_efectivo + self.total_ventas_tarjeta + self.total_ventas_transferencia
