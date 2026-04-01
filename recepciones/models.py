from django.db import models
from django.utils import timezone
from compras.models import OrdenCompra, DetalleCompra
from almacenes.models import Almacen
from panel.models import Empresa
from decimal import Decimal

class Recepcion(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]

    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name='recepciones')
    almacen = models.ForeignKey(Almacen, on_delete=models.PROTECT)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    
    # NUEVOS CAMPOS: MONEDA Y TC AL RECIBIR
    moneda = models.ForeignKey('preferencias.Moneda', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Moneda")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, verbose_name="Tipo de Cambio")

    fecha = models.DateField(default=timezone.now)
    factura = models.CharField("Factura/Remito", max_length=100, blank=True, null=True)
    pedimento = models.CharField("Pedimento", max_length=100, blank=True, null=True)
    aduana = models.CharField("Aduana", max_length=100, blank=True, null=True)
    fecha_pedimento = models.DateField("Fecha Pedimento", blank=True, null=True, help_text="Fecha del documento de aduana")
    importe_aduana = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Importación Aduanal", help_text="Costo total de impuestos/aduana")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='completada')
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"REC-{self.id:04d} | OC-{self.orden_compra.id}"

    @property
    def total(self):
        return sum(detalle.subtotal for detalle in self.detalles.all())

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class DetalleRecepcion(models.Model):
    """ Ítems recibidos """
    recepcion = models.ForeignKey(Recepcion, on_delete=models.CASCADE, related_name='detalles')
    
    detalle_compra = models.ForeignKey(
        DetalleCompra, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='recepciones_asociadas',
        verbose_name="Partida de Orden de Compra",
    )
    
    producto = models.ForeignKey('core.Producto', on_delete=models.PROTECT)
    cantidad_recibida = models.PositiveIntegerField(default=0)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad_recibida * self.costo_unitario

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # SI LA RECEPCIÓN SE COMPLETA, DISPARAMOS LA SINCRONIZACIÓN
        if is_new and self.recepcion.estado == 'completada' and self.detalle_compra:
            self._sincronizar_todo()

    def _sincronizar_todo(self):
        """
        Función maestra para avisar a Pedidos y Producción.
        """
        try:
            # USAMOS LA ETIQUETA DIRECTA QUE PUSIMOS EN LA OC
            pedido_linea = self.detalle_compra.detalle_pedido_origen
            
            if not pedido_linea:
                # Si no tiene etiqueta directa, intentamos el camino largo por si acaso
                # (Para compatibilidad con órdenes viejas)
                return

            from produccion.models import OrdenProduccion
            from core.models import DetalleReceta
            
            # --- CASO 1: EL PRODUCTO RECIBIDO ES EL QUE EL CLIENTE QUIERE (Compra/Stock) ---
            if pedido_linea.producto == self.producto:
                if pedido_linea.estado_linea != 'completo':
                    pedido_linea.estado_linea = 'pendiente'
                    pedido_linea.save()
                    print(f"*** VÍNCULO DIRECTO: {self.producto.nombre} liberado en Pedido #{pedido_linea.pedido.id} ***")

            # --- CASO 2: EL PRODUCTO RECIBIDO ES UN INGREDIENTE (Producción) ---
            else:
                # Buscamos órdenes de taller esperando materiales para este pedido
                ops = OrdenProduccion.objects.filter(
                    pedido_origen=pedido_linea.pedido,
                    producto=pedido_linea.producto,
                    estado='pendiente'
                )

                for op in ops:
                    receta = DetalleReceta.objects.filter(producto_padre=op.producto)
                    listo = True
                    for item in receta:
                        # Verificamos si ya hay stock suficiente de cada componente
                        if item.componente.stock_disponible < (item.cantidad * op.cantidad):
                            listo = False
                            break
                    
                    if listo:
                        op.estado = 'listo'
                        op.save()
                        
                        # ELIMINADO: Ya no marcamos el pedido_linea como 'pendiente' aquí.
                        # El pedido se liberará hasta que en el Módulo de Producción 
                        # se le dé al botón "Finalizar Trabajo".
                        
                        print(f"*** TALLER: Orden {op.folio} lista para iniciar ***")

        except Exception as e:
            print(f"Error en sincronización maestra: {e}")

class DetalleRecepcionExtra(models.Model):
    """ Guarda información de Lotes y Números de Serie """
    detalle_recepcion = models.ForeignKey(DetalleRecepcion, on_delete=models.CASCADE, related_name='extras')
    tipo = models.CharField(max_length=10, choices=[('lote', 'Lote'), ('serie', 'Serie')])
    lote = models.CharField(max_length=50, blank=True, null=True)
    cantidad_lote = models.PositiveIntegerField(default=0)
    serie = models.CharField(max_length=100, blank=True, null=True)
    
    # NUEVO: RASTREO DE UBICACIÓN ACTUAL
    almacen = models.ForeignKey('almacenes.Almacen', on_delete=models.CASCADE, related_name='items_extra', null=True, blank=True)

    def __str__(self):
        return f"{self.tipo}: {self.lote or self.serie} ({self.almacen.nombre if self.almacen else 'Sin almacén'})"
