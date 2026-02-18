from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

class Interest(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Questionnaire(models.Model):
    """
    One-time user profile questionnaire.
    Used for personalization and event recommendations.
    """
    full_name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    can_travel_to_sofia = models.BooleanField()
    interests = models.ManyToManyField('Interest')
    about = models.TextField()
    has_children = models.BooleanField()
    wants_events_with_children = models.BooleanField()  
    why_join = models.TextField()
    instagram = models.CharField(max_length=255, blank=True, null=True)
    tiktok = models.CharField(max_length=255, blank=True, null=True)
    linkedin = models.CharField(max_length=255, blank=True, null=True)
    how_did_you_hear = models.CharField(max_length=255)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    friend_name = models.CharField(max_length=255, blank=True, null=True)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Въпросник – {self.user.username}"

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)

    first_name = models.CharField(max_length=30, verbose_name='Име')
    last_name = models.CharField(max_length=30, verbose_name='Фамилия')
    age = models.PositiveIntegerField(null=True, blank=True, verbose_name='Възраст')
    city = models.CharField(max_length=100, blank=True, verbose_name='Град')

    studies = models.BooleanField(default=False, verbose_name='Учи ли')
    education_place = models.CharField(max_length=255, blank=True, null=True, verbose_name='Учебно заведение')

    works = models.BooleanField(default=False, verbose_name='Работи ли')
    work_place = models.CharField(max_length=255, blank=True, null=True, verbose_name='Месторабота')

    about = models.TextField(blank=True, null=True, verbose_name='Информация за Вас')

    is_approved = models.BooleanField(default=False, verbose_name='Одобрен ли е потребителят')
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Снимка'
    )

    def get_role(self):
        if self.is_superuser:
            return 'Администратор'
        elif not self.is_approved:
            return 'Чака одобрение'
        return 'Одобрен потребител'

    def __str__(self):
        return f"{self.username} ({self.email})"

class NotificationSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificationsettings',
        verbose_name='Потребител'
    )
    email_event_reminders = models.BooleanField(
        default=True, verbose_name='Известия за събития, за които съм записана'
    )
    email_event_status_changes = models.BooleanField(
        default=True, verbose_name='Известия за одобрена/отхвърлена заявка за събитие'
    )
    email_recommendations = models.BooleanField(
        default=True, verbose_name='Известия за събития, подходящи за мен'
    )
    email_profile_changes = models.BooleanField(
        default=True, verbose_name='Известия при промяна на лични данни'
    )
    email_questionnaire_changes = models.BooleanField(
        default=True, verbose_name='Известия при промяна на отговори от въпросника'
    )
    email_news = models.BooleanField(
        default=False, verbose_name='Нови предложения и новини от LuxeLadies'
    )

    def __str__(self):
        return f'Настройки известия: {self.user.username}'

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_notifications(sender, instance, created, **kwargs):
    """
    Automatically creates NotificationSettings immediately after a new user registers.
    """
    if created:
        NotificationSettings.objects.create(user=instance)
