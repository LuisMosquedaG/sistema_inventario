from django.db import models
from django.contrib.auth.models import User
from panel.models import Empresa

class Notificacion(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones_enviadas', verbose_name="Quien realizó la acción")
    # El usuario que creó el registro original (si aplica)
    propietario_recurso = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones_recibidas', verbose_name="Dueño del registro")
    
    mensaje = models.CharField(max_length=255, verbose_name="Mensaje")
    link = models.CharField(max_length=255, null=True, blank=True, verbose_name="Enlace al registro")
    
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    
    # Campo para marcar si ya fue mostrada en tiempo real (opcional, para el polling)
    visto_en_toast = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.actor.username} - {self.mensaje}"
