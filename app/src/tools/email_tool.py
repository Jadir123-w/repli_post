import requests
import json
from typing import Annotated, Dict, Any, List, Optional
from langchain_core.tools import InjectedToolCallId, tool
import re
import traceback
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from pathlib import Path

# Obtener la ruta absoluta al archivo .env
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

from app.utils.config import Config

# Configuración de Gmail
# Usar variables de entorno para usuario y contraseña de Gmail
GMAIL_USER = Config.GMAIL_USER
GMAIL_PASSWORD = Config.GMAIL_PASSWORD # Usar una App Password si la autenticación en dos pasos está activa

# Verificar si las credenciales de Gmail están configuradas
if not GMAIL_USER or not GMAIL_PASSWORD:
    print("ADVERTENCIA: GMAIL_USER o GMAIL_PASSWORD no encontrados en .env. El envío de correos fallará.")
    # Considerar lanzar una excepción en producción si el envío de correos es crítico

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # Puerto TLS para Gmail

def create_elegant_email_template(
    title: str,
    content: str,
    summary: str = None,
    service_type: str = None,
    payment_info: str = None
) -> str:
    """
    Crea una plantilla de correo elegante con diseño moderno.

    Args:
        title: Título del correo
        content: Contenido principal
        summary: Resumen de la conversación (opcional)
        service_type: Tipo de servicio adquirido (opcional)
        payment_info: Información de pago (opcional)

    Returns:
        str: HTML del correo con diseño elegante
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                line-height: 1.6;
                color: #333333;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #4A90E2;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #ffffff;
                padding: 20px;
                border: 1px solid #e0e0e0;
                border-radius: 0 0 5px 5px;
            }}
            .summary {{
                background-color: #f8f9fa;
                padding: 15px;
                margin: 20px 0;
                border-left: 4px solid #4A90E2;
                border-radius: 0 5px 5px 0;
            }}
            .service-info {{
                background-color: #e8f4fd;
                padding: 15px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            .payment-info {{
                background-color: #f0f7e6;
                padding: 15px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #666666;
                font-size: 12px;
            }}
            h1 {{
                margin: 0;
                font-size: 24px;
            }}
            h2 {{
                color: #4A90E2;
                margin-top: 0;
            }}
            p {{
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                {content}

                {f'<div class="summary"><h2>Resumen de la Conversación</h2>{summary}</div>' if summary else ''}

                {f'<div class="service-info"><h2>Detalles del Servicio</h2>{service_type}</div>' if service_type else ''}

                {f'<div class="payment-info"><h2>Información de Pago</h2>{payment_info}</div>' if payment_info else ''}
            </div>
            <div class="footer">
                <p>Este es un correo automático de Repliker. Por favor, no responda a este mensaje.</p>
                <p>© 2025 Repliker. Todos los derechos reservados.</p>
            </div>
        </div>
    </body>
    </html>
    """

def validate_email(email: str) -> bool:
    """
    Valida que una dirección de correo electrónico tenga un formato correcto.

    Args:
        email (str): La dirección de correo a validar

    Returns:
        bool: True si el formato es válido, False en caso contrario
    """
    # Patrón para validar correos electrónicos
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def send_email(
    subject: str,
    body: str,
    recipients: List[str],
    sender_email: str = None,
    summary: str = None,
    service_type: str = None,
    payment_info: str = None
) -> Dict[str, Any]:
    """
    Envía un correo electrónico con diseño elegante.

    Args:
        subject: Asunto del correo
        body: Contenido principal
        recipients: Lista de correos destinatarios
        sender_email: Correo del remitente (opcional)
        summary: Resumen de la conversación (opcional)
        service_type: Tipo de servicio (opcional)
        payment_info: Información de pago (opcional)

    Returns:
        Dict[str, Any]: Resultado de la operación
    """
    try:
        print("\n=== [HERRAMIENTA send_email] INICIANDO ENVÍO DE CORREO ===")
        print(f"[HERRAMIENTA] Asunto: {subject}")
        print(f"[HERRAMIENTA] Destinatarios: {recipients}")
        print(f"[HERRAMIENTA] Resumen: {summary if summary else 'No se proporcionó'}")
        print(f"[HERRAMIENTA] Servicio: {service_type if service_type else 'No se proporcionó'}")
        print(f"[HERRAMIENTA] Pago: {payment_info if payment_info else 'No se proporcionó'}")

        # Validar los correos destinatarios
        invalid_emails = [email for email in recipients if not validate_email(email)]
        if invalid_emails:
            print(f"[HERRAMIENTA] Correos inválidos detectados: {invalid_emails}")
            return {
                "success": False,
                "message": f"Los siguientes correos tienen un formato inválido: {', '.join(invalid_emails)}"
            }

        print("[HERRAMIENTA] Creando mensaje con diseño elegante...")
        # Crear mensaje con diseño elegante
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender_email or GMAIL_USER # Usar GMAIL_USER como remitente por defecto
        msg['To'] = ', '.join(recipients)

        print("[HERRAMIENTA] Generando contenido HTML...")
        # Crear contenido HTML con diseño elegante
        html_content = create_elegant_email_template(
            title=subject,
            content=body,
            summary=summary,
            service_type=service_type,
            payment_info=payment_info
        )

        print("[HERRAMIENTA] Adjuntando contenido al mensaje...")
        # Agregar cuerpo del mensaje
        msg.attach(MIMEText(html_content, 'html'))

        print(f"[HERRAMIENTA] Conectando al servidor SMTP: {SMTP_SERVER}:{SMTP_PORT}...")
        # Conectar al servidor SMTP de Gmail usando TLS
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp_server:
            print("[HERRAMIENTA] Iniciando TLS...")
            smtp_server.starttls()  # Iniciar conexión TLS
            print("[HERRAMIENTA] Iniciando sesión en Gmail...")
            smtp_server.login(GMAIL_USER, GMAIL_PASSWORD)
            print("[HERRAMIENTA] Enviando mensaje...")
            smtp_server.send_message(msg)

        print(f"[HERRAMIENTA] Correo enviado exitosamente a {len(recipients)} destinatarios")
        return {
            "success": True,
            "message": "Correo enviado exitosamente"
        }

    except Exception as e:
        print(f"[HERRAMIENTA] Error en send_email: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "message": f"Error al enviar el correo: {str(e)}"
        }

