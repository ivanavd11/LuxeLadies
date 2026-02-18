from django.db import models
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from core.models import Interest

EUR_BGN = Decimal('1.95583')


class Event(models.Model):
    title = models.CharField(max_length=200, verbose_name="Заглавие на събитието")
    description = models.TextField(verbose_name="Описание")
    date_time = models.DateTimeField(verbose_name="Дата и час")

    city = models.CharField(max_length=100, verbose_name="Град")
    location_details = models.CharField(max_length=300, verbose_name="Точно местоположение")

    is_kid_friendly = models.BooleanField(default=False, verbose_name="Подходящо за деца")

    interests = models.ManyToManyField(Interest, related_name='events', verbose_name="Интереси")

    image = models.ImageField(upload_to='event_images/', null=True, blank=True, verbose_name="Основна снимка")

    capacity = models.PositiveIntegerField(verbose_name="Максимален капацитет")
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='registered_events',
        blank=True,
        verbose_name="Записани участници"
    )

    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.city}) - {self.date_time.strftime('%d.%m.%Y')}"

    @property
    def free_spots(self):
        approved_count = self.registrations.filter(status='approved').count()
        return max(0, self.capacity - approved_count)
    
    @property
    def price_eur(self):
        if self.price is None:
            return None
        eur = (Decimal(self.price) / EUR_BGN).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        return eur

    def is_past(self):
        return self.date_time < timezone.now()


class EventRegistration(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Очаква одобрение'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отказано'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150)
    child_name = models.CharField(max_length=150, blank=True, null=True)
    child_age = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')
        verbose_name = "Заявка за събитие"
        verbose_name_plural = "Заявки за събития"

    def __str__(self):
        return f"{self.full_name} - {self.event.title} ({self.get_status_display()})"
