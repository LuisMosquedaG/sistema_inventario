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

    CONTROL_PRESUPUESTO_CHOICES = [
        ('desactivado', 'Desactivado (Solo informativo)'),
        ('advertencia', 'Advertencia (Permitir con aviso de sobregiro)'),
        ('bloqueo', 'Bloqueo duro (Impedir compras si excede presupuesto)'),
    ]

    # Presupuesto mensual asignado
    presupuesto_mensual = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="Presupuesto Mensual"
    )

    # Control Activo de Disponibilidad Presupuestal (SAP Availability Control)
    control_presupuesto = models.CharField(
        max_length=20,
        choices=CONTROL_PRESUPUESTO_CHOICES,
        default='desactivado',
        verbose_name="Control de Presupuesto (Disponibilidad)"
    )
    tolerancia_presupuesto = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Tolerancia de Sobregiro (%)",
        help_text="Porcentaje adicional sobre el presupuesto antes de activar la advertencia o bloqueo"
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

    def calcular_distribuciones_emitidas_mes(self, anio=None, mes=None):
        """
        Total de costos transferidos/prorrateados hacia otros centros
        donde este centro actuó como emisor (disminuye su saldo de gasto).
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        total = Decimal('0.00')
        ejecuciones = self.ciclos_como_emisor.filter(
            ejecuciones__anio=anio,
            ejecuciones__mes=mes,
            ejecuciones__estado='aplicado'
        ).values_list('ejecuciones__monto_total_distribuido', flat=True)
        for m in ejecuciones:
            total += Decimal(str(m or 0))
        return total

    def calcular_distribuciones_recibidas_mes(self, anio=None, mes=None):
        """
        Total de costos recibidos por distribución/prorrateo de centros emisores
        (incrementa el gasto real absorbido por este centro).
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        total = Decimal('0.00')
        detalles = self.distribuciones_recibidas.filter(
            ejecucion__anio=anio,
            ejecucion__mes=mes,
            ejecucion__estado='aplicado'
        )
        for d in detalles:
            total += Decimal(str(d.monto_cargado or 0))
        return total

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
        Calcula el gasto neto financiero en el mes considerando prorrateos internos:
        Total Egresos Directos 
        - Total Ingresos 
        + Prorrateos Recibidos (absorbidos)
        - Prorrateos Emitidos (distribuidos hacia otros)
        """
        egresos = self.calcular_egresos_mes(anio, mes)
        ingresos = self.calcular_ingresos_mes(anio, mes)
        dist_recibidas = self.calcular_distribuciones_recibidas_mes(anio, mes)
        dist_emitidas = self.calcular_distribuciones_emitidas_mes(anio, mes)
        return (egresos - ingresos) + dist_recibidas - dist_emitidas

    def obtener_estado_prorrateo_mes(self, anio=None, mes=None):
        """
        Analiza detalladamente los comprobantes de egreso del periodo para este centro de costo.
        Detecta comprobantes que ya fueron aplicados en ciclos anteriores y aísla los movimientos
        posteriores no prorrateados para evitar inflar o duplicar los montos distribuidos.
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        from tesoreria.models import Egreso
        from django.db.models import Q

        # 1. Obtener todos los comprobantes de egreso aplicados para este centro en el mes
        egresos_qs = Egreso.objects.filter(
            Q(centro_costo=self) | Q(pago_compra__orden_compra__centro_costo=self),
            empresa=self.empresa,
            estado='aplicado',
            fecha__year=anio,
            fecha__month=mes
        ).select_related(
            'caja_banco', 'proveedor', 'pago_compra__orden_compra__proveedor', 'clase_costo'
        ).distinct().order_by('fecha', 'id')

        # 2. Obtener ejecuciones aplicadas donde este centro fue emisor
        ejecuciones_previas = self.ciclos_como_emisor.filter(
            ejecuciones__anio=anio,
            ejecuciones__mes=mes,
            ejecuciones__estado='aplicado'
        )
        # Acceder a las instancias de EjecucionCicloDistribucion aplicadas
        from centros_costos.models import EjecucionCicloDistribucion
        ejecuciones_objs = EjecucionCicloDistribucion.objects.filter(
            ciclo__centro_emisor=self,
            empresa=self.empresa,
            anio=anio,
            mes=mes,
            estado='aplicado'
        ).select_related('ciclo', 'usuario').prefetch_related('comprobantes_egresos', 'detalles__centro_receptor').order_by('fecha_ejecucion')

        ids_egresos_prorrateados = set()
        monto_total_ya_prorrateado = Decimal('0.00')

        for ejec in ejecuciones_objs:
            monto_total_ya_prorrateado += Decimal(str(ejec.monto_total_distribuido or 0))
            for eg in ejec.comprobantes_egresos.all():
                ids_egresos_prorrateados.add(eg.id)

        # 3. Clasificar cada comprobante: ya aplicado vs nuevo/posterior pendiente
        comprobantes_prorrateados = []
        comprobantes_pendientes = []
        total_egresos_mes = Decimal('0.00')
        total_pendientes = Decimal('0.00')

        for eg in egresos_qs:
            monto = Decimal(str(eg.monto_mxn or eg.monto or 0))
            total_egresos_mes += monto

            prov = '--'
            if eg.proveedor:
                prov = eg.proveedor.razon_social
            elif eg.pago_compra and eg.pago_compra.orden_compra and eg.pago_compra.orden_compra.proveedor:
                prov = eg.pago_compra.orden_compra.proveedor.razon_social

            concepto_disp = eg.concepto or '--'
            if eg.pago_compra and eg.pago_compra.orden_compra:
                concepto_disp = f"OC-{eg.pago_compra.orden_compra.id:04d} - {prov}"

            item = {
                'id': eg.id,
                'folio': f"EGR-{eg.id:04d}",
                'fecha': eg.fecha.strftime('%d/%m/%Y'),
                'fecha_iso': eg.fecha.isoformat(),
                'concepto': concepto_disp,
                'proveedor': prov,
                'clase_costo': eg.clase_costo.codigo if eg.clase_costo else '--',
                'monto': float(monto),
            }

            if eg.id in ids_egresos_prorrateados:
                comprobantes_prorrateados.append(item)
            else:
                comprobantes_pendientes.append(item)
                total_pendientes += monto

        # Fallback de compatibilidad retroactiva si hubo ejecuciones previas sin relación M2M guardada
        if not ids_egresos_prorrateados and monto_total_ya_prorrateado > 0:
            acumulado_fallback = Decimal('0.00')
            comp_prev = []
            comp_pend = []
            tot_pend = Decimal('0.00')
            for c in comprobantes_pendientes:
                m_dec = Decimal(str(c['monto']))
                if acumulado_fallback + m_dec <= monto_total_ya_prorrateado:
                    acumulado_fallback += m_dec
                    comp_prev.append(c)
                else:
                    comp_pend.append(c)
                    tot_pend += m_dec
            comprobantes_prorrateados = comp_prev
            comprobantes_pendientes = comp_pend
            total_pendientes = max(Decimal('0.00'), total_egresos_mes - monto_total_ya_prorrateado)

        # 4. Descontar ingresos acumulados del centro si existen
        ingresos_emisor = self.calcular_ingresos_mes(anio, mes)
        saldo_remanente_real = max(Decimal('0.00'), total_pendientes - ingresos_emisor)

        # 5. Resumen estructurado de ejecuciones anteriores
        historial_previo = []
        for ej in ejecuciones_objs:
            historial_previo.append({
                'id': ej.id,
                'ciclo_codigo': ej.ciclo.codigo,
                'ciclo_nombre': ej.ciclo.nombre,
                'fecha_ejecucion': ej.fecha_ejecucion.strftime('%d/%m/%Y %H:%M') if ej.fecha_ejecucion else '--',
                'monto_distribuido': float(ej.monto_total_distribuido),
                'usuario': (ej.usuario.get_full_name() or ej.usuario.username) if ej.usuario else '--',
                'cant_comprobantes': ej.comprobantes_egresos.count()
            })

        return {
            'total_egresos_mes': float(total_egresos_mes),
            'monto_ya_prorrateado': float(monto_total_ya_prorrateado),
            'total_pendiente': float(saldo_remanente_real),
            'comprobantes_pendientes': comprobantes_pendientes,
            'comprobantes_prorrateados': comprobantes_prorrateados,
            'cant_pendientes': len(comprobantes_pendientes),
            'cant_prorrateados': len(comprobantes_prorrateados),
            'ejecuciones_previas': historial_previo,
            'tiene_pendientes': saldo_remanente_real > 0,
            'todos_prorrateados': (monto_total_ya_prorrateado > 0 and saldo_remanente_real == 0),
        }

    def calcular_comprometido_mes(self, anio=None, mes=None, exclude_orden_id=None):
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
        if exclude_orden_id:
            ocs = ocs.exclude(id=exclude_orden_id)

        total_comprometido = Decimal('0.00')
        for oc in ocs:
            saldo = oc.saldo_pendiente
            if saldo > 0:
                total_comprometido += Decimal(str(saldo * (oc.tipo_cambio or Decimal('1.0000'))))

        return total_comprometido

    def validar_disponibilidad(self, monto_nuevo=Decimal('0.00'), anio=None, mes=None, exclude_orden_id=None):
        """
        Control Activo de Disponibilidad (SAP Availability Control / AVC).
        Evalúa si un monto proyectado excede el presupuesto disponible del centro de costos
        aplicando la regla configurada (desactivado, advertencia, bloqueo duro) y tolerancia.
        """
        now = timezone.now()
        if not anio:
            anio = now.year
        if not mes:
            mes = now.month

        presupuesto = self.presupuesto_mensual or Decimal('0.00')
        tolerancia_pct = self.tolerancia_presupuesto or Decimal('0.00')
        limite_maximo = presupuesto * (Decimal('1.00') + (tolerancia_pct / Decimal('100.00')))

        gastos_reales = self.calcular_gastos_mes(anio, mes)
        comprometido = self.calcular_comprometido_mes(anio, mes, exclude_orden_id=exclude_orden_id)
        consumo_actual = gastos_reales + comprometido

        disponible_actual = max(Decimal('0.00'), presupuesto - consumo_actual)
        disponible_con_tolerancia = max(Decimal('0.00'), limite_maximo - consumo_actual)

        monto_compra = Decimal(str(monto_nuevo or 0))
        proyeccion = consumo_actual + monto_compra

        excede_tolerancia = (proyeccion > limite_maximo) if presupuesto > 0 else False
        exceso_monto = max(Decimal('0.00'), proyeccion - limite_maximo) if presupuesto > 0 else Decimal('0.00')
        pct_consumo_proyectado = ((proyeccion / presupuesto) * Decimal('100.0')) if presupuesto > 0 else Decimal('0.0')

        control = self.control_presupuesto or 'desactivado'

        if control == 'desactivado' or presupuesto <= 0:
            return {
                'permitido': True,
                'tipo_control': 'desactivado',
                'bloquea': False,
                'excede': False,
                'presupuesto': float(presupuesto),
                'tolerancia_pct': float(tolerancia_pct),
                'limite_maximo': float(limite_maximo),
                'consumo_actual': float(consumo_actual),
                'disponible_actual': float(disponible_actual),
                'disponible_con_tolerancia': float(disponible_con_tolerancia),
                'monto_nuevo': float(monto_compra),
                'proyeccion': float(proyeccion),
                'exceso_monto': 0.0,
                'pct_proyectado': float(pct_consumo_proyectado),
                'mensaje': 'Sin control presupuestal activo.'
            }

        if control == 'advertencia':
            if excede_tolerancia:
                mensaje = (
                    f"Aviso Presupuestal: El centro de costos '{self.codigo} - {self.nombre}' "
                    f"tiene disponible ${disponible_actual:,.2f} MXN (presupuesto: ${presupuesto:,.2f} MXN). "
                    f"Esta compra de ${monto_compra:,.2f} MXN proyecta un consumo del {pct_consumo_proyectado:.1f}% "
                    f"(excediendo el límite autorizado con tolerancia en ${exceso_monto:,.2f} MXN)."
                )
                return {
                    'permitido': True,
                    'tipo_control': 'advertencia',
                    'bloquea': False,
                    'excede': True,
                    'presupuesto': float(presupuesto),
                    'tolerancia_pct': float(tolerancia_pct),
                    'limite_maximo': float(limite_maximo),
                    'consumo_actual': float(consumo_actual),
                    'disponible_actual': float(disponible_actual),
                    'disponible_con_tolerancia': float(disponible_con_tolerancia),
                    'monto_nuevo': float(monto_compra),
                    'proyeccion': float(proyeccion),
                    'exceso_monto': float(exceso_monto),
                    'pct_proyectado': float(pct_consumo_proyectado),
                    'mensaje': mensaje
                }
            return {
                'permitido': True,
                'tipo_control': 'advertencia',
                'bloquea': False,
                'excede': False,
                'presupuesto': float(presupuesto),
                'tolerancia_pct': float(tolerancia_pct),
                'limite_maximo': float(limite_maximo),
                'consumo_actual': float(consumo_actual),
                'disponible_actual': float(disponible_actual),
                'disponible_con_tolerancia': float(disponible_con_tolerancia),
                'monto_nuevo': float(monto_compra),
                'proyeccion': float(proyeccion),
                'exceso_monto': 0.0,
                'pct_proyectado': float(pct_consumo_proyectado),
                'mensaje': 'Presupuesto dentro del límite autorizado.'
            }

        if control == 'bloqueo':
            if excede_tolerancia:
                mensaje = (
                    f"Bloqueo Presupuestal: El centro de costos '{self.codigo} - {self.nombre}' "
                    f"cuenta con un saldo disponible de ${disponible_actual:,.2f} MXN (presupuesto mensual: ${presupuesto:,.2f} MXN). "
                    f"La compra (${monto_compra:,.2f} MXN) excede el límite máximo disponible "
                    f"por ${exceso_monto:,.2f} MXN (Consumo proyectado: {pct_consumo_proyectado:.1f}%)."
                )
                return {
                    'permitido': False,
                    'tipo_control': 'bloqueo',
                    'bloquea': True,
                    'excede': True,
                    'presupuesto': float(presupuesto),
                    'tolerancia_pct': float(tolerancia_pct),
                    'limite_maximo': float(limite_maximo),
                    'consumo_actual': float(consumo_actual),
                    'disponible_actual': float(disponible_actual),
                    'disponible_con_tolerancia': float(disponible_con_tolerancia),
                    'monto_nuevo': float(monto_compra),
                    'proyeccion': float(proyeccion),
                    'exceso_monto': float(exceso_monto),
                    'pct_proyectado': float(pct_consumo_proyectado),
                    'mensaje': mensaje
                }
            return {
                'permitido': True,
                'tipo_control': 'bloqueo',
                'bloquea': False,
                'excede': False,
                'presupuesto': float(presupuesto),
                'tolerancia_pct': float(tolerancia_pct),
                'limite_maximo': float(limite_maximo),
                'consumo_actual': float(consumo_actual),
                'disponible_actual': float(disponible_actual),
                'disponible_con_tolerancia': float(disponible_con_tolerancia),
                'monto_nuevo': float(monto_compra),
                'proyeccion': float(proyeccion),
                'exceso_monto': 0.0,
                'pct_proyectado': float(pct_consumo_proyectado),
                'mensaje': 'Presupuesto disponible verificado.'
            }

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