def send_html_template_email(
    subject: str,
    template_name: str,
    template_data: Dict[str, Any],
    recipients: List[str],
    sender_email: str = None
) -> Dict[str, Any]:
    """
    Envía un correo usando una plantilla HTML predefinida.

    Args:
        subject (str): Asunto del correo
        template_name (str): Nombre de la plantilla a utilizar
        template_data (Dict[str, Any]): Datos para rellenar la plantilla
        recipients (List[str]): Lista de correos destinatarios
        sender_email (str, optional): Correo del remitente. Si es None, se usa el correo por defecto.

    Returns:
        Dict[str, Any]: Diccionario con el resultado de la operación
    """
    try:
        # Validar los correos destinatarios
        invalid_emails = [email for email in recipients if not validate_email(email)]
        if invalid_emails:
            return {
                "success": False,
                "message": f"Los siguientes correos tienen un formato inválido: {', '.join(invalid_emails)}"
            }

        # Crear mensaje
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender_email or GMAIL_USER # Usar GMAIL_USER
        msg['To'] = ', '.join(recipients)

        # Crear contenido HTML basado en la plantilla
        html_content = f"""
        <html>
            <body>
                <h2>{template_data.get('title', '')}</h2>
                <p>{template_data.get('content', '')}</p>
            </body>
        </html>
        """

        # Agregar cuerpo del mensaje
        msg.attach(MIMEText(html_content, 'html'))

        # Conectar al servidor SMTP de Gmail usando TLS
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp_server.send_message(msg)

        print(f"Correo con plantilla '{template_name}' enviado exitosamente a {len(recipients)} destinatarios")
        return {
            "success": True,
            "message": "Correo con plantilla enviado exitosamente"
        }

    except Exception as e:
        print(f"Error en send_html_template_email: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "message": f"Error al enviar el correo con plantilla: {str(e)}"
        }

# Versiones para LangChain
@tool
def send_email_tool(
    subject: str,
    body: str,
    recipients: List[str],
    sender_email: str = None,
    summary: str = None,
    service_type: str = None,
    payment_info: str = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None
) -> str:
    """
    Envía un correo electrónico con diseño elegante.

    Args:
        subject: Asunto del correo
        body: Contenido principal
        recipients: Lista de correos destinatarios
        sender_email: Correo del remitente (opcional)
        summary: Resumen de la conversación (opcional)
        service_type: Tipo de servicio (opcional)
        payment_info: Información de pago (opcional)

    Returns:
        Mensaje con el resultado de la operación
    """
    print("\n=== [HERRAMIENTA send_email_tool] INICIANDO ===")
    print(f"[HERRAMIENTA] Parámetros recibidos:")
    print(f"- Asunto: {subject}")
    print(f"- Destinatarios: {recipients}")
    print(f"- Resumen: {summary if summary else 'No se proporcionó'}")
    print(f"- Servicio: {service_type if service_type else 'No se proporcionó'}")
    print(f"- Pago: {payment_info if payment_info else 'No se proporcionó'}")

    result = send_email(
        subject=subject,
        body=body,
        recipients=recipients,
        sender_email=sender_email,
        summary=summary,
        service_type=service_type,
        payment_info=payment_info
    )

    print(f"[HERRAMIENTA] Resultado: {result['message']}")
    return result["message"]

