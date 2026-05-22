from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from preferencias.models import Sucursal, Moneda
from decimal import Decimal

class Costeo(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Vendedor")
    
    # Identificación (puede ser producto o servicio)
    nombre_identificador = models.CharField(max_length=255, verbose_name="Nombre de Producto/Servicio")
    
    # Activadores de tipo
    es_manufactura = models.BooleanField(default=False, verbose_name="Manufactura")
    es_comercio = models.BooleanField(default=False, verbose_name="Comercio")
    es_servicio = models.BooleanField(default=False, verbose_name="Servicios")
    
    # Precio y Margen
    margen_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Margen %")
    precio_venta_fijo = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Precio Venta Fijo")
    utiliza_porcentaje = models.BooleanField(default=True, verbose_name="Utiliza Porcentaje")
    
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=16.00, verbose_name="IVA %")
    
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado'),
        ('CANCELADO', 'Cancelado'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='BORRADOR', verbose_name="Estado")
    duplicado_de = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='duplicados')
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def folio(self):
        if self.duplicado_de:
            # Encontrar qué número de duplicado es (en base a la fecha de creación)
            hermanos = self.duplicado_de.duplicados.order_by('fecha_creacion')
            for index, h in enumerate(hermanos):
                if h.id == self.id:
                    return f"{self.duplicado_de.folio}.{index + 1}"
            return f"{self.duplicado_de.folio}.?"
        return f"COS-{self.id:05d}"

    @property
    def get_costo_total(self):
        total = Decimal('0.00')
        if self.es_manufactura:
            for mp in self.materias_primas.all():
                total += mp.cantidad * mp.costo_unitario * mp.moneda.factor
            for mo in self.mano_obra.all():
                total += mo.horas * mo.costo_hora * mo.moneda.factor
            for gi in self.gastos_indirectos.all():
                total += gi.monto * gi.moneda.factor
        if self.es_comercio:
            for adq in self.costos_adquisicion.all():
                total += adq.monto * adq.moneda.factor
        if self.es_servicio:
            for p in self.personal_servicio.all():
                total += p.horas * p.tarifa_hora * p.moneda.factor
            for m in self.materiales_servicio.all():
                total += m.cantidad * m.costo * m.moneda.factor
        return total

    @property
    def get_venta_total(self):
        costo = self.get_costo_total
        if self.utiliza_porcentaje:
            return costo + (costo * (self.margen_porcentaje / Decimal('100.00')))
        return self.precio_venta_fijo

    @property
    def get_utilidad(self):
        return self.get_venta_total - self.get_costo_total

    def __str__(self):
        return f"Costeo {self.id} - {self.nombre_identificador}"

    class Meta:
        verbose_name = "Costeo"
        verbose_name_plural = "Costeos"
        ordering = ['-fecha_creacion']

# --- MANUFACTURA ---
class ManufacturaMateriaPrima(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='materias_primas')
    nombre = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=12, decimal_places=4)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT)

class ManufacturaManoObra(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='mano_obra')
    concepto = models.CharField(max_length=200)
    horas = models.DecimalField(max_digits=12, decimal_places=2)
    costo_hora = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT)

class ManufacturaGastoIndirecto(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='gastos_indirectos')
    concepto = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT)

# --- COMERCIO ---
class ComercioAdquisicion(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='costos_adquisicion')
    concepto = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT)

# --- SERVICIOS ---
class ServicioPersonal(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='personal_servicio')
    rol = models.CharField(max_length=200)
    horas = models.DecimalField(max_digits=12, decimal_places=2)
    tarifa_hora = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT)

class ServicioMaterial(models.Model):
    costeo = models.ForeignKey(Costeo, on_delete=models.CASCADE, related_name='materiales_servicio')
    concepto = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=12, decimal_places=4)
    costo = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT)
