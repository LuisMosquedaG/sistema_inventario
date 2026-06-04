from django.db import models
from django.db.models import F
from decimal import Decimal
from django.contrib.auth.models import User
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
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
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
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")

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
    def registrar_ingreso(cls, almacen, producto, cantidad_ingreso, costo_unitario, referencia="Ingreso", lote=None, serie=None, usuario=None):
        """
        Registra una entrada de stock y recalcula el costo promedio.
        Maneja la concurrencia internamente mediante select_for_update.
        """
        # Usamos select_for_update para bloquear la fila mientras calculamos el promedio
        inventario, created = cls.objects.select_for_update().get_or_create(
            producto=producto,
            almacen=almacen,
            # --- CORRECCIÓN: Asignamos la empresa y sucursal del almacén al crear el inventario ---
            defaults={
                'cantidad': 0, 
                'costo_promedio': Decimal('0.00'),
                'empresa': almacen.empresa,
                'sucursal': almacen.sucursal
            }
        )

        cantidad_anterior = Decimal(inventario.cantidad or 0)
        costo_anterior = Decimal(inventario.costo_promedio or 0)
        cantidad_nueva = Decimal(cantidad_ingreso)
        costo_compra = Decimal(costo_unitario)

        nuevo_total = cantidad_anterior + cantidad_nueva

        # Cálculo del nuevo costo promedio
        # 1. Si no había stock o era negativo, el nuevo costo es el de esta compra
        if cantidad_anterior <= 0:
            nuevo_promedio = costo_compra
        # 2. Si el nuevo total es 0 (ej. ingreso negativo que anula el stock), mantenemos el costo anterior para no dividir por cero
        elif nuevo_total == 0:
            nuevo_promedio = costo_anterior
        # 3. Caso normal: promedio ponderado
        else:
            valor_anterior = cantidad_anterior * costo_anterior
            valor_compra_total = cantidad_nueva * costo_compra
            nuevo_promedio = (valor_anterior + valor_compra_total) / nuevo_total

        # Guardamos cambios y aseguramos sucursal/empresa
        inventario.cantidad = nuevo_total
        inventario.costo_promedio = nuevo_promedio
        inventario.empresa = almacen.empresa
        inventario.sucursal = almacen.sucursal
        inventario.save()

        # REGISTRAR EN KARDEX
        Kardex.objects.create(
            empresa=almacen.empresa,
            sucursal=almacen.sucursal,
            producto=producto,
            almacen=almacen,
            tipo_movimiento='entrada',
            cantidad=cantidad_nueva,
            stock_anterior=cantidad_anterior,
            stock_nuevo=nuevo_total,
            referencia=referencia,
            lote=lote,
            serie=serie,
            usuario=usuario
        )
        
        return inventario

    # -----------------------------------------------------------
    # MÉTODO CENTRALIZADO PARA SALIDAS (VENTAS/PRODUCCIÓN/AJUSTES)
    # -----------------------------------------------------------
    @classmethod
    def registrar_salida(cls, almacen, producto, cantidad_salida, referencia="Salida", quitar_reserva=0, extras_data=None, usuario=None):
        """
        Registra una salida de stock de forma atómica.
        Lanza IntegrityError si no hay stock suficiente.
        
        quitar_reserva: cantidad a descontar del campo 'reservado'.
        extras_data: lista de dicts [{'id': ID_EXTRA, 'qty': CANTIDAD}, ...] 
        """
        from django.db import IntegrityError, transaction
        from django.db.models import F
        from recepciones.models import DetalleRecepcionExtra
        
        cantidad_a_restar = Decimal(str(cantidad_salida))
        
        with transaction.atomic():
            # Bloqueamos y buscamos el registro de inventario
            inventario = cls.objects.select_for_update().get(
                producto=producto,
                almacen=almacen
            )

            if inventario.cantidad < cantidad_a_restar:
                raise IntegrityError(
                    f"Stock insuficiente para {producto.nombre} en {almacen.nombre}. "
                    f"Disponible: {inventario.cantidad}, Solicitado: {cantidad_a_restar}"
                )
            
            cantidad_anterior = Decimal(str(inventario.cantidad))
            
            # 1. Resta física de inventario
            inventario.cantidad = F('cantidad') - cantidad_a_restar
            
            # 2. Manejo de Reservas (si aplica)
            if quitar_reserva > 0:
                # No permitir que la reserva sea negativa
                monto_reserva = Decimal(str(quitar_reserva))
                real_quitar = min(monto_reserva, Decimal(str(inventario.reservado)))
                inventario.reservado = F('reservado') - real_quitar
            
            inventario.save()
            inventario.refresh_from_db()

            # 3. Procesar Trazabilidad (Lotes / Series)
            lote_kardex, serie_kardex = None, None
            if extras_data:
                for item in extras_data:
                    eid = item.get('id')
                    qty = Decimal(str(item.get('qty', 1)))
                    
                    # Bloqueamos el registro del lote/serie
                    extra = DetalleRecepcionExtra.objects.select_for_update().get(id=eid, almacen=almacen)
                    
                    if extra.tipo == 'serie':
                        extra.almacen = None # El equipo sale del almacén
                        extra.save()
                        serie_kardex = extra.serie # Guardamos para el Kardex
                    else:
                        # Validación de stock en el lote
                        if extra.cantidad_lote < qty:
                            raise IntegrityError(f"Stock insuficiente en el lote {extra.lote}. Disponible: {extra.cantidad_lote}")
                        
                        extra.cantidad_lote = F('cantidad_lote') - qty
                        extra.save()
                        lote_kardex = extra.lote

            # 4. REGISTRAR EN KARDEX
            Kardex.objects.create(
                empresa=almacen.empresa,
                sucursal=almacen.sucursal,
                producto=producto,
                almacen=almacen,
                tipo_movimiento='salida',
                cantidad=cantidad_a_restar,
                stock_anterior=cantidad_anterior,
                stock_nuevo=inventario.cantidad,
                referencia=referencia,
                lote=lote_kardex,
                serie=serie_kardex,
                usuario=usuario
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
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
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
    
    # NUEVO CAMPO: USUARIO
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario Responsable")

    def save(self, *args, **kwargs):
        if not self.sucursal and self.almacen:
            self.sucursal = self.almacen.sucursal
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Movimiento de Kardex"
        verbose_name_plural = "Movimientos de Kardex"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.producto.nombre} - {self.tipo_movimiento} ({self.cantidad})"
