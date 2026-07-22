from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os

protected_storage = FileSystemStorage(location=str(settings.BASE_DIR / 'protected_media'))

def upload_to_beneficiario_doc(instance, filename):
    # Organizar por subdominio de empresa / tipo de documento
    subdominio = instance.empresa.subdominio
    return f'tenants/{subdominio}/beneficiarios/documentos/{filename}'

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
        ('01', '01 - Contrato de trabajo por tiempo indeterminado'),
        ('02', '02 - Contrato de trabajo por obra determinada'),
        ('03', '03 - Contrato de trabajo por tiempo determinado'),
        ('05', '05 - Contrato de trabajo sujeto a prueba'),
        ('06', '06 - Contrato de trabajo con capacitación inicial'),
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
    cp = models.CharField(max_length=255, blank=True, null=True, verbose_name="Código Postal")
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
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES, default='01', verbose_name="Tipo de Contrato")
    jornada = models.CharField(max_length=20, choices=JORNADA_CHOICES, default='diurna', verbose_name="Jornada")
    tipo_regimen_sat = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tipo Régimen (SAT)")
    jornada_sat = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tipo Jornada (SAT)")
    antiguedad_sat = models.CharField(max_length=50, blank=True, null=True, verbose_name="Antigüedad (Texto/SAT)")
    periodicidad_pago_sat = models.CharField(max_length=50, blank=True, null=True, verbose_name="Periodicidad Pago (SAT)")
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
        ('cerrado', 'Cerrado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")

    # 1. Colaboradores, Organización y Contratante
    empleados = models.ManyToManyField(Empleado, related_name='contratos_asignados', verbose_name="Colaboradores")
    contratista = models.ForeignKey('Contratista', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contratista")
    beneficiario = models.ForeignKey('Beneficiario', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Beneficiario")

    # 2. Datos Generales de Contrato
    folio = models.CharField(max_length=100, blank=True, null=True, verbose_name="Folio de Contrato")
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CHOICES, default='01', verbose_name="Tipo de Contrato")
    objeto_contrato = models.TextField(blank=True, null=True, verbose_name="Objeto del Contrato")
    monto_contrato = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Monto del Contrato")

    # Vigencia
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fecha de Término")
    vigencia_contrato = models.DateField(null=True, blank=True, verbose_name="Vigencia de Contrato")

    num_estimado_trabajadores = models.IntegerField(default=0, verbose_name="Número Estimado de Trabajadores")

    version = models.CharField(max_length=20, default='1', verbose_name="Versión")
    estado_vigencia = models.CharField(max_length=20, choices=[('vigente', 'Vigente'), ('vencido', 'Vencido'), ('cerrado', 'Cerrado')], default='vigente', verbose_name="Estado de Vigencia")
    estado_periodicidad = models.CharField(max_length=20, choices=[('vigente', 'Vigente'), ('cerrado', 'Cerrado')], default='vigente', verbose_name="Estado de Periodicidad")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='vigente', verbose_name="Estado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas/Observaciones")

    fecha_registro = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-calcular 'estado_vigencia' y 'estado_periodicidad' de forma independiente en base a sus respectivas fechas
        import datetime
        today = datetime.date.today()
        
        # 1. Vigencia global (Vigencia de contrato)
        if self.vigencia_contrato and self.vigencia_contrato < today:
            self.estado_vigencia = 'vencido'
        else:
            self.estado_vigencia = 'vigente'

        # 2. Periodicidad individual (Fecha de término)
        if self.fecha_fin and self.fecha_fin < today:
            self.estado_periodicidad = 'cerrado'
        else:
            self.estado_periodicidad = 'vigente'

        # Sincronizar el campo 'estado' legado para mantener compatibilidad (Precedencia: vencido > cerrado > vigente)
        if self.estado_vigencia == 'vencido':
            self.estado = 'vencido'
        elif self.estado_periodicidad == 'cerrado' or self.estado_vigencia == 'cerrado':
            self.estado = 'cerrado'
        else:
            self.estado = 'vigente'

        super().save(*args, **kwargs)

        # 3. Auto-secuenciar Versión cronológicamente y cerrar versiones anteriores automáticamente
        if self.folio:
            contratos_folio = Contrato.objects.filter(
                empresa=self.empresa,
                contratista=self.contratista,
                folio__iexact=self.folio.strip()
            ).order_by('fecha_inicio')
            
            total_contratos = len(contratos_folio)
            for idx, con in enumerate(contratos_folio, start=1):
                version_str = str(idx)
                is_latest = (idx == total_contratos)
                
                # Calcular vigencia para esta versión (Regla 3: Vencido si ya pasó la fecha de vigencia, sin importar la versión)
                if con.vigencia_contrato and con.vigencia_contrato < today:
                    est_vig = 'vencido'
                elif not is_latest:
                    est_vig = 'cerrado'
                else:
                    est_vig = 'vigente'
                    
                # Calcular periodicidad: si no es la última versión, se cierra automáticamente
                if not is_latest:
                    est_per = 'cerrado'
                else:
                    if con.fecha_fin and con.fecha_fin < today:
                        est_per = 'cerrado'
                    else:
                        est_per = 'vigente'
                        
                # Sincronizar el campo legacy 'estado' (Vencido tiene máxima precedencia)
                if est_vig == 'vencido':
                    est_legacy = 'vencido'
                elif est_per == 'cerrado' or est_vig == 'cerrado':
                    est_legacy = 'cerrado'
                else:
                    est_legacy = 'vigente'
                    
                Contrato.objects.filter(id=con.id).update(
                    version=version_str,
                    estado_vigencia=est_vig,
                    estado_periodicidad=est_per,
                    estado=est_legacy
                )
                
                if con.id == self.id:
                    self.version = version_str
                    self.estado_vigencia = est_vig
                    self.estado_periodicidad = est_per
                    self.estado = est_legacy

    def __str__(self):
        return f"{self.folio or 'S/F'} - {self.beneficiario or 'Sin beneficiario'}"

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"

class Contratista(models.Model):
    REGIMEN_FISCAL_CHOICES = [
        ('601', '601 - REGIMEN GENERAL DE LEY PERSONAS MORALES'),
        ('602', '602 - RÉGIMEN SIMPLIFICADO DE LEY PERSONAS MORALES'),
        ('603', '603 - PERSONAS MORALES CON FINES NO LUCRATIVOS'),
        ('604', '604 - RÉGIMEN DE PEQUEÑOS CONTRIBUYENTES'),
        ('605', '605 - RÉGIMEN DE SUELDOS Y SALARIOS E INGRESOS ASIMILADOS A SALARIOS'),
        ('606', '606 - RÉGIMEN DE ARRENDAMIENTO'),
        ('607', '607 - RÉGIMEN DE ENAJENACIÓN O ADQUISICIÓN DE BIENES'),
        ('608', '608 - RÉGIMEN DE LOS DEMÁS INGRESOS'),
        ('609', '609 - RÉGIMEN DE CONSOLIDACIÓN'),
        ('610', '610 - RÉGIMEN RESIDENTES EN EL EXTRANJERO SIN ESTABLECIMIENTO PERMANENTE EN MÉXICO'),
        ('611', '611 - RÉGIMEN DE INGRESOS POR DIVIDENDOS (SOCIOS Y ACCIONISTAS)'),
        ('612', '612 - RÉGIMEN DE LAS PERSONAS FÍSICAS CON ACTIVIDADES EMPRESARIALES Y PROFESIONALES'),
        ('613', '613 - RÉGIMEN INTERMEDIO DE LAS PERSONAS FÍSICAS CON ACTIVIDADES EMPRESARIALES'),
        ('614', '614 - RÉGIMEN DE LOS INGRESOS POR INTERESES'),
        ('615', '615 - RÉGIMEN DE LOS INGRESOS POR OBTENCIÓN DE PREMIOS'),
        ('616', '616 - SIN OBLIGACIONES FISCALES'),
        ('617', '617 - PEMEX'),
        ('618', '618 - RÉGIMEN SIMPLIFICADO DE LEY PERSONAS FÍSICAS'),
        ('619', '619 - INGRESOS POR LA OBTENCIÓN DE PRÉSTAMOS'),
        ('620', '620 - SOCIEDADES COOPERATIVAS DE PRODUCCIÓN QUE OPTAN POR DIFERIR SUS INGRESOS.'),
        ('621', '621 - RÉGIMEN DE INCORPORACIÓN FISCAL'),
        ('622', '622 - RÉGIMEN DE ACTIVIDADES AGRÍCOLAS, GANADERAS, SILVÍCOLAS Y PESQUERAS PM'),
        ('623', '623 - RÉGIMEN DE OPCIONAL PARA GRUPOS DE SOCIEDADES'),
        ('624', '624 - RÉGIMEN DE LOS COORDINADOS'),
        ('625', '625 - RÉGIMEN DE LAS ACTIVIDADES EMPRESARIALES CON INGRESOS A TRAVÉS DE PLATAFORMAS TECNOLÓGICAS.'),
        ('626', '626 - RÉGIMEN SIMPLIFICADO DE CONFIANZA'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # Datos Identificación
    clave = models.CharField(max_length=50, blank=True, null=True, verbose_name="Clave")
    rfc = models.CharField(max_length=13, verbose_name="RFC")
    nombre_razon_social = models.CharField(max_length=200, verbose_name="Nombre / Razón Social")
    regimen = models.CharField(max_length=3, choices=REGIMEN_FISCAL_CHOICES, blank=True, null=True, verbose_name="Régimen Fiscal")
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
    objeto_contrato = models.TextField(blank=True, null=True, verbose_name="Objeto del Contrato")
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
    
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='beneficiario', verbose_name="Usuario de Acceso")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rfc} - {self.nombre_razon_social}"

    class Meta:
        verbose_name = "Beneficiario"
        verbose_name_plural = "Beneficiarios"

class DocumentacionBeneficiario(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    beneficiario = models.ForeignKey(Beneficiario, on_delete=models.CASCADE, related_name='documentos', verbose_name="Beneficiario")
    
    NOMBRE_DOC_CHOICES = [
        ('REPSE', 'Registro REPSE'),
        ('SAT', 'Opinión SAT'),
        ('IMSS', 'Opinión IMSS'),
        ('INFONAVIT', 'Opinión INFONAVIT'),
        ('SUA_CEDULA', 'Cédula SUA'),
        ('SUA_PAGO', 'Pago SUA'),
        ('LISTA_TRABAJADORES', 'Lista de Trabajadores'),
        ('OTROS', 'Otros'),
    ]
    
    STATUS_DOC_CHOICES = [
        ('revision', 'En Revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    
    nombre_documento = models.CharField(max_length=50, choices=NOMBRE_DOC_CHOICES, verbose_name="Nombre del Documento")
    archivo = models.FileField(storage=protected_storage, upload_to=upload_to_beneficiario_doc, verbose_name="Archivo")
    mes = models.PositiveIntegerField(verbose_name="Mes (1-12)")
    anio = models.PositiveIntegerField(verbose_name="Año")
    fecha_subida = models.DateTimeField(auto_now_add=True)
    estatus = models.CharField(max_length=20, choices=STATUS_DOC_CHOICES, default='revision', verbose_name="Estatus")

    def __str__(self):
        return f"{self.beneficiario.nombre_razon_social} - {self.nombre_documento} ({self.mes}/{self.anio})"

    class Meta:
        verbose_name = "Documentación de Beneficiario"
        verbose_name_plural = "Documentación de Beneficiarios"
        unique_together = ('beneficiario', 'nombre_documento', 'mes', 'anio')

# SECCIÓN DE SEÑALES PARA LIMPIEZA DE DISCO Y GESTIÓN POR EMPRESA
from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=DocumentacionBeneficiario)
def eliminar_archivo_fisico_beneficiario(sender, instance, **kwargs):
    """Elimina el archivo del servidor cuando se borra el registro de la BD"""
    if instance.archivo:
        if os.path.isfile(instance.archivo.path):
            os.remove(instance.archivo.path)

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


class Nomina(models.Model):
    TIPO_NOMINA_CHOICES = [
        ('O', 'O - Nómina ordinaria'),
        ('E', 'E - Nómina extraordinaria'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empleado", related_name="nominas")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")

    # 1. Datos de timbrado
    periodo = models.CharField(max_length=100, verbose_name="Periodo")
    uso_cfdi = models.CharField(max_length=255, default="CN01", verbose_name="Uso de CFDI")
    uuid = models.CharField(max_length=36, blank=True, null=True, verbose_name="UUID")
    tipo_nomina = models.CharField(max_length=1, choices=TIPO_NOMINA_CHOICES, default='O', verbose_name="Tipo de Nómina")
    serie = models.CharField(max_length=20, blank=True, null=True, verbose_name="Serie")
    folio = models.CharField(max_length=20, blank=True, null=True, verbose_name="Folio")
    fecha_emision = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Emisión")
    fecha_certificacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Certificación")
    fecha_pago = models.DateField(null=True, blank=True, verbose_name="Fecha Pago")
    fecha_inicial_pago = models.DateField(null=True, blank=True, verbose_name="Fecha Inicial Pago")
    fecha_final_pago = models.DateField(null=True, blank=True, verbose_name="Fecha Final Pago")
    dias_pagados = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Días Pagados")

    # 2. Datos del trabajador
    rfc = models.CharField(max_length=13, verbose_name="RFC")
    curp = models.CharField(max_length=18, verbose_name="CURP")
    nss = models.CharField(max_length=11, verbose_name="NSS")
    nombre = models.CharField(max_length=255, verbose_name="Nombre")
    rfc_contratista = models.CharField(max_length=13, blank=True, null=True, verbose_name="RFC (Contratista)")
    sdi = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="SDI")
    sbc = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="SBC")

    # 3. Percepciones
    # Exento
    vacaciones_exento = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Vacaciones (Exento)")
    vacaciones_dignas_exento = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Vacaciones Dignas (Exento)")
    aguinaldo_exento = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Aguinaldo (Exento)")
    
    # Gravado
    sueldo_gravado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Sueldo (Gravado)")
    vacaciones_gravado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Vacaciones (Gravado)")
    vacaciones_dignas_gravado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Vacaciones Dignas (Gravado)")
    aguinaldo_gravado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Aguinaldo (Gravado)")
    percepciones_detalladas = models.JSONField(default=dict, blank=True, verbose_name="Detalle de Percepciones SAT")

    @property
    def total_percepciones(self):
        from decimal import Decimal
        total = Decimal('0.00')
        if self.percepciones_detalladas:
            for code, values in self.percepciones_detalladas.items():
                try:
                    total += Decimal(str(values.get('gravado', 0) or 0))
                except:
                    pass
                try:
                    total += Decimal(str(values.get('exento', 0) or 0))
                except:
                    pass
        else:
            # Fallback to legacy fields
            total += (self.vacaciones_exento or 0) + (self.vacaciones_dignas_exento or 0) + (self.aguinaldo_exento or 0) + \
                     (self.sueldo_gravado or 0) + (self.vacaciones_gravado or 0) + (self.vacaciones_dignas_gravado or 0) + \
                     (self.aguinaldo_gravado or 0)
        return total

    def __str__(self):
        return f"Nómina {self.folio or self.id} - {self.nombre} ({self.periodo})"

    class Meta:
        verbose_name = "Nómina"
        verbose_name_plural = "Nóminas"
        ordering = ['-fecha_pago', 'nombre']


class FielContratista(models.Model):
    """Almacena los archivos de la FIEL de un contratista de forma cifrada."""
    contratista = models.OneToOneField(Contratista, on_delete=models.CASCADE, related_name="fiel")
    
    # Contenido cifrado (Base64)
    certificado_cifrado = models.TextField(verbose_name="Certificado (.cer) Cifrado")
    llave_privada_cifrada = models.TextField(verbose_name="Llave Privada (.key) Cifrada")
    
    # RFC que ampara esta FIEL (para validación)
    rfc_fiel = models.CharField(max_length=13, verbose_name="RFC de la FIEL")
    
    # Llave de datos cifrada con Master Key (Envelope Encryption)
    data_key_cifrada = models.TextField(verbose_name="Data Key Cifrada")
    
    fecha_alta = models.DateTimeField(auto_now_add=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FIEL - {self.rfc_fiel} ({self.contratista.nombre_razon_social})"

    class Meta:
        verbose_name = "FIEL Contratista"
        verbose_name_plural = "FIELs de Contratistas"


class SolicitudDescargaSAT(models.Model):
    """Rastreo de solicitudes de descarga masiva ante el SAT."""
    ESTADO_CHOICES = [
        ('solicitada', 'Solicitada'),
        ('en_proceso', 'En Proceso'),
        ('terminada', 'Terminada'),
        ('error', 'Error'),
        ('procesada', 'Procesada / Integrada'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    contratista = models.ForeignKey(Contratista, on_delete=models.CASCADE, null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    id_solicitud = models.CharField(max_length=100, verbose_name="ID de Solicitud SAT")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo_comprobante = models.CharField(max_length=20, default="Nomina")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='solicitada')
    mensaje_error = models.TextField(blank=True, null=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Solicitud {self.id_solicitud} - {self.estado}"

    class Meta:
        verbose_name = "Solicitud SAT"
        verbose_name_plural = "Solicitudes"
        ordering = ['-fecha_creacion']


