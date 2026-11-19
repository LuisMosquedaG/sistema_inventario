from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from panel.models import Empresa
from preferencias.models import Sucursal

class CentroCosto(models.Model):
    TIPO_CHOICES = [
        ('departamento', 'Departamento'),
        ('proyecto', 'Proyecto / Obra'),
        ('linea_negocio', 'Línea de Negocio'),
        ('vehiculo', 'Vehículo / Maquinaria'),
        ('operativo', 'Operativo / General'),
    ]

    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        related_name='centros_costos', 
        verbose_name="Empresa"
    )
    codigo = models.CharField(max_length=30, verbose_name="Código / Clave")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES, 
        default='departamento', 
        verbose_name="Tipo de Centro"
    )

    # Jerarquía: Centro padre opcional (para subcentros)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subcentros', 
        verbose_name="Centro Padre"
    )

    # Sucursal opcional (si es null, aplica a nivel corporativo / multi-sucursal)
    sucursal = models.ForeignKey(
        Sucursal, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='centros_costos', 
        verbose_name="Sucursal"
    )

    # Almacén asociado opcional (para vincular centros de costo con un almacén físico específico)
    almacen = models.ForeignKey(
        'almacenes.Almacen',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='centros_costos_asociados',
        verbose_name="Almacén Asociado"
    )

    # Responsable del centro
    responsable = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='centros_costo_responsable', 
        verbose_name="Responsable"
    )

    # Usuarios autorizados para imputar o registrar documentos en este centro de costo
    # (Si está vacío, está disponible para todos los usuarios de la empresa)
    usuarios_autorizados = models.ManyToManyField(
        User,
        blank=True,
        related_name='centros_costos_permitidos',
        verbose_name="Usuarios Autorizados a Imputar"
    )

    # Presupuesto mensual asignado
    presupuesto_mensual = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="Presupuesto Mensual"
    )

    # Para proyectos / temporales
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fecha de Fin")

    # Estado y auditoría
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Centro de Costos"
        verbose_name_plural = "Centros de Costos"
        ordering = ['codigo', 'nombre']
        unique_together = ('empresa', 'codigo')

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def es_padre(self):
        return self.subcentros.exists()

    def get_ruta_completa(self):
        if self.parent:
            return f"{self.parent.get_ruta_completa()} > {self.nombre}"
        return self.nombre

    def calcular_egresos_mes(self, anio=None, mes=None):
        """
        Calcula el total consumido en Egresos de tesorería pagados
        (pagos de OCs de productos y servicios + egresos directos).
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        total_egresos = Decimal('0.00')
        from tesoreria.models import Egreso
        from django.db.models import Q
        egresos = Egreso.objects.filter(
            Q(centro_costo=self) | Q(pago_compra__orden_compra__centro_costo=self),
            empresa=self.empresa,
            estado='aplicado',
            fecha__year=anio,
            fecha__month=mes
        ).distinct()
        for eg in egresos:
            total_egresos += Decimal(str(eg.monto_mxn or eg.monto or 0))

        return total_egresos

    def calcular_ingresos_mes(self, anio=None, mes=None):
        """
        Calcula el total de Ingresos de tesorería cobrados
        (cobros de Pedidos de venta + ingresos directos).
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        total_ingresos = Decimal('0.00')
        from tesoreria.models import Ingreso
        from django.db.models import Q
        ingresos = Ingreso.objects.filter(
            Q(centro_costo=self) | Q(pago_pedido__pedido__centro_costo=self),
            empresa=self.empresa,
            estado='aplicado',
            fecha__year=anio,
            fecha__month=mes
        ).distinct()
        for ing in ingresos:
            total_ingresos += Decimal(str(ing.monto_mxn or ing.monto or 0))

        return total_ingresos

    def calcular_gastos_mes(self, anio=None, mes=None):
        """
        Calcula el gasto neto financiero en el mes:
        Total Egresos menos Total Ingresos (igual que en el modal de movimientos).
        """
        return self.calcular_egresos_mes(anio, mes) - self.calcular_ingresos_mes(anio, mes)

    def calcular_comprometido_mes(self, anio=None, mes=None):
        """
        Calcula el monto comprometido en Órdenes de Compra vigentes
        que aún tienen saldo pendiente de pago en tesorería.
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        from compras.models import OrdenCompra
        ocs = OrdenCompra.objects.filter(
            centro_costo=self,
            estado__in=['aprobada', 'recibida', 'parcial'],
            fecha__year=anio,
            fecha__month=mes
        )
        total_comprometido = Decimal('0.00')
        for oc in ocs:
            saldo = oc.saldo_pendiente
            if saldo > 0:
                total_comprometido += Decimal(str(saldo * (oc.tipo_cambio or Decimal('1.0000'))))

        return total_comprometido

    def porcentaje_presupuesto(self, anio=None, mes=None):
        if self.presupuesto_mensual and self.presupuesto_mensual > 0:
            gastos = self.calcular_gastos_mes(anio, mes)
            pct = (gastos / self.presupuesto_mensual) * Decimal('100.0')
            return min(round(pct, 1), Decimal('999.9'))
        return Decimal('0.0')

    def porcentaje_total_comprometido(self, anio=None, mes=None):
        if self.presupuesto_mensual and self.presupuesto_mensual > 0:
            total = self.calcular_gastos_mes(anio, mes) + self.calcular_comprometido_mes(anio, mes)
            pct = (total / self.presupuesto_mensual) * Decimal('100.0')
            return min(round(pct, 1), Decimal('999.9'))
        return Decimal('0.0')

    def usuario_tiene_acceso(self, usuario):
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser or (usuario.username and usuario.username.startswith('madmin@')):
            return True
        if self.responsable_id == usuario.id:
            return True
        # Si no hay usuarios asignados explícitamente, está abierto para todos los usuarios de la empresa
        if not self.usuarios_autorizados.exists():
            return True
        return self.usuarios_autorizados.filter(id=usuario.id).exists()

    @classmethod
    def para_usuario(cls, empresa, usuario):
        """Devuelve los centros activos disponibles para que este usuario registre documentos."""
        qs = cls.objects.filter(empresa=empresa, activo=True)
        if not usuario or not usuario.is_authenticated:
            return qs.order_by('codigo')
        if usuario.is_superuser or (usuario.username and usuario.username.startswith('madmin@')):
            return qs.order_by('codigo')
        from django.db.models import Count, Q
        return qs.annotate(num_autorizados=Count('usuarios_autorizados')).filter(
            Q(num_autorizados=0) |
            Q(usuarios_autorizados=usuario) |
            Q(responsable=usuario)
        ).distinct().order_by('codigo')
