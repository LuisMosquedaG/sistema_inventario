from django.core.mail.backends.smtp import EmailBackend
from django.core.mail import EmailMessage
from preferencias.models import UsuarioCorreoSMTP
import logging

logger = logging.getLogger(__name__)

def enviar_correo_usuario(usuario, asunto, cuerpo, destinatarios, archivos_adjuntos=None):
    """
    Envía un correo electrónico utilizando la configuración SMTP personalizada del usuario.
    Si el usuario no tiene configuración SMTP, utiliza la configuración por defecto de Django.
    """
    backend = None
    from_email = None
    
    if usuario:
        try:
            smtp_config = UsuarioCorreoSMTP.objects.get(usuario=usuario)
            if smtp_config.smtp_host and smtp_config.smtp_user:
                use_ssl = smtp_config.use_ssl
                use_tls = smtp_config.use_tls
                port = smtp_config.smtp_port or 587
                if port == 465:
                    use_ssl = True
                    use_tls = False
                elif port in [587, 25] and use_ssl:
                    use_ssl = False
                    use_tls = True

                backend = EmailBackend(
                    host=smtp_config.smtp_host,
                    port=port,
                    username=smtp_config.smtp_user,
                    password=smtp_config.smtp_password,
                    use_tls=use_tls,
                    use_ssl=use_ssl,
                    timeout=10,
                )
                nombre = smtp_config.nombre_remitente or usuario.get_full_name() or usuario.username
                correo = smtp_config.email_remitente or smtp_config.smtp_user
                from_email = f"{nombre} <{correo}>"
        except UsuarioCorreoSMTP.DoesNotExist:
            pass

    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=from_email,
        to=destinatarios,
        connection=backend
    )
    
    if archivos_adjuntos:
        for path in archivos_adjuntos:
            email.attach_file(path)
                
    try:
        email.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo con SMTP de usuario: {e}")
        # Si falló con el SMTP de usuario, intentar con el por defecto de Django como fallback
        if backend is not None:
            try:
                email.connection = None
                email.from_email = None
                email.send(fail_silently=False)
                return True
            except Exception as e_fallback:
                logger.error(f"Error al enviar correo con fallback de Django: {e_fallback}")
        return False


def enviar_correo_contratista(contratista, asunto, cuerpo, destinatarios=None, cc=None, archivos_adjuntos=None, es_html=False):
    """
    Envía un correo electrónico utilizando la configuración SMTP personalizada del contratista.
    Si el contratista tiene configurados correos de notificación (Destinatario / CC), los utiliza.
    Si el contratista no tiene configuración SMTP, utiliza la configuración por defecto de Django.
    """
    backend = None
    from_email = None
    to_emails = list(destinatarios) if destinatarios else []
    cc_emails = list(cc) if cc else []
    
    if contratista:
        try:
            from recursos_humanos.models import ContratistaCorreoSMTP
            smtp_config = ContratistaCorreoSMTP.objects.get(contratista=contratista)
            if smtp_config.smtp_host and smtp_config.smtp_user:
                use_ssl = smtp_config.use_ssl
                use_tls = smtp_config.use_tls
                port = smtp_config.smtp_port or 587
                if port == 465:
                    use_ssl = True
                    use_tls = False
                elif port in [587, 25] and use_ssl:
                    use_ssl = False
                    use_tls = True

                backend = EmailBackend(
                    host=smtp_config.smtp_host,
                    port=port,
                    username=smtp_config.smtp_user,
                    password=smtp_config.smtp_password,
                    use_tls=use_tls,
                    use_ssl=use_ssl,
                    timeout=10,
                )
                nombre = smtp_config.nombre_remitente or contratista.nombre_razon_social
                correo = smtp_config.email_remitente or smtp_config.smtp_user
                from_email = f"{nombre} <{correo}>"

            # Determinar destinatarios de entrada según configuración del contratista
            if not to_emails:
                if smtp_config.email_notificacion_1:
                    to_emails = [smtp_config.email_notificacion_1]
                elif contratista.correo:
                    to_emails = [contratista.correo]

                if smtp_config.email_notificacion_2:
                    cc_emails.append(smtp_config.email_notificacion_2)
                if smtp_config.email_notificacion_3:
                    cc_emails.append(smtp_config.email_notificacion_3)

        except ContratistaCorreoSMTP.DoesNotExist:
            if not to_emails and contratista.correo:
                to_emails = [contratista.correo]

    if not to_emails and contratista and contratista.correo:
        to_emails = [contratista.correo]

    # Eliminar duplicados de CC que ya estén en To
    cc_emails = [c for c in cc_emails if c and c not in to_emails]

    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=from_email,
        to=to_emails,
        cc=cc_emails if cc_emails else None,
        connection=backend
    )
    
    if es_html or (isinstance(cuerpo, str) and any(tag in cuerpo for tag in ['<html', '<div', '<p', '<table', '<br', '<body'])):
        email.content_subtype = "html"

    if archivos_adjuntos:
        for adj in archivos_adjuntos:
            if isinstance(adj, str):
                email.attach_file(adj)
            elif hasattr(adj, 'read') and hasattr(adj, 'name'):
                content_type = getattr(adj, 'content_type', 'application/octet-stream')
                email.attach(adj.name, adj.read(), content_type)
            elif isinstance(adj, (list, tuple)) and len(adj) == 3:
                email.attach(adj[0], adj[1], adj[2])
                
    try:
        email.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo con SMTP de contratista: {e}")
        # Si falló con el SMTP de contratista, intentar con el por defecto de Django como fallback
        if backend is not None:
            try:
                email.connection = None
                email.from_email = None
                email.send(fail_silently=False)
                return True
            except Exception as e_fallback:
                logger.error(f"Error al enviar correo de contratista con fallback de Django: {e_fallback}")
        return False
