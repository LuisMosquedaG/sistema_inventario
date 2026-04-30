from .models import Notificacion

def crear_notificacion(empresa, actor, mensaje, link=None, propietario=None):
    """
    empresa: Objeto Empresa
    actor: User que realiza la acción
    mensaje: Texto de la notificación
    link: URL opcional
    propietario: El usuario que creó el registro (opcional)
    """
    Notificacion.objects.create(
        empresa=empresa,
        actor=actor,
        propietario_recurso=propietario,
        mensaje=mensaje,
        link=link
    )
