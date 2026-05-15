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
    contratista = models.ForeignKey('Contratista', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contratista")
    beneficiario = models.ForeignKey('Beneficiario', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Beneficiario")
    fecha_ingreso = models.DateField(null=True, blank=True, verbose_name="Fecha de Ingreso")
    fecha_antiguedad = models.DateField(null=True, blank=True, verbose_name="Fecha de Antigüedad")
    fecha_expiracion = models.DateField(null=True, blank=True, verbose_name="Fecha de Expiración Contrato")
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES, default='indefinido', verbose_name="Tipo de Contrato")
    jornada = models.CharField(max_length=20, choices=JORNADA_CHOICES, default='diurna', verbose_name="Jornada")
    puesto = models.CharField(max_length=100, default="", verbose_name="Puesto")
    departamento = models.CharField(max_length=100, default="", verbose_name="Departamento/Área")
    supervisor = models.CharField(max_length=150, blank=True, null=True, verbose_name="Supervisor Inmediato")
    clave_ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Clave de Ubicación")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas")
    riesgo_trabajo = models.CharField(max_length=5, choices=RIESGO_TRABAJO_CHOICES, default='I', verbose_name="Riesgo de Trabajo")
    tipo_trabajador = models.CharField(max_length=20, choices=TIPO_TRABAJADOR_CHOICES, default='base', verbose_name="Tipo de Trabajador")

    # 4. DATOS SALARIALES
    sbc = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Salario Base de Cotización")
    sdi = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Salario Diario Integrado")
    salario_diario_ordinario = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Salario Diario Ordinario")
    unidad_monetaria = models.CharField(max_length=3, default='MXN', verbose_name="Moneda")
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='quincenal', verbose_name="Forma de Pago")
    clave_percepcion_sat = models.CharField(max_length=100, default='001', verbose_name="Clave Percepción SAT")
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

