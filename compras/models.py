from django.db import models
from core.models import Producto 
from panel.models import Empresa
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone

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
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    sucursal_empresa = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal Empresa")
    almacen_destino = models.ForeignKey('almacenes.Almacen', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra')
    centro_costo = models.ForeignKey('centros_costos.CentroCosto', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra', verbose_name="Centro de Costos")
    
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
        desc = Decimal(str(self.descuento or 0))
        nuevo_subtotal = max(Decimal('0'), subtotal_original - desc)
        factor = nuevo_subtotal / subtotal_original
        
        return (iva_original * factor).quantize(Decimal('0.01'))

    @property
    def calcular_total(self):
        """Total = (Subtotal - Descuento) + IVA Ajustado"""
        desc = Decimal(str(self.descuento or 0))
        nuevo_subtotal = max(Decimal('0'), self.calcular_subtotal - desc)
        return nuevo_subtotal + self.calcular_iva

    @property
    def total(self):
        return self.calcular_total
    
    @property
    def total_en_pesos(self):
        """Devuelve el total convertido a MXN usando el TC de la OC"""
        tc = self.tipo_cambio or Decimal('1.0000')
        return (self.total * tc).quantize(Decimal('0.01'))
    
    @property
    def total_pagado_en_pesos(self):
        """Suma de todos los pagos aplicados convertidos a MXN"""
        total_mxn = Decimal('0.00')
        for p in self.pagos.filter(estado='aplicado'):
            if p.monto_mxn is not None and p.monto_mxn > Decimal('0'):
                m_mxn = p.monto_mxn
            else:
                m_mxn = p.monto * (p.tipo_cambio or Decimal('1.0000'))
            total_mxn += Decimal(str(m_mxn))
        return total_mxn.quantize(Decimal('0.01'))

    @property
    def saldo_pendiente_en_pesos(self):
        """Diferencia en MXN entre el total de la compra y lo pagado en MXN"""
        saldo = self.total_en_pesos - self.total_pagado_en_pesos
        return max(Decimal('0.00'), saldo.quantize(Decimal('0.01')))

    @property
    def total_pagado(self):
        """Suma pagada expresada en la moneda original de la orden de compra"""
        tc = self.tipo_cambio or Decimal('1.0000')
        if tc > 0:
            return (self.total_pagado_en_pesos / tc).quantize(Decimal('0.01'))
        return self.total_pagado_en_pesos

    @property
    def saldo_pendiente(self):
        """Saldo pendiente expresado en la moneda original de la orden de compra"""
        tc = self.tipo_cambio or Decimal('1.0000')
        if tc > 0:
            return (self.saldo_pendiente_en_pesos / tc).quantize(Decimal('0.01'))
        return self.saldo_pendiente_en_pesos

    @property
    def pago_estado(self):
        """Calcula el estado de pago basado en los abonos registrados normalizados a MXN"""
        tot_mxn = self.total_en_pesos
        pag_mxn = self.total_pagado_en_pesos
        
        if pag_mxn <= 0:
            return 'pendiente'
        elif pag_mxn < (tot_mxn - Decimal('0.01')):
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
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NUEVO: Vínculo directo para no perder el hilo con el pedido
    detalle_pedido_origen = models.ForeignKey(
        'pedidos.DetallePedido', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Partida de Pedido Origen"
    )

    # CONVERSIONES DE UNIDAD DE COMPRA
    unidad_compra = models.CharField(max_length=50, blank=True, null=True, verbose_name="Unidad de Compra")
    factor_conversion = models.DecimalField(max_digits=12, decimal_places=4, default=1.0000, verbose_name="Factor de Conversión")
    cantidad_inventario = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Cant. Entrada Inventario")

    # CLASE DE COSTO POR PARTIDA (Estilo SAP CO - Primary Cost Element)
    clase_costo = models.ForeignKey(
        'centros_costos.ClaseCosto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles_compras',
        verbose_name="Clase de Costo"
    )

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    @property
    def cantidad_inventario_calculada(self):
        if self.cantidad_inventario and self.cantidad_inventario > Decimal('0'):
            return self.cantidad_inventario
        return Decimal(str(self.cantidad)) * (self.factor_conversion or Decimal('1.0'))

    @property
    def unidad_compra_display(self):
        if self.unidad_compra and self.unidad_compra != 'BASE':
            return self.unidad_compra
        return self.producto.get_unidad_medida_display() or self.producto.unidad_medida

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


class HistorialOrdenCompra(models.Model):
    ACCION_CHOICES = (
        ('creacion', 'Creada'),
        ('aprobacion', 'Aprobada'),
        ('recibida', 'Recibida'),
        ('parcial', 'Recepción Parcial'),
        ('edicion', 'Editada'),
        ('cancelacion', 'Cancelada'),
    )

    orden_compra = models.ForeignKey(OrdenCompra, related_name='historial', on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario")
    accion = models.CharField(max_length=30, choices=ACCION_CHOICES, verbose_name="Acción")
    comentario = models.TextField(blank=True, default='', verbose_name="Comentarios / Motivo")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Historial de Orden de Compra"
        verbose_name_plural = "Historiales de Órdenes de Compra"
        ordering = ['fecha']

    def __str__(self):
        return f"{self.orden_compra} - {self.get_accion_display()} ({self.fecha.strftime('%d/%m/%Y %H:%M')})"
