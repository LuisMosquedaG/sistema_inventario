from django.db import models

class Empresa(models.Model):
    """
    Modelo para representar a cada cliente (Tenant) en el sistema Multi-Tenant.
    """
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Empresa")
    subdominio = models.SlugField(max_length=100, unique=True, verbose_name="Subdominio (URL)", help_text="Ej: mizona.crossoversuite.com")
    usuario_admin = models.CharField(max_length=50, verbose_name="Usuario Admin de la Empresa")
    correo_contacto = models.EmailField(verbose_name="Correo de contacto")
    
    # Nuevos campos de contacto y logo
    nombre_contacto = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre de contacto")
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de contacto")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True, verbose_name="Logo de la empresa")

    # Campos de dirección
    calle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Calle")
    numero = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número")
    colonia = models.CharField(max_length=150, blank=True, null=True, verbose_name="Colonia")
    estado = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado")
    cp = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")

    fecha_alta = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de alta")
    activa = models.BooleanField(default=True, verbose_name="Empresa Activa")

    # Módulos habilitados
    modulo_ventas = models.BooleanField(default=True, verbose_name="Módulo Ventas")
    modulo_compras = models.BooleanField(default=True, verbose_name="Módulo Compras")
    modulo_tesoreria = models.BooleanField(default=True, verbose_name="Módulo Tesorería")
    modulo_produccion = models.BooleanField(default=True, verbose_name="Módulo Producción")
    modulo_inventarios = models.BooleanField(default=True, verbose_name="Módulo Inventarios")
    modulo_recursos_humanos = models.BooleanField(default=True, verbose_name="Módulo Recursos Humanos")

    # Licenciamiento
    fecha_inicio_licencia = models.DateField(null=True, blank=True, verbose_name="Inicio de Licencia")
    fecha_vencimiento_licencia = models.DateField(null=True, blank=True, verbose_name="Vencimiento de Licencia")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Empresa (Tenant)"
        verbose_name_plural = "Empresas (Tenants)"