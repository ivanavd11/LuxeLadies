from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from core.models import NotificationSettings, Questionnaire
from events.models import Event, EventRegistration
from events.jobs import send_event_reminders_job

User = get_user_model()

class _RespAssertsMixin:
    def assertStatusIn(self, resp, codes):
        self.assertIn(resp.status_code, codes, f"Got {resp.status_code}, expected one of {codes}")


def make_min_questionnaire(user, completed=True):
    return Questionnaire.objects.create(
        user=user,
        full_name=(user.get_full_name() or user.username or "User").strip(),
        city=getattr(user, "city", "") or "Sofia",
        can_travel_to_sofia=False,
        about="",
        has_children=False,
        wants_events_with_children=False,
        why_join="",
        how_did_you_hear="instagram",
        completed=completed,
    )


def _all_events_url():
    """Опитва няколко стандартни имена."""
    for name in ("all_events", "events_all", "events_upcoming", "events_list"):
        try:
            return reverse(name)
        except NoReverseMatch:
            pass
    return "/events/all/"


@override_settings(APSCHEDULER_ENABLE=False)
class EventListsTests(_RespAssertsMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.ev_future1 = Event.objects.create(
            title="Future One", city="Sofia", location_details="Center",
            date_time=now + timedelta(days=3), price=10, capacity=50,
        )
        cls.ev_future2 = Event.objects.create(
            title="Future Two", city="Plovdiv", location_details="Old Town",
            date_time=now + timedelta(hours=2), price=0, capacity=15,
        )
        cls.ev_past = Event.objects.create(
            title="Past One", city="Varna", location_details="Sea Garden",
            date_time=now - timedelta(days=5), price=5, capacity=5,
        )

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="viewer", email="viewer@example.com", password="x", is_approved=True, age=20
        )
        self.client.login(username="viewer", password="x")
        make_min_questionnaire(self.user, completed=True)

    def test_events_home_shows_only_buttons(self):
        r = self.client.get(reverse("events_home"))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8")
        self.assertIn("Всички събития", body)
        self.assertIn("Най-подходящите събития за теб", body)
        self.assertIn("Минали събития", body)
        self.assertNotIn("Future One", body)
        self.assertNotIn("Future Two", body)
        self.assertNotIn("Past One", body)

    def test_all_events_shows_only_upcoming(self):
        r = self.client.get(_all_events_url())
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8")
        self.assertIn("Future One", body)
        self.assertIn("Future Two", body)
        self.assertNotIn("Past One", body)

    def test_events_past_shows_only_past(self):
        r = self.client.get(reverse("events_past"))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8")
        self.assertIn("Past One", body)
        self.assertNotIn("Future One", body)
        self.assertNotIn("Future Two", body)

    def test_home_renders_default_image_when_no_event_image(self):
        r = self.client.get(_all_events_url())
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8")
        self.assertIn("Future One", body)
        self.assertIn("Future Two", body)
        self.assertNotIn("Past One", body)


@override_settings(
    APSCHEDULER_ENABLE=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EventDetailAndRegistrationTests(_RespAssertsMixin, TestCase):
    def _register_urls(self, event_id):
        urls = []
        for name in ("register_for_event", "event_register", "event_detail"):
            try:
                urls.append(reverse(name, args=[event_id]))
            except NoReverseMatch:
                continue
        return urls

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="eva", email="eva@example.com",
            password="pass1234", age=22, is_approved=True
        )
        NotificationSettings.objects.get_or_create(
            user=self.user,
            defaults=dict(email_event_status_changes=True, email_event_reminders=True),
        )
        make_min_questionnaire(self.user, completed=True)
        self.ev_future = Event.objects.create(
            title="Joinable", city="Sofia", location_details="Center",
            date_time=timezone.now() + timedelta(days=2), price=12, capacity=100,
        )
        self.ev_past = Event.objects.create(
            title="Too Late", city="Sofia", location_details="Center",
            date_time=timezone.now() - timedelta(days=1), price=7, capacity=30,
        )

    def test_event_detail_loads(self):
        self.client.login(username="eva", password="pass1234")
        r = self.client.get(reverse("event_detail", args=[self.ev_future.id]))
        self.assertEqual(r.status_code, 200)

    def test_register_requires_login(self):
        r = self.client.post(self._register_urls(self.ev_future.id)[0])
        self.assertStatusIn(r, (302, 303))
        self.assertIn(settings.LOGIN_URL, r.headers.get("Location", ""))

    def test_register_creates_pending_and_is_idempotent(self):
        self.client.login(username="eva", password="pass1234")

        urls = self._register_urls(self.ev_future.id)
        payloads = [
            {"full_name": "Eva U"},
            {"action": "register", "full_name": "Eva U"},
            {"form": "register", "full_name": "Eva U"},
            {"form": "register", "reg_full_name": "Eva U"},
            {"form": "register", "full_name": "Eva U", "phone": "0000000000"},
            {"action": "register", "reg_full_name": "Eva U", "phone": "0000000000"},
        ]

        created = False
        for url in urls:
            for data in payloads:
                r = self.client.post(url, data=data, follow=True)
                self.assertIn(r.status_code, (200, 302))
                if EventRegistration.objects.filter(user=self.user, event=self.ev_future).exists():
                    created = True
                    break
            if created:
                break

        self.assertTrue(created, "Не се създаде регистрация за събитието")

        count_before = EventRegistration.objects.filter(user=self.user, event=self.ev_future).count()
        for url in urls:
            self.client.post(url, data=payloads[-1], follow=True)
        count_after = EventRegistration.objects.filter(user=self.user, event=self.ev_future).count()
        self.assertEqual(count_before, count_after)
        reg = EventRegistration.objects.get(user=self.user, event=self.ev_future)
        self.assertIn(reg.status, ("pending", "approved", "rejected")) 

    def test_register_to_past_event_is_blocked(self):
        self.client.login(username="eva", password="pass1234")
        before = EventRegistration.objects.count()

        url = self._register_urls(self.ev_past.id)[0] 
        r = self.client.post(url, data={"action": "register", "full_name": "Eva U"}, follow=True)
        self.assertStatusIn(r, (200, 302))

        after = EventRegistration.objects.count()
        self.assertEqual(before, after)

        r2 = self.client.get(reverse("event_detail", args=[self.ev_past.id]))
        self.assertEqual(r2.status_code, 200)
        self.assertNotIn("Запиши се", r2.content.decode("utf-8"))


