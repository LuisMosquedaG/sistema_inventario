from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from core.models import Producto
from pedidos.models import DetallePedido 

class SolicitudCompra(models.Model):
    """Representa una petición de compra al departamento de compras"""
    ESTADO_CHOICES = (
        ('borrador', 'Borrador'),
        ('aprobada', 'Aprobada'),  # <--- AGREGADO
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
    notas = models.TextField(blank=True, verbose_name="Notas / Urgencia")

    def __str__(self):
        return f"Solicitud #{self.id} - {self.get_estado_display()}"
    
        # ... resto de la clase SolicitudCompra ...

    @property
    def solicitante_nombre_corto(self):
        """Devuelve el nombre de usuario sin el dominio (todo antes del @)"""
        if self.solicitante and '@' in self.solicitante.username:
            return self.solicitante.username.split('@')[0]
        return self.solicitante.username if self.solicitante else ''

    @property
    def total_items(self):
        return self.detalles.count()

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