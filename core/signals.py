from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .emails import send_templated_email

User = get_user_model()

@receiver(pre_save, sender=User)
def capture_old_is_approved(sender, instance: User, **kwargs):
    """
    We store the old is_approved in instance._old_is_approved,
    to detect a change after the save.
    """
    if not instance.pk:
        instance._old_is_approved = None
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_is_approved = old.is_approved
    except sender.DoesNotExist:
        instance._old_is_approved = None


@receiver(post_save, sender=User)
def notify_on_user_approved(sender, instance: User, created, **kwargs):
    """
    When is_approved is changed from False -> True, we send an email for approval.
    """
    if created:
        return  
    old = getattr(instance, "_old_is_approved", None)
    new = instance.is_approved
    if old is False and new is True:
        if instance.email:
            ctx = {
                "recipient_name": instance.first_name or instance.username,
            }
            send_templated_email(
                subject="LuxeLadies – Регистрацията е одобрена",
                to=[instance.email],
                txt_template="email/user_approved.txt",
                html_template="email/user_approved.html",
                context=ctx,
            )
