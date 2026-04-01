from django.db import models
from django.db.models import F
from decimal import Decimal
from panel.models import Empresa

class Almacen(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Almacén")
    responsable = models.CharField(max_length=150, blank=True, null=True, verbose_name="Responsable")
    
    # Dirección
    calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle")
    numero_ext = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número Exterior")
    numero_int = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número Interior")
    colonia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Colonia")
    estado = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado")
    cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    
    # Contacto
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    
    # --- RELACIÓN CON EMPRESA ---
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"
        ordering = ['nombre']

# --- MODELO: INVENTARIO ---
class Inventario(models.Model):
    # Usamos 'core.Producto' para evitar errores de importación circular
    producto = models.ForeignKey('core.Producto', on_delete=models.CASCADE, related_name='inventarios')
    almacen = models.ForeignKey('Almacen', on_delete=models.CASCADE, related_name='inventarios')
    cantidad = models.IntegerField(default=0, verbose_name="Cantidad Física")
    reservado = models.PositiveIntegerField(default=0, verbose_name="Cantidad Reservada en Pedidos")
    costo_promedio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Promedio")

    fecha_actualizacion = models.DateTimeField(auto_now=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")

    class Meta:
        unique_together = ('producto', 'almacen') 
        verbose_name = "Stock en Almacén"
        verbose_name_plural = "Stocks en Almacenes"

    def __str__(self):
        return f"{self.producto.nombre} en {self.almacen.nombre}: {self.cantidad}"

    # -----------------------------------------------------------
    # MÉTODO CENTRALIZADO PARA INGRESOS (COMPRAS/PRODUCCIÓN)
    # -----------------------------------------------------------
    @classmethod
    def registrar_ingreso(cls, almacen, producto, cantidad_ingreso, costo_unitario, referencia="Ingreso", lote=None, serie=None):
        """
        Registra una entrada de stock y recalcula el costo promedio.
        Maneja la concurrencia internamente mediante select_for_update.
        """
        # Usamos select_for_update para bloquear la fila mientras calculamos el promedio
        inventario, created = cls.objects.select_for_update().get_or_create(
            producto=producto,
            almacen=almacen,
            # --- CORRECCIÓN: Asignamos la empresa del almacén al crear el inventario ---
            defaults={
                'cantidad': 0, 
                'costo_promedio': Decimal('0.00'),
                'empresa': almacen.empresa 
            }
        )

        cantidad_anterior = Decimal(inventario.cantidad or 0)
        costo_anterior = Decimal(inventario.costo_promedio or 0)
        cantidad_nueva = Decimal(cantidad_ingreso)
        costo_compra = Decimal(costo_unitario)

        nuevo_total = cantidad_anterior + cantidad_nueva

        # Cálculo del nuevo costo promedio
        if cantidad_anterior == 0:
            nuevo_promedio = costo_compra
        else:
            valor_anterior = cantidad_anterior * costo_anterior
            valor_compra_total = cantidad_nueva * costo_compra
            nuevo_promedio = (valor_anterior + valor_compra_total) / nuevo_total

        # Guardamos cambios
        inventario.cantidad = nuevo_total
        inventario.costo_promedio = nuevo_promedio
        inventario.save()

        # REGISTRAR EN KARDEX
        Kardex.objects.create(
            empresa=almacen.empresa,
            producto=producto,
            almacen=almacen,
            tipo_movimiento='entrada',
            cantidad=cantidad_nueva,
            stock_anterior=cantidad_anterior,
            stock_nuevo=nuevo_total,
            referencia=referencia,
            lote=lote,
            serie=serie
        )
        
        return inventario

    # -----------------------------------------------------------
    # MÉTODO CENTRALIZADO PARA SALIDAS (VENTAS)
    # -----------------------------------------------------------
    @classmethod
    def registrar_salida(cls, almacen, producto, cantidad_salida, referencia="Salida", lote=None, serie=None):
        """
        Registra una salida de stock de forma atómica.
        Lanza IntegrityError si no hay stock suficiente.
        """
        from django.db import IntegrityError
        
        cantidad_a_restar = Decimal(cantidad_salida)
        
        # Bloqueamos y buscamos
        inventario = cls.objects.select_for_update().get(
            producto=producto,
            almacen=almacen
        )

        if inventario.cantidad < cantidad_a_restar:
            raise IntegrityError(
                f"Stock insuficiente en {almacen.nombre}. "
                f"Disponible: {inventario.cantidad}, Solicitado: {cantidad_a_restar}"
            )
        
        cantidad_anterior = Decimal(inventario.cantidad)
        nuevo_total = cantidad_anterior - cantidad_a_restar

        # Resta atómica
        inventario.cantidad = nuevo_total
        inventario.save()

        # REGISTRAR EN KARDEX
        Kardex.objects.create(
            empresa=almacen.empresa,
            producto=producto,
            almacen=almacen,
            tipo_movimiento='salida',
            cantidad=cantidad_a_restar,
            stock_anterior=cantidad_anterior,
            stock_nuevo=nuevo_total,
            referencia=referencia,
            lote=lote,
            serie=serie
        )
        
        return inventario

# --- MODELO: KARDEX ---
class Kardex(models.Model):
    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('ajuste', 'Ajuste'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    producto = models.ForeignKey('core.Producto', on_delete=models.CASCADE, related_name='movimientos_kardex')
    almacen = models.ForeignKey(Almacen, on_delete=models.CASCADE, related_name='movimientos_kardex')
    
    fecha = models.DateTimeField(auto_now_add=True)
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    
    stock_anterior = models.DecimalField(max_digits=10, decimal_places=2)
    stock_nuevo = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NUEVOS CAMPOS: LOTE Y SERIE
    lote = models.CharField(max_length=100, blank=True, null=True, verbose_name="Lote")
    serie = models.CharField(max_length=100, blank=True, null=True, verbose_name="Núm. Serie")
    
    referencia = models.CharField(max_length=200, blank=True, null=True, help_text="Ej: REC-0001, OV-0005, Ajuste manual")

    class Meta:
        verbose_name = "Movimiento de Kardex"
        verbose_name_plural = "Movimientos de Kardex"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.producto.nombre} - {self.tipo_movimiento} ({self.cantidad})"
