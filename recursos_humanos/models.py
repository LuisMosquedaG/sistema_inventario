from django.db import models
from panel.models import Empresa

class Empleado(models.Model):
    # Opciones
    GENERO_CHOICES = [
        ('H', 'Hombre'),
        ('M', 'Mujer'),
        ('NB', 'No binario'),
    ]
    ESTADO_CIVIL_CHOICES = [
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('union_libre', 'Unión Libre'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
    ]
    ESTADO_EMPLEADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('suspendido', 'Suspendido'),
        ('baja_temporal', 'Baja Temporal'),
        ('baja_definitiva', 'Baja Definitiva'),
    ]
    TIPO_CONTRATO_CHOICES = [
        ('indefinido', 'Indefinido'),
        ('temporal_obra', 'Temporal por obra'),
        ('temporal_tiempo', 'Temporal por tiempo determinado'),
    ]
    JORNADA_CHOICES = [
        ('diurna', 'Diurna'),
        ('nocturna', 'Nocturna'),
        ('mixta', 'Mixta'),
        ('parcial', 'Tiempo Parcial'),
    ]
    RIESGO_TRABAJO_CHOICES = [
        ('I', 'Clase I'),
        ('II', 'Clase II'),
        ('III', 'Clase III'),
        ('IV', 'Clase IV'),
        ('V', 'Clase V'),
    ]
    TIPO_TRABAJADOR_CHOICES = [
        ('base', 'Base'),
        ('eventual', 'Eventual'),
        ('confianza', 'Confianza'),
        ('sindicalizado', 'Sindicalizado'),
    ]
    FORMA_PAGO_CHOICES = [
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
    ]
    TIPO_SALARIO_CHOICES = [
        ('fijo', 'Fijo'),
        ('variable', 'Variable'),
        ('mixto', 'Mixto'),
    ]
    TIPO_CUENTA_CHOICES = [
        ('ahorro', 'Ahorro'),
        ('cheques', 'Cheques'),
        ('tarjeta', 'Tarjeta'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # 1. IDENTIFICACIÓN Y DATOS PERSONALES
    num_empleado = models.CharField(max_length=20, default="", verbose_name="Número de Empleado")
    curp = models.CharField(max_length=18, default="", verbose_name="CURP")
    rfc = models.CharField(max_length=13, default="", verbose_name="RFC")
    nss = models.CharField(max_length=11, default="", verbose_name="NSS")
    id_oficial = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID Oficial (INE/Pasaporte)")
    
    nombre = models.CharField(max_length=100, default="", verbose_name="Nombre(s)")
    apellido_paterno = models.CharField(max_length=100, default="", verbose_name="Apellido Paterno")
    apellido_materno = models.CharField(max_length=100, default="", verbose_name="Apellido Materno")
    
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    genero = models.CharField(max_length=5, choices=GENERO_CHOICES, default='H', verbose_name="Género")
    nacionalidad = models.CharField(max_length=100, default="Mexicana", verbose_name="Nacionalidad")
    estado_civil = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES, default='soltero', verbose_name="Estado Civil")
    
    correo_personal = models.EmailField(default="", verbose_name="Correo Personal")
    telefono_movil = models.CharField(max_length=20, default="", verbose_name="Teléfono Móvil")
    telefono_fijo = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono Fijo")
    
    # Domicilio
    calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle")
    num_ext = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número Exterior")
    num_int = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número Interior")
    colonia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Colonia")
    cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    ciudad = models.CharField(max_length=150, blank=True, null=True, verbose_name="Ciudad")
    estado_dir = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado")

    # 2. DATOS DE CONTROL Y ESTADO
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    estado = models.CharField(max_length=20, choices=ESTADO_EMPLEADO_CHOICES, default='activo', verbose_name="Estado del Empleado")
    fecha_baja = models.DateField(null=True, blank=True, verbose_name="Fecha de Baja")
    motivo_baja = models.CharField(max_length=200, blank=True, null=True, verbose_name="Motivo de Baja")

    # 3. PUESTO Y CONTRATACIÓN
    fecha_ingreso = models.DateField(null=True, blank=True, verbose_name="Fecha de Ingreso")
    fecha_antiguedad = models.DateField(null=True, blank=True, verbose_name="Fecha de Antigüedad")
    fecha_expiracion = models.DateField(null=True, blank=True, verbose_name="Fecha de Expiración Contrato")
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES, default='indefinido', verbose_name="Tipo de Contrato")
    jornada = models.CharField(max_length=20, choices=JORNADA_CHOICES, default='diurna', verbose_name="Jornada")
    puesto = models.CharField(max_length=100, default="", verbose_name="Puesto")
    departamento = models.CharField(max_length=100, default="", verbose_name="Departamento/Área")
    supervisor = models.CharField(max_length=150, blank=True, null=True, verbose_name="Supervisor Inmediato")
    riesgo_trabajo = models.CharField(max_length=5, choices=RIESGO_TRABAJO_CHOICES, default='I', verbose_name="Riesgo de Trabajo")
    tipo_trabajador = models.CharField(max_length=20, choices=TIPO_TRABAJADOR_CHOICES, default='base', verbose_name="Tipo de Trabajador")

    # 4. DATOS SALARIALES
    sbc = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Salario Base de Cotización")
    sdi = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Salario Diario Integrado")
    salario_diario_ordinario = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Salario Diario Ordinario")
    unidad_monetaria = models.CharField(max_length=3, default='MXN', verbose_name="Moneda")
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='quincenal', verbose_name="Forma de Pago")
    clave_percepcion_sat = models.CharField(max_length=10, default='001', verbose_name="Clave Percepción SAT")
    tipo_salario = models.CharField(max_length=20, choices=TIPO_SALARIO_CHOICES, default='fijo', verbose_name="Tipo de Salario")

    # 5. BENEFICIOS
    registro_patronal = models.CharField(max_length=50, blank=True, null=True, verbose_name="Registro Patronal IMSS")
    num_infonavit = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número Infonavit")
    num_fonacot = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número FONACOT")
    fondo_ahorro = models.BooleanField(default=False, verbose_name="Fondo de Ahorro")
    porcentaje_fondo = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Porcentaje Fondo")
    caja_ahorro = models.BooleanField(default=False, verbose_name="Caja de Ahorro")

    # 6. DATOS BANCARIOS
    banco_nombre = models.CharField(max_length=100, blank=True, null=True, verbose_name="Banco")
    clabe = models.CharField(max_length=18, blank=True, null=True, verbose_name="CLABE")
    num_cuenta = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número de Cuenta")
    tipo_cuenta = models.CharField(max_length=20, choices=TIPO_CUENTA_CHOICES, default='tarjeta', verbose_name="Tipo de Cuenta")
    tarjeta_nomina = models.BooleanField(default=False, verbose_name="Tarjeta de Nómina")
    num_tarjeta = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número de Tarjeta")

    def __str__(self):
        return f"{self.num_empleado} - {self.nombre} {self.apellido_paterno}"

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"

