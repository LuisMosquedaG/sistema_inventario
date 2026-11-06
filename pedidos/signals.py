from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Pedido

@receiver(post_save, sender=Pedido)
def actualizar_tipo_cliente_en_pedido(sender, instance, **kwargs):
    """
    Cuando se crea, actualiza o cancela un pedido, actualiza en tiempo real
    el tipo del cliente asociado (cliente_nuevo, cliente_activo, cliente_inactivo).
    """
    if instance.cliente_id:
        try:
            instance.cliente.actualizar_tipo_cliente()
        except Exception:
            pass
