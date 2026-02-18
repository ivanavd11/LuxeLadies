from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils.timezone import now, timedelta
from django.conf import settings
from events.models import EventRegistration

class Command(BaseCommand):
    help = "Изпраща напомняния за предстоящи събития (5 дни, 1 ден, 1 час)"

    def handle(self, *args, **kwargs):
        now_time = now()
        reminders = {
            "5 дни": timedelta(days=5),
            "1 ден": timedelta(days=1),
            "1 час": timedelta(hours=1),
        }

        # Само одобрени регистрации и събития в бъдеще
        qs = EventRegistration.objects.select_related("event", "user") \
            .filter(status='approved', event__date_time__gt=now_time)

        sent_count = 0

        for reg in qs:
            event_time = reg.event.date_time

            for label, delta in reminders.items():
                remind_time = event_time - delta

                # В прозорец от 5 минути след remind_time → изпращаме
                if remind_time <= now_time < remind_time + timedelta(minutes=5):
                    if reg.user and reg.user.email:
                        send_mail(
                            subject=f"Напомняне: {reg.event.title} ({label} преди)",
                            message=(
                                f"Здравей, {reg.full_name}!\n\n"
                                f"Напомняме ти, че събитието \"{reg.event.title}\" ще се проведе "
                                f"на {event_time.strftime('%d.%m.%Y %H:%M')} в {reg.event.city}.\n"
                                f"Остават {label}.\n\n"
                                f"Място: {reg.event.location_details}\n"
                                f"Поздрави,\nЕкипът на LuxeLadies"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[reg.user.email],
                            fail_silently=False,
                        )
                        sent_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"Изпратено напомняне ({label}) до {reg.user.email} за {reg.event.title}"
                        ))

        self.stdout.write(self.style.NOTICE(f"Готово. Изпратени {sent_count} напомняния."))