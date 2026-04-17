from django.db import models
from core.models import Producto 
from panel.models import Empresa
from django.contrib.auth.models import User

class OrdenCompra(models.Model):
    """ Cabecera de la Orden de Compra """
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('aprobada', 'Aprobada'),
        ('recibida', 'Recibida'),
        ('parcial', 'Parcial'),
        ('cancelada', 'Cancelada'),
    ]

    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.PROTECT, verbose_name="Proveedor", limit_choices_to={'estado': 'activo'})
    sucursal = models.ForeignKey('proveedores.SucursalProveedor', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    almacen_destino = models.ForeignKey('almacenes.Almacen', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra')
    
    # NUEVOS CAMPOS: MONEDA Y TIPO DE CAMBIO
    moneda = models.ForeignKey('preferencias.Moneda', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, verbose_name="Tipo de Cambio")

    notas = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Creado por")
    solicitud_origen = models.ForeignKey(
        'solicitudcompras.SolicitudCompra', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ordenes_generadas',
        verbose_name="Solicitud de Compra Origen"
    )

    def __str__(self):
        return f"OC-{self.id:04d} | {self.proveedor}"

    @property
    def total(self):
        return sum(detalle.subtotal for detalle in self.detalles.all())
    
    @property
    def cantidad_items(self):
        return self.detalles.count()
    
    @property
    def usuario_corto(self):
        if self.usuario:
            return str(self.usuario).split('@')[0]
        return "Sistema"

    # --- ELIMINADO EL MÉTODO SAVE QUE HACÍA LA LIBERACIÓN MASIVA ---
    # La sincronización ahora es granular y se maneja en DetalleRecepcion
    # para evitar que partidas no recibidas se marquen como listas.

class DetalleCompra(models.Model):
    """ Ítems de la Orden de Compra """
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NUEVO: Vínculo directo para no perder el hilo con el pedido
    detalle_pedido_origen = models.ForeignKey(
        'pedidos.DetallePedido', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Partida de Pedido Origen"
    )

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_costo