class ClaseCosto(models.Model):
    """
    Catálogo de Clases de Costo (Cost Elements - Estilo SAP CO).
    - Primarias: Gastos directos derivados de facturas de proveedores, insumos, compras externas y egresos de caja.
    - Secundarias: Costos generados internamente por distribución, sub-reparto de centros de soporte o tarifas de absorción.
    """
    TIPO_CHOICES = [
        ('primaria', 'Primaria (Gasto externo)'),
        ('secundaria', 'Secundaria (Gasto interno)'),
    ]

    CATEGORIA_CHOICES = [
        ('materiales', 'Materiales y Suministros'),
        ('servicios', 'Servicios Externos / Contratistas'),
        ('personal', 'Mano de Obra / Personal'),
        ('mantenimiento', 'Mantenimiento y Reparación'),
        ('instalaciones', 'Instalaciones / Rentas / Servicios Básicos'),
        ('transporte', 'Logística, Combustibles y Fletes'),
        ('administrativo', 'Gastos Administrativos / Oficina'),
        ('distribucion_interna', 'Distribución / Sub-reparto Interno'),
        ('otros', 'Otros Gastos Operativos'),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='clases_costos',
        verbose_name="Empresa"
    )
    codigo = models.CharField(max_length=30, verbose_name="Código / Cuenta Contable")
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Clase de Costo")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='primaria',
        verbose_name="Tipo de Clase de Costo"
    )
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        default='materiales',
        verbose_name="Categoría Analítica"
    )

    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Clase de Costo"
        verbose_name_plural = "Clases de Costos"
        ordering = ['codigo', 'nombre']
        unique_together = ('empresa', 'codigo')

    def __str__(self):
        return f"{self.codigo} - {self.nombre} ({self.get_tipo_display().split()[0]})"

    @classmethod
    def sembrar_catalogo_estandar(cls, empresa):
        """
        Crea un catálogo estándar sugerido para la empresa si no tiene ninguna clase configurada.
        """
        if cls.objects.filter(empresa=empresa).exists():
            return 0

        catalogo_base = [
            # Primarias
            ('5101', 'Materia Prima e Insumos Directos', 'primaria', 'materiales', 'Consumo directo de insumos para la operación o producción'),
            ('5102', 'Refacciones y Repuestos', 'primaria', 'mantenimiento', 'Piezas de recambio y componentes para maquinaria y vehículos'),
            ('5103', 'Combustibles y Lubricantes', 'primaria', 'transporte', 'Gasolina, diésel, aceites y grasas automotrices/industriales'),
            ('5104', 'Fletes y Envíos', 'primaria', 'transporte', 'Transporte de mercancía y envíos por paquetería externa'),
            ('5105', 'Mantenimiento y Reparaciones Externas', 'primaria', 'mantenimiento', 'Servicios de reparación y mantenimiento contratados a terceros'),
            ('5106', 'Servicios Básicos (Luz, Agua, Gas)', 'primaria', 'instalaciones', 'Servicios públicos directos de las instalaciones'),
            ('5107', 'Comunicaciones e Internet', 'primaria', 'servicios', 'Telefonía, conectividad a internet y servicios de datos'),
            ('5108', 'Honorarios y Asesorías Profesionales', 'primaria', 'servicios', 'Consultoría legal, contable o técnica externa'),
            ('5109', 'Papelería y Artículos de Oficina', 'primaria', 'administrativo', 'Consumibles, impresiones y artículos administrativos'),
            ('5110', 'Viáticos y Gastos de Viaje', 'primaria', 'administrativo', 'Hospedaje, alimentos de viaje y traslados de personal'),
            ('5111', 'Herramientas Menores y Seguridad', 'primaria', 'materiales', 'EPP, uniformes y herramientas no capitalizables'),
            # Secundarias
            ('9101', 'Reparto Interno Servicios TI / Sistemas', 'secundaria', 'distribucion_interna', 'Liquidación mensual de costos de infraestructura y soporte TI'),
            ('9102', 'Absorción Mano de Obra Taller / Producción', 'secundaria', 'personal', 'Tarifas horarias aplicadas a órdenes de trabajo u operaciones'),
            ('9103', 'Sub-reparto Mantenimiento General', 'secundaria', 'distribucion_interna', 'Prorrateo de gastos del taller de mantenimiento a centros operativos'),
            ('9104', 'Distribución Gastos Corporativos y Renta', 'secundaria', 'distribucion_interna', 'Prorrateo de renta y gastos administrativos corporativos'),
        ]

        creados = 0
        for codigo, nombre, tipo, cat, desc in catalogo_base:
            cls.objects.create(
                empresa=empresa,
                codigo=codigo,
                nombre=nombre,
                tipo=tipo,
                categoria=cat,
                descripcion=desc,
                activo=True
            )
            creados += 1
        return creados


