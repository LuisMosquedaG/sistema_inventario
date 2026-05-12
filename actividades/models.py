from django.db import models
from clientes.models import Cliente, ContactoCliente
from cotizaciones.models import Cotizacion
from panel.models import Empresa  # <--- IMPORTANTE: Importamos el modelo Empresa

class Actividad(models.Model):
    # Opciones para Choice Fields
    TIPO_OPCIONES = [
        ('llamada', 'Llamada'),
        ('visita', 'Visita'),
        ('reunion', 'Reunión'),
        ('envio', 'Envío de Propuesta'),
        ('seguimiento', 'Seguimiento'),
    ]

    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]

    PRIORIDAD_OPCIONES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]

    nombre = models.CharField(max_length=200, verbose_name="Actividad")
    fecha = models.DateField(verbose_name="Fecha")
    hora_inicio = models.TimeField(verbose_name="Hora Inicio")
    hora_fin = models.TimeField(verbose_name="Hora Fin", null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_OPCIONES, default='llamada', verbose_name="Tipo")
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_OPCIONES, default='media', verbose_name="Prioridad")
    
    # --- NUEVO CAMPO: MULTI-TENANCY ---
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Empresa (Tenant)")
    sucursal = models.ForeignKey('preferencias.Sucursal', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Sucursal")
    
    # Relaciones
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    contacto = models.ForeignKey(ContactoCliente, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contacto")
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cotización Relacionada")
    
    # Campos rellenados automáticamente (o manuales si se requiere editar)
    correo = models.EmailField(verbose_name="Correo Electrónico")
    direccion = models.TextField(verbose_name="Dirección")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    creado_en = models.DateTimeField(auto_now_add=True)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    motivo_cancelacion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['-fecha', '-hora_inicio']
        verbose_name_plural = "Actividades"