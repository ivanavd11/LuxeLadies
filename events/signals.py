import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import EventRegistration

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=EventRegistration)
def capture_old_status(sender, instance: EventRegistration, **kwargs):
    if instance.pk:
        try:
            old = EventRegistration.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except EventRegistration.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=EventRegistration)
def notify_on_status_change(sender, instance: EventRegistration, created, **kwargs):
    old = getattr(instance, "_old_status", None)
    new = instance.status

    if created and new == 'pending':
        return
    if old == new:
        return
    if not instance.user or not instance.user.email:
        return

    prefs = getattr(instance.user, 'notificationsettings', None)
    if prefs and not prefs.email_event_status_changes:
        return

    recipient_name = instance.full_name or (instance.user.first_name or instance.user.username)
    event = instance.event

    if new == 'approved':
        subject = f"Одобрение за участие: {event.title}"
        txt_template = "email/status_approved.txt"
        html_template = "email/status_approved.html"
    elif new == 'rejected':
        subject = f"Отказ за участие: {event.title}"
        txt_template = "email/status_rejected.txt"
        html_template = "email/status_rejected.html"
    else:
        return

    ctx = {
        "recipient_name": recipient_name,
        "event": event,
        "reg": instance,
    }

    try:
        text_body = render_to_string(txt_template, ctx)
        try:
            html_body = render_to_string(html_template, ctx)
        except Exception:
            html_body = None

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[instance.user.email],
        )
        if html_body:
            email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=True)
    except Exception as exc:
        logger.warning("Failed to send status change email for reg %s: %s", instance.pk, exc)