# =========================================================================
# CICLOS DE DISTRIBUCIÓN Y PRORRATEO DE GASTOS (SAP ALLOCATION / ASSESSMENT)
# =========================================================================

class CicloDistribucion(models.Model):
    """
    Define una regla o ciclo recurrente para prorratear gastos acumulados de un
    Centro de Costo emisor (ej. Administración Central, TI, Mantenimiento General)
    hacia uno o más Centros de Costo receptores (ej. Sucursales, Obras, Proyectos).
    """
    METODO_CHOICES = [
        ('porcentaje_fijo', 'Porcentajes Fijos (%)'),
        ('monto_fijo', 'Monto Fijo Absoluto ($)'),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='ciclos_distribucion',
        verbose_name="Empresa"
    )
    codigo = models.CharField(max_length=30, verbose_name="Código del Ciclo")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Ciclo")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    centro_emisor = models.ForeignKey(
        CentroCosto,
        on_delete=models.CASCADE,
        related_name='ciclos_como_emisor',
        verbose_name="Centro Emisor (Origen)"
    )

    clase_costo_secundaria = models.ForeignKey(
        ClaseCosto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ciclos_distribucion',
        verbose_name="Clase de Costo Secundaria (Imputación)",
        help_text="Clase de costo tipo secundaria bajo la cual se registrará el reparto interno"
    )

    metodo = models.CharField(
        max_length=30,
        choices=METODO_CHOICES,
        default='porcentaje_fijo',
        verbose_name="Método de Distribución"
    )

    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Ciclo de Distribución"
        verbose_name_plural = "Ciclos de Distribución"
        ordering = ['codigo', 'nombre']
        unique_together = ('empresa', 'codigo')

    def __str__(self):
        return f"{self.codigo} - {self.nombre} (Emisor: {self.centro_emisor.codigo})"

    @property
    def total_porcentaje(self):
        """Suma de los porcentajes asignados a receptores."""
        return sum([s.porcentaje for s in self.segmentos.filter(activo=True)], Decimal('0.00'))


