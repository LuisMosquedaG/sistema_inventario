from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from core.models import Producto
from pedidos.models import Pedido
from almacenes.models import Almacen

class OrdenProduccion(models.Model):
    """Representa un trabajo de fabricación en el taller"""
    
    ESTADO_CHOICES = (
        ('borrador', 'Borrador'),       # Recién creada, editable
        ('en_proceso', 'En Proceso'),    # Ya se está fabricando
        ('testeo', 'Testeo / Calidad'),  # Pruebas finales
        ('terminado', 'Terminado'),      # Producto final listo
        ('cancelado', 'Cancelada'),
    )

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa (Tenant)")
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, verbose_name="Producto a Fabricar", limit_choices_to={'tipo_abastecimiento': 'produccion'})
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad a Producir")
    
    pedido_origen = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_produccion', verbose_name="Pedido Origen")
    solicitante = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_produccion', verbose_name="Usuario que solicitó")
    
    almacen = models.ForeignKey(Almacen, on_delete=models.PROTECT, verbose_name="Almacén de Entrada (PT)", related_name='ordenes_entrada')
    almacen_materia_prima = models.ForeignKey(Almacen, on_delete=models.PROTECT, verbose_name="Almacén de Salida (MP)", related_name='ordenes_salida', null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos_asignados', verbose_name="Responsable del Taller")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Solicitud")
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Inicio")
    fecha_terminado = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Término")
    
    notas = models.TextField(blank=True, verbose_name="Notas del Maestro")

    class Meta:
        verbose_name = "Orden de Producción"
        verbose_name_plural = "Órdenes de Producción"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"OP-{self.id:04d} | {self.producto.nombre} ({self.cantidad} pz)"

    @property
    def folio(self):
        return f"OP-{self.id:04d}"

class DetalleOrdenProduccion(models.Model):
    """Componentes específicos que se usarán para UNA orden de producción"""
    orden_produccion = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, verbose_name="Componente")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad Requerida")

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (OP-{self.orden_produccion.id})"

# ==========================================
# NUEVOS MODELOS PARA CONTROL DE CALIDAD
# ==========================================

class Test(models.Model):
    """Cabecera del manual de revisión (Check-list)"""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Test")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción / Objetivo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Test de Calidad"
        verbose_name_plural = "Tests de Calidad"

    def __str__(self):
        return self.nombre

class ItemTest(models.Model):
    """Tarea individual dentro de un Test"""
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='items')
    tarea = models.CharField(max_length=255, verbose_name="Tarea a realizar")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden de aparición")

    class Meta:
        ordering = ['orden']
        verbose_name = "Tarea del Test"
        verbose_name_plural = "Tareas del Test"

    def __str__(self):
        return self.tarea

class ResultadoTestOP(models.Model):
    """Guarda el resultado de una tarea específica en una orden de producción real"""
    orden_produccion = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name='resultados_test')
    item_test = models.ForeignKey(ItemTest, on_delete=models.CASCADE)
    completado = models.BooleanField(default=False, verbose_name="¿Pasó la prueba?")
    fecha_chequeo = models.DateTimeField(null=True, blank=True)
    usuario_verifico = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Inspeccionado por")

    class Meta:
        unique_together = ('orden_produccion', 'item_test')

    def __str__(self):
        return f"{self.orden_produccion.folio} - {self.item_test.tarea}"
