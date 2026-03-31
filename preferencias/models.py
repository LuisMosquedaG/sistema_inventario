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
