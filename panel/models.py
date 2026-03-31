from django.db import models

class Empresa(models.Model):
    """
    Modelo para representar a cada cliente (Tenant) en el sistema Multi-Tenant.
    """
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Empresa")
    subdominio = models.SlugField(max_length=100, unique=True, verbose_name="Subdominio (URL)", help_text="Ej: mizona.crossoversuite.com")
    usuario_admin = models.CharField(max_length=50, verbose_name="Usuario Admin de la Empresa")
    correo_contacto = models.EmailField(verbose_name="Correo de contacto")
    fecha_alta = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de alta")
    activa = models.BooleanField(default=True, verbose_name="Empresa Activa")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Empresa (Tenant)"
        verbose_name_plural = "Empresas (Tenants)"