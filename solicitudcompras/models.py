from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from panel.models import Empresa
from core.models import Producto
from pedidos.models import DetallePedido 

class SolicitudCompra(models.Model):
    """Representa una petición de compra al departamento de compras"""
    ESTADO_CHOICES = (
        ('borrador', 'Borrador'),
        ('aprobada', 'Aprobada'),
        ('enviada', 'Enviada a Compras'),
        ('atendida', 'Atendida (OC Generada)'),
        ('cancelada', 'Cancelada'),
    )

    pedido_origen = models.ForeignKey('pedidos.Pedido', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Pedido Origen")
    solicitante = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Solicitante")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha Solicitud")
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name="Enviada el")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    aplica_iva = models.BooleanField(default=True, verbose_name="Aplica IVA")
    notas = models.TextField(blank=True, verbose_name="Notas / Urgencia")

    def __str__(self):
        return f"Solicitud #{self.id} - {self.get_estado_display()}"

    @property
    def proveedor_display(self):
        """Devuelve el primer proveedor sugerido en los detalles si existe"""
        # Si ya tiene una OC, usamos el proveedor de la OC
        oc = self.ordenes_generadas.first()
        if oc:
            return oc.proveedor
            
        primer_detalle = self.detalles.exclude(proveedor__isnull=True).first()
        if primer_detalle:
            return primer_detalle.proveedor
        return None

    @property
    def oc_folios(self):
        """Devuelve los folios de las órdenes de compra generadas desde esta solicitud"""
        ordenes = self.ordenes_generadas.all()
        if not ordenes:
            return None
        return ", ".join([f"OC-{o.id:04d}" for o in ordenes])

    @property
    def solicitante_nombre_corto(self):
        """Devuelve el nombre de usuario sin el dominio (todo antes del @)"""
        if self.solicitante and '@' in self.solicitante.username:
            return self.solicitante.username.split('@')[0]
        return self.solicitante.username if self.solicitante else ''

    @property
    def total_items(self):
        return self.detalles.count()

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

class DetalleSolicitudCompra(models.Model):
    solicitud = models.ForeignKey(SolicitudCompra, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name="Producto")
    cantidad_solicitada = models.PositiveIntegerField(verbose_name="Cant. Solicitada")
    
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Proveedor Sugerido")
    sucursal = models.ForeignKey('proveedores.SucursalProveedor', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    almacen = models.ForeignKey('almacenes.Almacen', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Almacén Destino")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Unitario")
    
    # NUEVO CAMPO: MONEDA POR PARTIDA
    moneda = models.ForeignKey('preferencias.Moneda', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Moneda")
    
    # NUEVO CAMPO: LISTA DE COSTO
    lista = models.ForeignKey('categorias.ListaPrecioCosto', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Lista de Costo")

    detalle_pedido_origen = models.ForeignKey(DetallePedido, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.cantidad_solicitada} x {self.producto.nombre}"

    @property
    def subtotal(self):
        if self.costo_unitario is None:
            return Decimal('0')
        return Decimal(str(self.cantidad_solicitada)) * self.costo_unitario

    @property
    def iva_monto(self):
        if not self.solicitud.aplica_iva:
            return Decimal('0')
        porc = self.producto.iva or Decimal('0')
        return self.subtotal * (porc / 100)

    @property
    def total(self):
        return self.subtotal + self.iva_monto