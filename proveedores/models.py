from django.db import models
from panel.models import Empresa

class Proveedor(models.Model):
    # Opciones actualizadas para el estado (Sincronizadas con el HTML)
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('suspendido', 'Suspendido'), 
        ('inactivo', 'Inactivo'),
    ]

    # --- DATOS FISCALES ---
    razon_social = models.CharField(max_length=200, verbose_name="Razón Social")
    rfc = models.CharField(max_length=13, verbose_name="RFC", unique=True)
    cp = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código Postal")
    domicilio = models.TextField(blank=True, null=True, verbose_name="Domicilio Fiscal")
    
    # --- CONTACTO PRINCIPAL ---
    contacto_nombre = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre Contacto")
    contacto_telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    contacto_email = models.EmailField(blank=True, null=True, verbose_name="Email")

    # --- CONTROL ---
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo', verbose_name="Estado")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Actualizado en")

    # --- NUEVO CAMPO MULTI-TENANCY ---
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="Empresa"
    )

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.razon_social} ({self.rfc})"

class SucursalProveedor(models.Model):
    """ Sedes o sucursales de un proveedor """
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='sucursales')
    nombre = models.CharField(max_length=150, verbose_name="Nombre de Sucursal")
    direccion = models.TextField(verbose_name="Dirección")

    def __str__(self):
        return f"{self.nombre} - {self.proveedor.razon_social}"

class MapeoProductoProveedor(models.Model):
    """
    Diccionario inteligente: Relaciona una clave de proveedor con un producto interno.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='mapeos_productos')
    producto = models.ForeignKey('core.Producto', on_delete=models.CASCADE, related_name='mapeos_proveedores')
    
    clave_proveedor = models.CharField(max_length=100, verbose_name="Clave en Factura del Proveedor")
    descripcion_proveedor = models.TextField(blank=True, null=True, verbose_name="Descripción en Factura")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mapeo de Producto"
        verbose_name_plural = "Mapeos de Productos"
        unique_together = ('empresa', 'proveedor', 'clave_proveedor')

    def __str__(self):
        return f"{self.proveedor.razon_social} | {self.clave_proveedor} -> {self.producto.nombre}"
