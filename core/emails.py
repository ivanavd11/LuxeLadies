from typing import Mapping
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def send_templated_email(
    *,
    subject: str,
    to: list[str],
    txt_template: str,
    html_template: str,
    context: Mapping,
    fail_silently: bool = True,
) -> None:
    """
    Sends multipart/alternative email (text + HTML) from templates.
    If HTML template is missing, sends text only.
    """
    
    if not to:
        return

    text_body = render_to_string(txt_template, context)
    try:
        html_body = render_to_string(html_template, context)
    except Exception:
        html_body = None

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    if html_body:
        email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=fail_silently)