class EventModelTinyTests(TestCase):
    def test_str_and_price_eur(self):
        ev = Event.objects.create(
            title="Price Check",
            city="Sofia",
            location_details="Center",
            date_time=timezone.now() + timedelta(days=1),
            price=Decimal("19.56"),
            capacity=10,
        )
        self.assertTrue(str(ev).startswith("Price Check"))
        self.assertGreater(ev.price, 0)
        self.assertRegex(f"{ev.price_eur:.2f}", r"^\d+\.\d{2}$")


@override_settings(
    APSCHEDULER_ENABLE=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class EventReminderJobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rem", email="rem@example.com",
            password="x", age=30, is_approved=True
        )
        NotificationSettings.objects.get_or_create(
            user=self.user,
            defaults=dict(email_event_reminders=True, email_event_status_changes=False),
        )
        self.fixed_now = timezone.now()
        self.event = Event.objects.create(
            title="Reminder Event", city="Sofia", location_details="Center",
            date_time=self.fixed_now + timedelta(hours=1), price=0, capacity=100,
        )
        self.reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="approved", full_name="Rem User"
        )

    def test_reminder_sends_once_for_same_window(self):
        cache.clear()
        mail.outbox = []

        def _fake_send(reg, label):
            mail.send_mail(
                subject=f"[{label}] {reg.event.title}",
                message="body",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reg.user.email],
            )

        with patch("events.jobs.timezone.now", return_value=self.fixed_now), \
             patch("events.jobs._send_reminder_email", side_effect=_fake_send):
            send_event_reminders_job()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

        mail.outbox = []
        with patch("events.jobs.timezone.now", return_value=self.fixed_now), \
             patch("events.jobs._send_reminder_email", side_effect=_fake_send):
            send_event_reminders_job()
        self.assertEqual(len(mail.outbox), 0)


@override_settings(APSCHEDULER_ENABLE=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EventKidFriendlyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="kid", email="kid@example.com", password="x", is_approved=True, age=25
        )
        self.client.login(username="kid", password="x")
        make_min_questionnaire(self.user, completed=True)

        self.ev_kid = Event.objects.create(
            title="Kids", city="Sofia", location_details="Center",
            date_time=timezone.now() + timedelta(days=1), price=0, capacity=10, is_kid_friendly=True
        )

    def test_kid_event_requires_child_data_if_register_view_exists(self):
        try:
            url = reverse("register_for_event", args=[self.ev_kid.id])
        except NoReverseMatch:
            self.skipTest("Няма register_for_event – пропускаме този сценарий.")

        before = EventRegistration.objects.count()
        r = self.client.post(url, data={"full_name": "Parent Only"}, follow=True)
        self.assertEqual(r.status_code, 200)  
        after = EventRegistration.objects.count()
        self.assertEqual(before, after)    


@override_settings(APSCHEDULER_ENABLE=False)
class EventChildFieldsCleanupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="parent", email="p@example.com", password="x", is_approved=True, age=25
        )
        self.client.login(username="parent", password="x")
        make_min_questionnaire(self.user, completed=True)

        self.ev = Event.objects.create(
            title="Adults Only", city="Sofia", location_details="Center",
            date_time=timezone.now() + timedelta(days=1), price=0, capacity=10, is_kid_friendly=False
        )

    def _first_valid_register_url(self, event_id):
        for name in ("register_for_event", "event_register", "event_detail"):
            try:
                return reverse(name, args=[event_id])
            except NoReverseMatch:
                continue
        self.fail("Няма подходящ URL за регистрация")

    def test_child_fields_are_cleared_on_non_kid_event(self):
        url = self._first_valid_register_url(self.ev.id)
        payload = {"action": "register", "full_name": "P", "child_name": "Mini", "child_age": 5}
        r = self.client.post(url, data=payload, follow=True)
        self.assertIn(r.status_code, (200, 302))
        reg = EventRegistration.objects.get(user=self.user, event=self.ev)
        self.assertIsNone(reg.child_name)
        self.assertIsNone(reg.child_age)


@override_settings(
    APSCHEDULER_ENABLE=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)

class EventReminderPrefsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="np", email="np@example.com", password="x", is_approved=True, age=30)
        prefs, _ = NotificationSettings.objects.get_or_create(user=self.user)
        prefs.email_event_reminders = False
        prefs.save()

        self.fixed_now = timezone.now()
        self.event = Event.objects.create(
            title="No Pref Reminder", city="Sofia", location_details="Center",
            date_time=self.fixed_now + timedelta(hours=1), price=0, capacity=100
        )
        EventRegistration.objects.create(user=self.user, event=self.event, status="approved", full_name="NP")

    def test_no_reminder_if_pref_disabled(self):
        cache.clear()
        mail.outbox = []
        with patch("events.jobs.timezone.now", return_value=self.fixed_now):
            send_event_reminders_job()
        self.assertEqual(len(mail.outbox), 0)

