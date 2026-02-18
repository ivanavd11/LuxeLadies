from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


def _already_sent_cache_key(reg_id: int, event_ts: int, label: str) -> str:
    return f"evrem:{reg_id}:{event_ts}:{label}"


def _send_reminder_email(reg, label: str):
    user = reg.user
    event = reg.event
    if not user or not user.email:
        return

    prefs = getattr(user, "notificationsettings", None)
    if prefs and not prefs.email_event_reminders:
        return

    rate = Decimal(getattr(settings, "EVENTS_EUR_RATE", "0.51"))
    price_eur = (Decimal(event.price_bgn) * rate).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    ctx = {
        "recipient_name": user.first_name or user.username,
        "event": event,
        "reg": reg,
        "label": label,
        "price_eur": price_eur,
    }

    subject = f"Напомняне: {event.title} – скоро започва"
    txt = render_to_string("email/event_reminder.txt", ctx)
    html = render_to_string("email/event_reminder.html", ctx)

    email = EmailMultiAlternatives(
        subject=subject,
        body=txt,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html, "text/html")
    email.send(fail_silently=True)


def send_event_reminders_job():
    """
    Стартира се на всеки 5 мин. Праща напомняния:
      - 5 дни преди
      - 1 ден преди
      - 1 час преди
    Избягва дублиране чрез cache ключове (ASCII).
    """
    now = timezone.now()

    horizon = now + timedelta(days=6)

    from events.models import EventRegistration  
    approved_qs = (
        EventRegistration.objects
        .select_related("event", "user")
        .filter(status="approved", event__date_time__gt=now, event__date_time__lte=horizon)
        .order_by("event__date_time")
    )

    windows = [
        ("5d", timedelta(days=5)),
        ("1d", timedelta(days=1)),
        ("1h", timedelta(hours=1)),
    ]

    tolerance = timedelta(minutes=3)

    for reg in approved_qs:
        event_dt = reg.event.date_time
        remaining = event_dt - now
        event_ts = int(event_dt.timestamp())

        for label, delta in windows:
            if abs(remaining - delta) <= tolerance:
                key = _already_sent_cache_key(reg.id, event_ts, label)
                if cache.get(key):
                    continue

                _send_reminder_email(reg, label)
                cache.set(key, 1, timeout=24 * 60 * 60)