class SegmentoCicloDistribucion(models.Model):
    """
    Especifica la regla de reparto para cada Centro de Costo receptor dentro de un ciclo.
    """
    ciclo = models.ForeignKey(
        CicloDistribucion,
        on_delete=models.CASCADE,
        related_name='segmentos',
        verbose_name="Ciclo de Distribución"
    )
    centro_receptor = models.ForeignKey(
        CentroCosto,
        on_delete=models.CASCADE,
        related_name='segmentos_como_receptor',
        verbose_name="Centro Receptor (Destino)"
    )
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Porcentaje Asignado (%)",
        help_text="Participación porcentual en el prorrateo (ej. 25.00)"
    )
    monto_fijo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Fijo Mensual ($)",
        help_text="Monto nominal a transferir mensualmente si el método es monto fijo"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Segmento de Distribución"
        verbose_name_plural = "Segmentos de Distribución"
        unique_together = ('ciclo', 'centro_receptor')

    def __str__(self):
        return f"{self.ciclo.codigo} -> {self.centro_receptor.codigo} ({self.porcentaje}%)"


class EjecucionCicloDistribucion(models.Model):
    """
    Registro histórico de la ejecución de un ciclo en un periodo (año y mes) específico.
    Permite trazabilidad total y reversión controlada.
    """
    ESTADO_CHOICES = [
        ('aplicado', 'Aplicado'),
        ('revertido', 'Revertido'),
    ]

    ciclo = models.ForeignKey(
        CicloDistribucion,
        on_delete=models.CASCADE,
        related_name='ejecuciones',
        verbose_name="Ciclo Ejecutado"
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='ejecuciones_ciclos_distribucion',
        verbose_name="Empresa"
    )
    anio = models.PositiveIntegerField(verbose_name="Año del Periodo")
    mes = models.PositiveIntegerField(verbose_name="Mes del Periodo (1-12)")
    
    fecha_ejecucion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Ejecución")
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ejecuciones_ciclos_distribucion',
        verbose_name="Usuario que Ejecutó"
    )

    monto_base_emisor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Gastado en Emisor ($)"
    )
    monto_total_distribuido = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Total Prorrateado ($)"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='aplicado',
        verbose_name="Estado de la Ejecución"
    )
    notas = models.TextField(blank=True, null=True, verbose_name="Notas / Observaciones")

    # Auditoría de reversión
    comprobantes_egresos = models.ManyToManyField(
        'tesoreria.Egreso',
        blank=True,
        related_name='ejecuciones_distribucion',
        verbose_name="Comprobantes de Egreso Prorrateados"
    )
    fecha_reversion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Reversión")
    usuario_reversion = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversiones_ciclos_distribucion',
        verbose_name="Usuario que Revirtió"
    )
    motivo_reversion = models.TextField(blank=True, null=True, verbose_name="Motivo de Reversión")

    class Meta:
        verbose_name = "Ejecución de Ciclo de Distribución"
        verbose_name_plural = "Ejecuciones de Ciclos de Distribución"
        ordering = ['-fecha_ejecucion']

    def __str__(self):
        return f"{self.ciclo.codigo} - Periodo {self.mes:02d}/{self.anio} ({self.get_estado_display()})"


