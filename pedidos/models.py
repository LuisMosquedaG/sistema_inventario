from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from clientes.models import Cliente, ContactoCliente
from core.models import Producto

# Create your models here.

# ==========================================
# 1. MODELO: PEDIDO (CABECERA)
# ==========================================
class Pedido(models.Model):
    """Representa una orden de venta confirmada"""
    
    # DEFINIMOS LAS OPCIONES AL PRINCIPIO
    ESTADO_CHOICES = (
        ('borrador', 'Borrador'),       # Editable, recién creado
        ('revision', 'En Revisión'),    # Stock validado, pendiente de gestión visual
        ('confirmado', 'Confirmado'),   # Stock validado y reservado
        ('pendiente', 'Pendiente'),     # Falta stock (Compra/Producción)
        ('completo', 'Completo'),       # Todo listo para enviar
        ('cancelado', 'Cancelado'),
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    contacto = models.ForeignKey(
        ContactoCliente, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        verbose_name="Contacto Asignado",
        related_name='pedidos_asignados'
    )

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Vendedor")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa (Tenant)")
    
    # Referencia a la cotización origen (opcional)
    cotizacion_origen_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="ID Cotización")

    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    fecha_confirmacion = models.DateTimeField(null=True, blank=True, verbose_name="Confirmado el")
    
    # ESTADO GENERAL DEL PEDIDO
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    notas = models.TextField(blank=True, verbose_name="Notas internas")

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente}"
    
    @property
    def total_pedido(self):
        total = 0
        for detalle in self.detalles.all():
            total += detalle.subtotal
        return total
    
    @property
    def tiene_orden_venta(self):
        """Verifica si este pedido ya tiene al menos una orden de venta (salida) generada"""
        return self.ordenes_venta.exists()

    @property
    def estado_display(self):
        return dict(self.ESTADO_CHOICES).get(self.estado, self.estado)

    @property
    def porcentaje_avance(self):
        """Calcula el porcentaje de partidas que ya están listas (reservadas o completas)"""
        total = self.detalles.count()
        if total == 0:
            return 0
        # Consideramos avanzadas las partidas en estado 'completo' o 'reservado'
        # ya que ambas indican que el material ya está asegurado para el cliente.
        listos = self.detalles.filter(estado_linea__in=['completo', 'reservado']).count()
        return int((listos / total) * 100)


# ==========================================
# 2. MODELO: DETALLE PEDIDO (PARTIDAS)
# ==========================================
class DetallePedido(models.Model):
    """Líneas de pedido con gestión de estado individual"""
    
    ESTADO_LINEA_CHOICES = (
        ('pendiente', 'Pendiente'),     
        ('reservado', 'Reservado'),     
        ('en_proceso', 'Aprobación'),   
        ('comprado', 'Comprado'),       
        ('compra', 'Compra'),           
        ('produccion', 'Producción'),   
        ('parcial', 'Parcial'),         
        ('completo', 'Completo'),       
    )

    pedido = models.ForeignKey('Pedido', related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name="Producto")
    cantidad_solicitada = models.PositiveIntegerField(default=1, verbose_name="Cant. Solicitada")
    cantidad_entregada = models.PositiveIntegerField(default=0, verbose_name="Cant. Entregada")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")
    estado_linea = models.CharField(max_length=20, choices=ESTADO_LINEA_CHOICES, default='pendiente')
    parent_line = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='lineas_hijas',
        verbose_name="Partida Original (Si fue dividida)"
    )

    def __str__(self):
        return f"{self.cantidad_solicitada} x {self.producto.nombre}"

    @property
    def subtotal(self):
        return self.cantidad_solicitada * self.precio_unitario

    @property
    def pendiente_entrega(self):
        return self.cantidad_solicitada - self.cantidad_entregada