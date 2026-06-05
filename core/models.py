from django.db import models, IntegrityError
from django.db.models import F, Sum 
from panel.models import Empresa
from decimal import Decimal

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="Empresa (Tenant)",
        related_name='categorias_core' # <--- AGREGAR ESTO
    )

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    # --- 1. IDENTIFICACIÓN ---
    clave = models.CharField(max_length=100, blank=True, null=True, verbose_name="Clave")
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    
    TIPO_OPCIONES = [
        ('producto', 'Producto'),
        ('servicio', 'Servicio'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_OPCIONES, default='producto', verbose_name="Tipo")

    ABASTECIMIENTO_OPCIONES = [
        ('stock', 'Stock'),
        ('produccion', 'Producción'),
        ('compra', 'Compra'),
    ]
    tipo_abastecimiento = models.CharField(
        max_length=20, 
        choices=ABASTECIMIENTO_OPCIONES, 
        default='compra', 
        verbose_name="Tipo de Abastecimiento"
    )

    ESTADO_OPCIONES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('descontinuado', 'Descontinuado'),
        ('revision', 'Revisión'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_OPCIONES, default='activo', verbose_name="Estado")

    # --- 2. CLASIFICACIÓN ---
    categoria = models.CharField(max_length=100, blank=True, null=True, verbose_name="Categoría")
    subcategoria = models.CharField(max_length=100, blank=True, null=True, verbose_name="Subcategoría")
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name="Marca")
    modelo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    linea = models.CharField(max_length=100, blank=True, null=True, verbose_name="Línea")
    UNIDAD_OPCIONES = [
        ('H87', 'H87 (Pieza)'),
        ('E48', 'E48 (Unidad de servicio)'),
    ]
    unidad_medida = models.CharField(
        max_length=50, 
        choices=UNIDAD_OPCIONES,
        default="H87", 
        verbose_name="Unidad de Medida"
    )
    iva = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, verbose_name="IVA (%)", help_text="Impuesto al Valor Agregado")
    ieps = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, verbose_name="IEPS (%)", help_text="Impuesto Especial sobre Producción y Servicios")
    tiene_iva = models.BooleanField(default=True, verbose_name="Tiene IVA")

    # --- 3. INVENTARIO Y LOGÍSTICA (CAMBIOS) ---
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    
    # --- ELIMINADO: stock_actual (ahora está en el modelo Inventario) ---
    
    stock_minimo = models.IntegerField(default=0, verbose_name="Stock Mínimo")
    stock_maximo = models.IntegerField(default=1000, verbose_name="Stock Máximo")
    
    maneja_lote = models.BooleanField(default=False, verbose_name="Maneja Lote")
    maneja_serie = models.BooleanField(default=False, verbose_name="Maneja No. Serie")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    empresa = models.ForeignKey('panel.Empresa', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    
    # NUEVO: Vínculo al Test de Calidad (Módulo Producción)
    test_calidad = models.ForeignKey('produccion.Test', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Test de Calidad")

    precios_lista = models.JSONField(default=list, blank=True, verbose_name="Lista de Precios Extra")
    costos_lista = models.JSONField(default=list, blank=True, verbose_name="Lista de Costos Extra")

    def __str__(self):
        return f"{self.nombre}"

    # --- NUEVO: PROPIEDAD PARA CALCULAR STOCK TOTAL EN TODOS LOS ALMACENES ---
    @property
    def stock_total(self):
        # Importamos aquí localmente para evitar errores circulares al cargar el archivo
        from almacenes.models import Inventario
        total = Inventario.objects.filter(producto=self).aggregate(total=Sum('cantidad'))['total']
        return total if total is not None else 0
    
    @property
    def stock_disponible(self):
        """
        Calcula el stock que realmente está libre para vender.
        (Total Físico - Total Reservado en Pedidos)
        """
        from almacenes.models import Inventario
        inventarios = Inventario.objects.filter(producto=self)
        
        total_fisico = inventarios.aggregate(total=Sum('cantidad'))['total'] or 0
        total_reservado = inventarios.aggregate(res=Sum('reservado'))['res'] or 0
        
        return total_fisico - total_reservado

    @property
    def stock_reservado(self):
        """
        Retorna el total de unidades reservadas en pedidos para este producto.
        """
        from almacenes.models import Inventario
        total_reservado = Inventario.objects.filter(
            producto=self
        ).aggregate(res=Sum('reservado'))['res'] or 0
        return total_reservado

    @property
    def costo_promedio_global(self):
        from almacenes.models import Inventario
        inventarios = Inventario.objects.filter(producto=self)
        
        total_unidades = sum(i.cantidad for i in inventarios)
        
        if total_unidades == 0:
            return self.precio_costo
        
        total_valor = sum(i.cantidad * i.costo_promedio for i in inventarios)
        return total_valor / total_unidades

ESTADO_COMPRA_CHOICES = [
    ('borrador', 'Borrador'),
    ('aprobada', 'Aprobada'),
    ('recibida', 'Recibida'),
    ('cancelada', 'Cancelada'),
]

class Transaccion(models.Model):
    TIPO_CHOICES = [
        ('compra', 'Compra'),
        ('venta', 'Venta'),
        ('ajuste', 'Ajuste'),
        ('produccion', 'Producción'),
    ]
    
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    almacen = models.ForeignKey('almacenes.Almacen', on_delete=models.CASCADE, verbose_name="Almacén")

    proveedor = models.ForeignKey(
        'proveedores.Proveedor', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Proveedor"
    )
    
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.IntegerField()
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fecha = models.DateTimeField(auto_now_add=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa (Tenant)")
    
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario")
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia")
    lote = models.CharField(max_length=100, blank=True, null=True, verbose_name="Lote")
    serie = models.CharField(max_length=100, blank=True, null=True, verbose_name="Serie")
    extras_data = models.JSONField(default=list, blank=True, null=True, verbose_name="Datos Extras (Lotes/Series)")
    quitar_reserva = models.IntegerField(default=0, verbose_name="Quitar Reserva")

    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_COMPRA_CHOICES, 
        default='borrador', 
        verbose_name="Estado"
    )

    def save(self, *args, **kwargs):
        from decimal import Decimal
        from almacenes.models import Inventario 
        
        # --- IMPORTANTE: Importamos F e IntegrityError para la concurrencia ---
        from django.db.models import F
        from django.db import IntegrityError
        
        # --- 1. LÓGICA DE PRECIOS ---
        costo_unitario_compra = Decimal('0.00')

        if self.tipo == 'compra':
            if self.cantidad > 0:
                costo_unitario_compra = Decimal(self.total) / Decimal(self.cantidad)
            else:
                costo_unitario_compra = Decimal(self.producto.precio_costo)

            # Actualizamos precio costo referencia (opcional, depende de tu lógica de negocio)
            self.producto.precio_costo = costo_unitario_compra
            self.producto.save()
            self.total = Decimal(self.cantidad) * costo_unitario_compra

        elif self.tipo == 'venta':
            if self.total == 0:
                self.total = Decimal(self.cantidad) * Decimal(self.producto.precio_venta)
            costo_unitario_compra = Decimal(self.producto.precio_costo)
        
        elif self.tipo == 'produccion' or self.tipo == 'ajuste':
            costo_unitario_compra = Decimal(self.producto.precio_costo)

        # --- 2. GESTIÓN DE STOCK ---
        
        # CASO A: COMPRA RECIBIDA o AJUSTE POSITIVO
        if (self.tipo == 'compra' and self.estado == 'recibida') or \
           ((self.tipo == 'ajuste' or self.tipo == 'produccion') and self.cantidad > 0):
            
            if self.producto.tipo != 'servicio':
                Inventario.registrar_ingreso(
                    almacen=self.almacen,
                    producto=self.producto,
                    cantidad_ingreso=abs(self.cantidad),
                    costo_unitario=costo_unitario_compra,
                    referencia=self.referencia or f"{self.get_tipo_display()} {self.id}",
                    lote=self.lote,
                    serie=self.serie,
                    usuario=self.usuario
                )

        # CASO B: VENTA o AJUSTE NEGATIVO
        elif self.tipo == 'venta' or \
             ((self.tipo == 'ajuste' or self.tipo == 'produccion') and self.cantidad < 0):
            
            # Gestionamos el stock solo si NO es un servicio
            if self.producto.tipo != 'servicio':
                try:
                    # Si es venta, quitar_reserva por defecto es la cantidad (ya seteado en el modelo anterior, pero aquí lo hacemos dinámico)
                    q_res = self.quitar_reserva
                    if self.tipo == 'venta' and q_res == 0:
                        q_res = abs(self.cantidad)

                    Inventario.registrar_salida(
                        almacen=self.almacen,
                        producto=self.producto,
                        cantidad_salida=abs(self.cantidad),
                        referencia=self.referencia or f"{self.get_tipo_display()} {self.id}",
                        usuario=self.usuario,
                        extras_data=self.extras_data,
                        quitar_reserva=q_res
                    )
                except Exception as e:
                    raise e
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tipo} - {self.producto.nombre} x{self.cantidad} ({self.almacen.nombre})"
    
class DetalleReceta(models.Model):
    """ Define qué componentes necesita un producto para ser producido """
    # USAMOS 'Producto' ENTRE COMILLAS PARA EVITAR ERRORES DE ORDEN
    producto_padre = models.ForeignKey('Producto', on_delete=models.CASCADE, related_name='receta', verbose_name="Producto Final (Ensamblado)")
    componente = models.ForeignKey('Producto', on_delete=models.PROTECT, related_name='usado_en', verbose_name="Componente")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad Requerida")

    class Meta:
        unique_together = ('producto_padre', 'componente') # Evitar duplicados

    def __str__(self):
        return f"{self.producto_padre.nombre} <-> {self.componente.nombre} (x{self.cantidad})"