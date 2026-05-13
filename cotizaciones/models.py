from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa  # <--- IMPORTANTE
from clientes.models import Cliente, ContactoCliente 
from core.models import Producto    

class Cotizacion(models.Model):
    ESTADO_CHOICES = (
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
        ('aprobada', 'Aprobada'),
        ('ganada', 'Ganada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'), 
    )

    RESULTADO_CHOICES = (
        ('pendiente', 'Pendiente'),
        ('ganada', 'Ganada'),
        ('perdida', 'Perdida'),
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    
    contacto = models.ForeignKey(
        ContactoCliente, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        verbose_name="Contacto Asignado",
        related_name='cotizaciones_asignadas'
    )

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Vendedor")
    
    # --- NUEVO CAMPO: MULTI-TENANCY ---
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa (Tenant)")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    fecha_inicio = models.DateField(verbose_name="Vigencia Inicio")
    fecha_fin = models.DateField(verbose_name="Vigencia Fin")
    
    origen = models.CharField(max_length=200, verbose_name="Origen")
    direccion_entrega = models.TextField(verbose_name="Dirección de Entrega")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, default='pendiente')
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")

    parent_quote = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="Cotización Padre",
        related_name="recotizaciones"
    )

    @property
    def tiene_pedido(self):
        """Verifica si esta cotización ya generó un pedido"""
        from pedidos.models import Pedido
        return Pedido.objects.filter(cotizacion_origen_id=self.id, empresa=self.empresa).exists()

    def __str__(self):
        return f"{self.folio_completo} - {self.cliente}"
    
    @property
    def calcular_total(self):
        """Calcula la suma total de todos los detalles de esta cotización"""
        total = 0
        for detalle in self.detalles.all():
            total += detalle.subtotal
        return total

    @property
    def folio_completo(self):
        if self.parent_quote:
            return f"COT-{self.parent_quote.id:04d}-001"
        else:
            return f"COT-{self.id:04d}"

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"


class DetalleCotizacion(models.Model):
    """Tabla para guardar los productos de cada cotización"""
    # Nota: No necesita campo 'empresa' porque pertenece a una Cotización, 
    # y la Cotización ya pertenece a una empresa.
    cotizacion = models.ForeignKey(Cotizacion, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name="Producto")
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def subtotal(self):
        if self.precio_unitario is None:
            return 0
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"