class DetalleEjecucionCiclo(models.Model):
    """
    Desglose por receptor del prorrateo aplicado en una ejecución.
    """
    ejecucion = models.ForeignKey(
        EjecucionCicloDistribucion,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name="Ejecución"
    )
    centro_receptor = models.ForeignKey(
        CentroCosto,
        on_delete=models.CASCADE,
        related_name='distribuciones_recibidas',
        verbose_name="Centro Receptor"
    )
    porcentaje_aplicado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Porcentaje Aplicado (%)"
    )
    monto_cargado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Monto Cargado al Receptor ($)"
    )

    class Meta:
        verbose_name = "Detalle de Ejecución de Ciclo"
        verbose_name_plural = "Detalles de Ejecución de Ciclos"
        ordering = ['id']

    def __str__(self):
        return f"{self.ejecucion.ciclo.codigo} -> {self.centro_receptor.codigo}: ${self.monto_cargado}"


class PeriodoContable(models.Model):
    """
    Control de Cierre de Periodos Contables / Mensuales.
    Impide que se sigan imputando o modificando egresos, órdenes de compra
    o prorrateos en meses que han sido dictaminados y cerrados por finanzas.
    """
    ESTADO_CHOICES = [
        ('abierto', 'Abierto'),
        ('cerrado', 'Cerrado'),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='periodos_contables',
        verbose_name="Empresa"
    )
    anio = models.PositiveIntegerField(verbose_name="Año del Periodo")
    mes = models.PositiveIntegerField(verbose_name="Mes del Periodo (1-12)")
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='abierto',
        verbose_name="Estado del Periodo"
    )

    # Auditoría de Cierre
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Cierre")
    usuario_cierre = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='periodos_cerrados',
        verbose_name="Usuario que Cerró"
    )
    notas_cierre = models.TextField(blank=True, null=True, verbose_name="Notas del Cierre")

    # Auditoría de Reapertura
    fecha_reapertura = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Reapertura")
    usuario_reapertura = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='periodos_reabiertos',
        verbose_name="Usuario que Reabrió"
    )
    motivo_reapertura = models.TextField(blank=True, null=True, verbose_name="Motivo de Reapertura")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Periodo Contable"
        verbose_name_plural = "Periodos Contables"
        unique_together = ('empresa', 'anio', 'mes')
        ordering = ['-anio', '-mes']

    def __str__(self):
        return f"{self.mes:02d}/{self.anio} ({self.get_estado_display()}) - {self.empresa.nombre}"

    @classmethod
    def esta_cerrado(cls, empresa, anio, mes):
        """Devuelve True si el periodo está cerrado para esa empresa."""
        if not empresa or not anio or not mes:
            return False
        return cls.objects.filter(
            empresa=empresa,
            anio=int(anio),
            mes=int(mes),
            estado='cerrado'
        ).exists()

    @classmethod
    def validar_fecha_no_cerrada(cls, empresa, fecha, raise_exception=False):
        """
        Valida que una fecha (date o datetime) no pertenezca a un periodo cerrado.
        Si está cerrado y raise_exception=True, lanza ValidationError.
        Devuelve (es_valido, mensaje_error).
        """
        if not empresa or not fecha:
            return True, None
        anio = fecha.year
        mes = fecha.month
        cerrado = cls.esta_cerrado(empresa, anio, mes)
        if cerrado:
            msg = f"El periodo {mes:02d}/{anio} se encuentra CERRADO para operaciones financieras y contables. No se permiten nuevos registros ni cancelaciones en este periodo."
            if raise_exception:
                from django.core.exceptions import ValidationError
                raise ValidationError(msg)
            return False, msg
        return True, None



