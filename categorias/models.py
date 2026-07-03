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
    
    dias_semana = models.CharField(max_length=50, blank=True, null=True, default="", verbose_name="Días de la semana")
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora de Inicio")
    hora_fin = models.TimeField(null=True, blank=True, verbose_name="Hora de Fin")

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def dias_display(self):
        if not self.dias_semana:
            return ""
        mapa_dias = {
            '0': 'Lu',
            '1': 'Ma',
            '2': 'Mi',
            '3': 'Ju',
            '4': 'Vi',
            '5': 'Sá',
            '6': 'Do'
        }
        parts = [mapa_dias.get(d.strip()) for d in self.dias_semana.split(',') if d.strip() in mapa_dias]
        return ", ".join(parts)

    def esta_activa_ahora(self):
        """Verifica si la lista de precios está activa en la hora y día actual."""
        if not self.dias_semana or self.hora_inicio is None or self.hora_fin is None:
            return False
            
        from django.utils import timezone
        # Obtener el tiempo actual local al servidor/tenant
        ahora = timezone.localtime(timezone.now())
        dia_semana_actual = ahora.weekday() # 0 = Lunes, 6 = Domingo
        
        # Validar si el día de hoy está en los días permitidos
        dias_permitidos = []
        for d in self.dias_semana.split(','):
            if d.strip().isdigit():
                dias_permitidos.append(int(d))
        
        # Caso 1: Rango de horas en el mismo día (e.g. 08:00 a 18:00)
        if self.hora_inicio <= self.hora_fin:
            if dia_semana_actual in dias_permitidos:
                return self.hora_inicio <= ahora.time() <= self.hora_fin
            return False
        # Caso 2: El rango cruza la medianoche (e.g. 23:00 a 05:00)
        else:
            # Opción A: Comenzó hoy más tarde por la noche (e.g. son las 23:30, límite fin es mañana 05:00)
            if dia_semana_actual in dias_permitidos and ahora.time() >= self.hora_inicio:
                return True
            # Opción B: Comenzó ayer por la noche y expira hoy más tarde (e.g. hoy a las 02:00, límite fin es hoy 05:00)
            dia_ayer = (dia_semana_actual - 1) % 7
            if dia_ayer in dias_permitidos and ahora.time() <= self.hora_fin:
                return True
            return False

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    class Meta:
        verbose_name = "Lista de Precio/Costo"
        verbose_name_plural = "Listas de Precios/Costos"
        ordering = ['nombre']