class Contrato(models.Model):
    TIPO_CHOICES = Empleado.TIPO_CONTRATO_CHOICES
    ESTADO_CHOICES = [
        ('vigente', 'Vigente'),
        ('vencido', 'Vencido'),
        ('suspendido', 'Suspendido'),
        ('cancelado', 'Cancelado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")

    # 1. Colaboradores, Organización y Contratante
    empleados = models.ManyToManyField(Empleado, related_name='contratos_asignados', verbose_name="Colaboradores")
    contratista = models.ForeignKey('Contratista', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contratista")
    beneficiario = models.ForeignKey('Beneficiario', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Beneficiario")

    # 2. Datos Generales de Contrato
    folio = models.CharField(max_length=100, blank=True, null=True, verbose_name="Folio de Contrato")
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CHOICES, default='indefinido', verbose_name="Tipo de Contrato")
    objeto_contrato = models.TextField(blank=True, null=True, verbose_name="Objeto del Contrato")
    monto_contrato = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Monto del Contrato")

    # Vigencia
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fecha de Término")
    vigencia_contrato = models.DateField(null=True, blank=True, verbose_name="Vigencia de Contrato")

    num_estimado_trabajadores = models.IntegerField(default=0, verbose_name="Número Estimado de Trabajadores")

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='vigente', verbose_name="Estado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas/Observaciones")

    fecha_registro = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.folio or 'S/F'} - {self.beneficiario or 'Sin beneficiario'}"

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"

class Contratista(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # Datos Identificación
    clave = models.CharField(max_length=50, blank=True, null=True, verbose_name="Clave")
    rfc = models.CharField(max_length=13, verbose_name="RFC")
    nombre_razon_social = models.CharField(max_length=200, verbose_name="Nombre / Razón Social")
    correo = models.EmailField(verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    registro_patronal = models.CharField(max_length=50, blank=True, null=True, verbose_name="Registro Patronal")
    
    # Dirección
    calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle")
    num_ext = models.CharField(max_length=50, blank=True, null=True, verbose_name="Núm. Ext.")
    num_int = models.CharField(max_length=50, blank=True, null=True, verbose_name="Núm. Int.")
    entre_calle = models.CharField(max_length=150, blank=True, null=True, verbose_name="Entre calle")
    y_calle = models.CharField(max_length=150, blank=True, null=True, verbose_name="y calle")
    colonia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Colonia")
    cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    municipio_alcaldia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Municipio / Alcaldía")
    entidad_federativa = models.CharField(max_length=100, blank=True, null=True, verbose_name="Entidad Federativa")
    
    # Representación y Legal
    representante_legal = models.CharField(max_length=200, blank=True, null=True, verbose_name="Representante Legal")
    administrador_unico = models.CharField(max_length=200, blank=True, null=True, verbose_name="Administrador Único")
    
    # Información Notarial
    num_escritura = models.CharField(max_length=100, blank=True, null=True, verbose_name="Núm. de Escritura")
    nombre_notario_publico = models.CharField(max_length=200, blank=True, null=True, verbose_name="Nombre Notario Público")
    num_notario_publico = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número de Notario Público")
    fecha_escritura_publica = models.DateField(null=True, blank=True, verbose_name="Fecha de Escritura Pública")
    folio_mercantil = models.CharField(max_length=100, blank=True, null=True, verbose_name="Folio Mercantil")
    
    # Otros Registros
    numero_stps = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número STPS")
    
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rfc} - {self.nombre_razon_social}"

    class Meta:
        verbose_name = "Contratista"
        verbose_name_plural = "Contratistas"

class Beneficiario(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # Datos Identificación
    clave = models.CharField(max_length=50, blank=True, null=True, verbose_name="Clave")
    rfc = models.CharField(max_length=13, verbose_name="RFC")
    nombre_razon_social = models.CharField(max_length=200, verbose_name="Nombre / Razón Social")
    registro_patronal = models.CharField(max_length=50, blank=True, null=True, verbose_name="Registro Patronal")
    
    # Dirección
    calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle")
    num_ext = models.CharField(max_length=50, blank=True, null=True, verbose_name="Núm. Ext.")
    num_int = models.CharField(max_length=50, blank=True, null=True, verbose_name="Núm. Int.")
    entre_calle = models.CharField(max_length=150, blank=True, null=True, verbose_name="Entre calle")
    y_calle = models.CharField(max_length=150, blank=True, null=True, verbose_name="y calle")
    colonia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Colonia")
    cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    municipio_alcaldia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Municipio o Alcaldía")
    entidad_federativa = models.CharField(max_length=100, blank=True, null=True, verbose_name="Entidad Federativa")
    
    # Contacto
    correo = models.EmailField(verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rfc} - {self.nombre_razon_social}"

    class Meta:
        verbose_name = "Beneficiario"
        verbose_name_plural = "Beneficiarios"

class ImportacionSUA(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # 1.1 Sección Empresa
    registro_patronal = models.CharField(max_length=100, blank=True, null=True)
    rfc_empresa = models.CharField(max_length=50, blank=True, null=True)
    nombre_razon_social = models.TextField(blank=True, null=True)
    actividad = models.TextField(blank=True, null=True)
    domicilio = models.TextField(blank=True, null=True)
    cp = models.CharField(max_length=50, blank=True, null=True)
    entidad = models.TextField(blank=True, null=True)

    # 1.2 Sección Seguro Social
    area_geografica = models.TextField(blank=True, null=True)
    delegacion_imss = models.TextField(blank=True, null=True)
    subdelegacion_imss = models.TextField(blank=True, null=True)
    municipio_alcaldia = models.TextField(blank=True, null=True)
    prima_rt = models.TextField(blank=True, null=True, verbose_name="Aportación Patronal / Prima RT")

    periodo = models.CharField(max_length=150, verbose_name="Periodo del Reporte")
    tipo = models.CharField(max_length=20, choices=[('mensual', 'Mensual'), ('bimestral', 'Bimestral')], default='mensual')
    fecha_importacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Importación {self.periodo} - {self.nombre_razon_social}"

    @property
    def total_trabajadores_unicos(self):
        return self.trabajadores.values('nss').distinct().count()

    class Meta:
        verbose_name = "Importación SUA"
        verbose_name_plural = "Importaciones SUA"

class TrabajadorSUA(models.Model):
    importacion = models.ForeignKey(ImportacionSUA, on_delete=models.CASCADE, related_name='trabajadores')
    
    # Línea 1
    nss = models.CharField(max_length=20)
    nombre = models.CharField(max_length=255)
    rfc_curp = models.CharField(max_length=50, blank=True, null=True)
    clave_ubicacion = models.CharField(max_length=50, blank=True, null=True)
    
    # Línea 2 (General / RCV)
    clave_mov = models.CharField(max_length=50, blank=True, null=True)
    fecha_mov = models.CharField(max_length=20, blank=True, null=True)
    dias = models.IntegerField(default=0)
    sdi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Detalle Cuotas
    licencias = models.IntegerField(default=0)
    incapacidades = models.IntegerField(default=0)
    ausentismos = models.IntegerField(default=0)
    
    # RCV (Para Bimestral)
    retiro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Patronal / Cesantía Pat.")
    obrera = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Obrera / Cesantía Obr.")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Subtotal / Suma RCV")
    
    # IMSS Mensual (Nuevos campos)
    cuota_fija = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excedente_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excedente_obrera = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    prestaciones_dinero_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    prestaciones_dinero_obrera = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos_medicos_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos_medicos_obrera = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    riesgo_trabajo_cuota = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invalidez_vida_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invalidez_vida_obrera = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    guarderias_ps = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Reutilizamos patronal, obrera y subtotal para los totales de la línea mensual si es necesario, 
    # o creamos campos específicos para evitar confusión con RCV.
    imss_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    imss_obrera = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    imss_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Infonavit (Bimestral)
    aportacion_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tipo_valor_infonavit = models.CharField(max_length=20, blank=True, null=True, verbose_name="% o $ o FD")
    amortizacion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    suma_infonavit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cred_vivienda = models.CharField(max_length=50, blank=True, null=True)
    tipo_mov_credito = models.CharField(max_length=50, blank=True, null=True)
    fecha_mov_credito = models.CharField(max_length=20, blank=True, null=True)
    
    # Totales
    total_general = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Línea 3 (Opcional)
    baja_fecha = models.CharField(max_length=20, blank=True, null=True)
    baja_clave = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.nss} - {self.nombre}"

    class Meta:
        verbose_name = "Trabajador SUA"
        verbose_name_plural = "Trabajadores SUA"