@tool
def send_template_email_tool(
    subject: str,
    template_name: str,
    template_data: Dict[str, Any],
    recipients: List[str],
    sender_email: str = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None
) -> str:
    """
    Envía un correo usando una plantilla HTML predefinida.

    Args:
        subject: Asunto del correo
        template_name: Nombre de la plantilla a utilizar
        template_data: Datos para rellenar la plantilla
        recipients: Lista de correos destinatarios
        sender_email: Correo del remitente (opcional)

    Returns:
        Mensaje con el resultado de la operación
    """
    result = send_html_template_email(subject, template_name, template_data, recipients, sender_email)
    return result["message"]

@tool
def send_notification_email_tool(
    title: str,
    description: str,
    recipients: List[str],
    sender_email: str = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None
) -> str:
    """
    Envía un correo de notificación simple con título y descripción.

    Args:
        title: Título de la notificación (también se usa como asunto)
        description: Descripción o cuerpo de la notificación
        recipients: Lista de correos destinatarios
        sender_email: Correo del remitente (opcional)

    Returns:
        Mensaje con el resultado de la operación
    """
    # Crear HTML simple
    html_content = f"""
    <html>
      <body>
        <h2>{title}</h2>
        <p>{description}</p>
      </body>
    </html>
    """

    result = send_email(title, html_content, recipients, sender_email)
    return result["message"]

def send_cv_email(
    subject: str,
    legal_content: str,
    recipients: List[str],
    sender_email: str = None,
    summary: str = None,
    service_type: str = None,
    payment_info: str = None
) -> Dict[str, Any]:
    """
    Envía un correo con el Propuesta.

    Args:
        subject: Asunto del correo
        legal_content: Contenido del Propuesta
        recipients: Lista de correos destinatarios
        sender_email: Correo del remitente (opcional)
        summary: Resumen de la conversación (opcional)
        service_type: Tipo de servicio (opcional)
        payment_info: Información de pago (opcional)

    Returns:
        Dict[str, Any]: Resultado de la operación
    """
    try:
        print("--- [HERRAMIENTA send_cv_email] Iniciando envío de correo ---")
        print(f"[HERRAMIENTA] Asunto: {subject}")
        print(f"[HERRAMIENTA] Destinatarios: {recipients}")

        # Validar los correos destinatarios
        invalid_emails = [email for email in recipients if not validate_email(email)]
        if invalid_emails:
            print(f"[HERRAMIENTA] Correos inválidos detectados: {invalid_emails}")
            return {
                "success": False,
                "message": f"Los siguientes correos tienen un formato inválido: {', '.join(invalid_emails)}"
            }

        print("[HERRAMIENTA] Creando mensaje con diseño elegante...")
        # Crear mensaje con diseño elegante
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender_email or GMAIL_USER # Usar GMAIL_USER
        msg['To'] = ', '.join(recipients)

        print("[HERRAMIENTA] Generando contenido HTML...")
        # Crear contenido HTML con diseño elegante
        html_content = create_elegant_email_template(
            title=subject,
            content=f"""
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
                <h2 style="color: #4A90E2; margin-top: 0;">Propuesta Legal</h2>
                <div style="white-space: pre-wrap; font-family: 'Arial', sans-serif;">
                    {legal_content}
                </div>
            </div>
            """,
            summary=summary,
            service_type=service_type,
            payment_info=payment_info
        )

        print("[HERRAMIENTA] Adjuntando contenido al mensaje...")
        # Agregar cuerpo del mensaje
        msg.attach(MIMEText(html_content, 'html'))

        print("[HERRAMIENTA] Conectando al servidor SMTP de Gmail...")
        # Conectar al servidor SMTP de Gmail usando TLS
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp_server.send_message(msg)

        print(f"[HERRAMIENTA] Correo enviado exitosamente a {len(recipients)} destinatarios")
        return {
            "success": True,
            "message": "Correo la Propuesta Legal enviado exitosamente"
        }

    except Exception as e:
        print(f"[HERRAMIENTA] Error en send_cv_email: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "message": f"Error al enviar el correo con la Propuesta Legal: {str(e)}"
        }

@tool
def send_legal_email_tool(
    subject: str,
    legal_content: str,
    recipients: List[str],
    sender_email: str = None,
    summary: str = None,
    service_type: str = None,
    payment_info: str = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None
) -> str:
    """
    Envía un correo con Propuesta Legal optimizado.

    Args:
        subject: Asunto del correo
        legal_content: Contenido de la Propuesta Legal
        recipients: Lista de correos destinatarios
        sender_email: Correo del remitente (opcional)
        summary: Resumen de la conversación (opcional)
        service_type: Tipo de servicio (opcional)
        payment_info: Información de pago (opcional)

    Returns:
        Mensaje con el resultado de la operación
    """
    result = send_cv_email(
        subject=subject,
        legal_content=legal_content,
        recipients=recipients,
        sender_email=sender_email,
        summary=summary,
        service_type=service_type,
        payment_info=payment_info
    )
    return result["message"]
