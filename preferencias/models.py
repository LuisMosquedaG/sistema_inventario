from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa


class Moneda(models.Model):
    nombre = models.CharField(max_length=50, verbose_name="Nombre de la Moneda")
    siglas = models.CharField(max_length=5, verbose_name="Siglas (ej. MXN)")
    simbolo = models.CharField(max_length=5, verbose_name="Símbolo (ej. $)")
    factor = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, verbose_name="Factor de Conversión")
    
    # Responsable y Empresa
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsable")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.siglas})"

    class Meta:
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ['nombre']


class Rol(models.Model):
    nombre = models.CharField(max_length=80, verbose_name="Nombre del Rol")
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre']
        unique_together = ('empresa', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.empresa})"


class PermisoRolModulo(models.Model):
    MODULO_CHOICES = [
        ('ventas', 'Ventas'),
        ('produccion', 'Producción'),
    ]

    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='permisos_modulo')
    modulo = models.CharField(max_length=40, choices=MODULO_CHOICES, default='ventas')
    puede_ver = models.BooleanField(default=False)
    puede_crear = models.BooleanField(default=False)
    puede_editar = models.BooleanField(default=False)
    puede_eliminar = models.BooleanField(default=False)
    puede_aprobar = models.BooleanField(default=False)
    puede_imprimir = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Permiso de Rol por Módulo"
        verbose_name_plural = "Permisos de Rol por Módulo"
        unique_together = ('rol', 'modulo')

    def __str__(self):
        return f"{self.rol.nombre} - {self.modulo}"


class AsignacionRolUsuario(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles_empresa')
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='usuarios_asignados')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='asignaciones_roles')
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asignación de Rol a Usuario"
        verbose_name_plural = "Asignaciones de Rol a Usuario"
        unique_together = ('usuario', 'empresa')

    def __str__(self):
        return f"{self.usuario.username} -> {self.rol.nombre}"


class PermisoRolAccion(models.Model):
    AREA_CHOICES = [
        ('ventas', 'Ventas'),
        ('compras', 'Compras'),
        ('produccion', 'Producción'),
        ('inventario', 'Inventario'),
    ]
    area = models.CharField(max_length=40, choices=AREA_CHOICES, default='ventas')
    submodulo = models.CharField(max_length=60)
    accion = models.CharField(max_length=60)
    permitido = models.BooleanField(default=False)
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='permisos_accion')

    class Meta:
        verbose_name = "Permiso de Rol por Acción"
        verbose_name_plural = "Permisos de Rol por Acción"
        unique_together = ('rol', 'area', 'submodulo', 'accion')

    def __str__(self):
        return f"{self.rol.nombre} - {self.area}.{self.submodulo}.{self.accion}: {self.permitido}"
