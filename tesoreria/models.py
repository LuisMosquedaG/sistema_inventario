from django.db import models
from panel.models import Empresa
from preferencias.models import Moneda

class CajaBanco(models.Model):
    TIPO_CHOICES = [
        ('caja', 'Caja'),
        ('banco', 'Banco'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='caja', verbose_name="Tipo")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Caja/Banco")
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, verbose_name="Moneda")
    
    # Campos específicos para Banco
    banco_nombre = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nombre del Banco")
    cuenta = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número de Cuenta")
    clabe = models.CharField(max_length=18, blank=True, null=True, verbose_name="CLABE Interbancaria")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Caja o Banco"
        verbose_name_plural = "Cajas y Bancos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()}) - {self.moneda.siglas}"

class PagoPedido(models.Model):
    FORMA_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('transferencia', 'Transferencia'),
        ('compensacion', 'Compensación'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    pedido = models.ForeignKey('pedidos.Pedido', on_delete=models.CASCADE, related_name='pagos', verbose_name="Pedido")
    fecha_pago = models.DateField(verbose_name="Fecha de Pago")
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, verbose_name="Forma de Pago")
    caja_banco = models.ForeignKey(CajaBanco, on_delete=models.PROTECT, verbose_name="Caja/Banco")
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia")
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0, verbose_name="Tipo de Cambio")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto (Abono)")
    monto_mxn = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto en MXN")
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[('aplicado', 'Aplicado'), ('cancelado', 'Cancelado')], default='aplicado', verbose_name="Estado")
    motivo_cancelacion = models.TextField(blank=True, null=True, verbose_name="Motivo de Cancelación")

    class Meta:
        verbose_name = "Pago de Pedido"
        verbose_name_plural = "Pagos de Pedidos"
        ordering = ['-fecha_pago']

    def __str__(self):
        return f"Pago {self.id} - Pedido {self.pedido.id} - {self.monto} {self.moneda.siglas}"

class Ingreso(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    fecha = models.DateField(verbose_name="Fecha")
    concepto = models.CharField(max_length=255, verbose_name="Concepto")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto")
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0, verbose_name="Tipo de Cambio")
    monto_mxn = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto MXN")
    forma_pago = models.CharField(max_length=20, choices=PagoPedido.FORMA_PAGO_CHOICES, verbose_name="Forma de Pago")
    caja_banco = models.ForeignKey(CajaBanco, on_delete=models.PROTECT, verbose_name="Caja/Banco")
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia")
    
    # Vínculos opcionales
    pago_pedido = models.OneToOneField(PagoPedido, on_delete=models.SET_NULL, null=True, blank=True, related_name='ingreso_vinc')
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[('aplicado', 'Aplicado'), ('cancelado', 'Cancelado')], default='aplicado', verbose_name="Estado")
    motivo_cancelacion = models.TextField(blank=True, null=True, verbose_name="Motivo de Cancelación")

    class Meta:
        verbose_name = "Ingreso"
        verbose_name_plural = "Ingresos"
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Ingreso {self.id} - {self.concepto} - {self.monto} {self.moneda.siglas}"

class PagoCompra(models.Model):
    FORMA_PAGO_CHOICES = PagoPedido.FORMA_PAGO_CHOICES

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    orden_compra = models.ForeignKey('compras.OrdenCompra', on_delete=models.CASCADE, related_name='pagos', verbose_name="Orden de Compra")
    fecha_pago = models.DateField(verbose_name="Fecha de Pago")
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, verbose_name="Forma de Pago")
    caja_banco = models.ForeignKey(CajaBanco, on_delete=models.PROTECT, verbose_name="Caja/Banco")
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia")
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0, verbose_name="Tipo de Cambio")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto (Abono)")
    monto_mxn = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto en MXN")
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[('aplicado', 'Aplicado'), ('cancelado', 'Cancelado')], default='aplicado', verbose_name="Estado")
    motivo_cancelacion = models.TextField(blank=True, null=True, verbose_name="Motivo de Cancelación")

    class Meta:
        verbose_name = "Pago de Compra"
        verbose_name_plural = "Pagos de Compras"
        ordering = ['-fecha_pago']

    def __str__(self):
        return f"Pago OC {self.id} - {self.orden_compra.id} - {self.monto} {self.moneda.siglas}"

class Egreso(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    fecha = models.DateField(verbose_name="Fecha")
    concepto = models.CharField(max_length=255, verbose_name="Concepto")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto")
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0, verbose_name="Tipo de Cambio")
    monto_mxn = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto MXN")
    forma_pago = models.CharField(max_length=20, choices=PagoPedido.FORMA_PAGO_CHOICES, verbose_name="Forma de Pago")
    caja_banco = models.ForeignKey(CajaBanco, on_delete=models.PROTECT, verbose_name="Caja/Banco")
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia")
    
    # Vínculos opcionales
    pago_compra = models.OneToOneField(PagoCompra, on_delete=models.SET_NULL, null=True, blank=True, related_name='egreso_vinc')
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[('aplicado', 'Aplicado'), ('cancelado', 'Cancelado')], default='aplicado', verbose_name="Estado")
    motivo_cancelacion = models.TextField(blank=True, null=True, verbose_name="Motivo de Cancelación")

    class Meta:
        verbose_name = "Egreso"
        verbose_name_plural = "Egresos"
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Egreso {self.id} - {self.concepto} - {self.monto} {self.moneda.siglas}"
