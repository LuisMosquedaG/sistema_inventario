from django.db import models
from core.models import Producto 
from panel.models import Empresa
from django.contrib.auth.models import User
from decimal import Decimal

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
    sucursal_empresa = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal Empresa")
    almacen_destino = models.ForeignKey('almacenes.Almacen', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra')
    
    # NUEVOS CAMPOS: MONEDA Y TIPO DE CAMBIO
    moneda = models.ForeignKey('preferencias.Moneda', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, verbose_name="Tipo de Cambio")
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Descuento")
    aplica_iva = models.BooleanField(default=True, verbose_name="Aplica IVA")

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
    def calcular_subtotal(self):
        total = Decimal('0')
        for detalle in self.detalles.all():
            total += detalle.subtotal
        return total

    @property
    def calcular_iva(self):
        """Calcula el IVA proporcional tras aplicar el descuento al subtotal"""
        subtotal_original = self.calcular_subtotal
        if subtotal_original <= 0:
            return Decimal('0')
        
        # Suma de IVA de todas las partidas
        iva_original = Decimal('0')
        for detalle in self.detalles.all():
            iva_original += detalle.iva_monto
            
        # Proporción tras el descuento
        nuevo_subtotal = subtotal_original - self.descuento
        factor = nuevo_subtotal / subtotal_original
        
        return (iva_original * factor).quantize(Decimal('0.01'))

    @property
    def calcular_total(self):
        """Total = (Subtotal - Descuento) + IVA Ajustado"""
        nuevo_subtotal = self.calcular_subtotal - self.descuento
        return nuevo_subtotal + self.calcular_iva

    @property
    def total(self):
        return self.calcular_total
    
    @property
    def total_en_pesos(self):
        """Devuelve el total convertido a MXN usando el TC de la OC"""
        return self.total * self.tipo_cambio
    
    @property
    def total_pagado(self):
        """Suma de todos los pagos registrados para esta compra"""
        from django.db.models import Sum
        total = self.pagos.filter(estado='aplicado').aggregate(Sum('monto'))['monto__sum']
        return total or Decimal('0')

    @property
    def saldo_pendiente(self):
        """Diferencia entre el total de la compra y lo pagado"""
        return self.total - self.total_pagado

    @property
    def pago_estado(self):
        """Calcula el estado de pago basado en los abonos registrados"""
        total = self.total
        pagado = self.total_pagado
        
        if pagado <= 0:
            return 'pendiente'
        elif pagado < total:
            return 'parcial'
        else:
            return 'pagado'

    @property
    def cantidad_items(self):
        return self.detalles.count()
    
    @property
    def final_proveedor_direccion(self):
        """Devuelve la dirección de la sucursal o el domicilio fiscal del proveedor"""
        if self.sucursal and self.sucursal.direccion:
            return self.sucursal.direccion
        return self.proveedor.domicilio or "No especificado"

    @property
    def usuario_corto(self):
        if self.usuario:
            return str(self.usuario).split('@')[0]
        return "Sistema"


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
        if self.precio_costo is None:
            return Decimal('0')
        return Decimal(str(self.cantidad)) * self.precio_costo

    @property
    def iva_monto(self):
        if not self.orden_compra.aplica_iva:
            return Decimal('0')
        porc = self.producto.iva or Decimal('0')
        return self.subtotal * (porc / 100)

    @property
    def total(self):
        return self.subtotal + self.iva_monto