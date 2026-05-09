from django.db import models
from panel.models import Empresa  # <--- IMPORTANTE: Importar Empresa

class Categoria(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Categoría")
    
    # --- NUEVO CAMPO MULTI-TENANCY ---
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="Empresa",
        related_name='categorias_catalogo' # <--- AGREGAR ESTO (nombre diferente)
    )
    
    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']

class Subcategoria(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Subcategoría")
    categoria = models.ForeignKey(Categoria, related_name='subcategorias', on_delete=models.CASCADE, verbose_name="Categoría Padre")
    
    # --- NUEVO CAMPO MULTI-TENANCY ---
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="Empresa"
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Subcategoría"
        verbose_name_plural = "Subcategorías"
        ordering = ['nombre']

class ListaPrecioCosto(models.Model):
    TIPO_CHOICES = [
        ('precio', 'Precio'),
        ('costo', 'Costo'),
    ]
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Lista")
    porcentaje_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Porcentaje Extra (%)")
    monto_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Monto Extra ($)")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='precio', verbose_name="Tipo")
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    class Meta:
        verbose_name = "Lista de Precio/Costo"
        verbose_name_plural = "Listas de Precios/Costos"
        ordering = ['nombre']
