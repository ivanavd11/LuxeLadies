"""
unittests for:
- Registration/login and business access rules.
- Admin panel: access, sorting, search, approve/reject/delete.
- Profile: data update, avatar, notifications, future/past events separation.
- Emails: template helper, HTML alternative, status change alerts.
"""
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.template.exceptions import TemplateDoesNotExist
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from core.emails import send_templated_email
from core.forms import CustomUserRegistrationForm
from core.models import NotificationSettings, Questionnaire
from events.models import Event, EventRegistration

User = get_user_model()

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
    b"\x0b\xe7\x02\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
)

class _RespAssertsMixin:
    def assertStatusIn(self, resp, codes):
        self.assertIn(resp.status_code, codes, f"Got {resp.status_code}, expected one of {codes}")


class RegistrationAndLoginTests(_RespAssertsMixin, TestCase):
    """
    Validating the registration form and login/approval rules.
    """
    def test_registration_form_validation(self):
        f = CustomUserRegistrationForm(
            data=dict(
                username="u1",
                first_name="F",
                last_name="L",
                email="u1@example.com",
                age=22,
                city="Sofia",
                password="x1",
                confirm_password="x2",
                studies="yes",
                education_place="SU",
                works="no",
                work_place="",
                about="",
            )
        )
        self.assertFalse(f.is_valid())
        self.assertIn("Паролите", " ".join(sum(f.errors.values(), [])))

        f = CustomUserRegistrationForm(
            data=dict(
                username="u2",
                first_name="F",
                last_name="L",
                email="u2@example.com",
                age=17,
                city="Sofia",
                password="same",
                confirm_password="same",
                studies="no",
                education_place="",
                works="yes",
                work_place="ACME",
                about="",
            )
        )
        self.assertFalse(f.is_valid())
        self.assertIn("навършени 18", " ".join(sum(f.errors.values(), [])))

    def test_registration_view_creates_user(self):
        resp = self.client.post(
            reverse("register"),
            data=dict(
                username="u3",
                first_name="Ana",
                last_name="Ivanova",
                email="u3@example.com",
                age=23,
                city="Varna",
                password="pass1234",
                confirm_password="pass1234",
                studies="yes",
                education_place="VFU",
                works="no",
                work_place="",
                about="Hello!",
            ),
            follow=True,
        )
        self.assertStatusIn(resp, (200, 302))
        self.assertTrue(User.objects.filter(username="u3").exists())
        u = User.objects.get(username="u3")
        self.assertFalse(u.is_approved)
        self.assertTrue(u.is_active)
        self.assertTrue(u.studies)
        self.assertFalse(u.works)

    def test_login_rules(self):
        u = User.objects.create_user(username="u4", email="u4@example.com", password="pass1234", age=22, is_approved=False)
        resp = self.client.post(reverse("login"), data={"username": "u4", "password": "pass1234"}, follow=True)
        self.assertStatusIn(resp, (200, 302))
        self.assertContains(resp, "регистрация все още не е одобрена", status_code=200)

        u.is_approved = True
        u.save()
        resp = self.client.post(reverse("login"), data={"username": "u4", "password": "pass1234"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("home"))


@override_settings(APSCHEDULER_ENABLE=False)
class AdminPanelTests(_RespAssertsMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass1234")
        # Одобрени
        cls.u_a = User.objects.create_user(username="alice", email="a@ex.com", age=21, is_approved=True, city="Sofia", password="x")
        cls.u_b = User.objects.create_user(username="bob",   email="b@ex.com", age=28, is_approved=True, city="Plovdiv", password="x")
        cls.u_c = User.objects.create_user(username="carol", email="c@ex.com", age=25, is_approved=True, city="Varna",   password="x")
        # Чакащи
        cls.u_p = User.objects.create_user(username="peter", email="p@ex.com", age=26, is_approved=False, password="x")

    def setUp(self):
        self.client = Client()

    def test_access(self):
        # анонимен
        r = self.client.get(reverse("admin_panel"))
        self.assertStatusIn(r, (302, 401, 403))
        # логнат, не e админ
        self.client.login(username="alice", password="x")
        r = self.client.get(reverse("admin_panel"))
        self.assertStatusIn(r, (302, 401, 403))
        # админ
        self.client.logout()
        self.client.login(username="admin", password="pass1234")
        r = self.client.get(reverse("admin_panel"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["pending_users"].filter(username="peter").exists())
        self.assertTrue(r.context["approved_users"].filter(username="alice").exists())

    def _names(self, resp):
        return list(resp.context["approved_users"].values_list("username", flat=True))

    def test_sort_username(self):
        self.client.login(username="admin", password="pass1234")
        r = self.client.get(reverse("admin_panel") + "?sort=username_asc")
        self.assertEqual(self._names(r), ["alice", "bob", "carol"])
        r = self.client.get(reverse("admin_panel") + "?sort=username_desc")
        self.assertEqual(self._names(r), ["carol", "bob", "alice"])

    def test_sort_age(self):
        self.client.login(username="admin", password="pass1234")
        r = self.client.get(reverse("admin_panel") + "?sort=age_asc")
        self.assertEqual(self._names(r), ["alice", "carol", "bob"])
        r = self.client.get(reverse("admin_panel") + "?sort=age_desc")
        self.assertEqual(self._names(r), ["bob", "carol", "alice"])

    def test_search(self):
        self.client.login(username="admin", password="pass1234")
        r = self.client.get(reverse("admin_panel") + "?search=varna")
        self.assertEqual(self._names(r), ["carol"])
        r = self.client.get(reverse("admin_panel") + "?search=alice")
        self.assertEqual(self._names(r), ["alice"])

    def test_approve_reject_delete_user(self):
        self.client.login(username="admin", password="pass1234")
        u = User.objects.create_user(username="xx", email="xx1@example.com", age=19, studies=False, works=False, password="x")
        self.client.get(reverse("approve_user", kwargs={"user_id": u.id}))
        u.refresh_from_db()
        self.assertFalse(u.is_approved)

        u2 = User.objects.create_user(username="yy", email="yy1@example.com", age=19, studies=True, works=False, password="x")
        self.client.get(reverse("approve_user", kwargs={"user_id": u2.id}))
        u2.refresh_from_db()
        self.assertTrue(u2.is_approved)

        u3 = User.objects.create_user(username="delme", age=22, password="x")
        self.client.get(reverse("reject_user", kwargs={"user_id": u3.id}))
        self.assertFalse(User.objects.filter(id=u3.id).exists())


def make_min_questionnaire(user):
    return Questionnaire.objects.create(
        user=user,
        full_name=(user.get_full_name() or user.username or "User").strip(),
        city=(getattr(user, "city", "") or "Sofia"),
        can_travel_to_sofia=False,
        about="",
        has_children=False,
        wants_events_with_children=False,
        why_join="",
        how_did_you_hear="instagram",  
        completed=False,
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MyProfileTests(_RespAssertsMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="puser", email="puser@example.com", password="pass1234", is_approved=True, age=22
        )
        NotificationSettings.objects.get_or_create(
            user=self.user,
            defaults=dict(
                email_event_reminders=True,
                email_event_status_changes=True,
                email_recommendations=True,
                email_profile_changes=True,
                email_questionnaire_changes=True,
                email_news=False,
            ),
        )
        make_min_questionnaire(self.user)
        self.client.login(username="puser", password="pass1234")

    def test_get_profile(self):
        r = self.client.get(reverse("my_profile"))
        self.assertEqual(r.status_code, 200)
        for key in ("form", "q_form", "notif_form", "approved_events", "past_events"):
            self.assertIn(key, r.context)

    def test_update_profile_sends_email_if_allowed(self):
        mail.outbox = []
        data = {
            "form": "profile",
            "first_name": "New",
            "last_name": "Name",
            "username": "puser",
            "email": "puser@example.com",
        }
        r = self.client.post(reverse("my_profile"), data=data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_update_profile_no_email_if_disabled(self):
        prefs = NotificationSettings.objects.get(user=self.user)
        prefs.email_profile_changes = False
        prefs.save()

        mail.outbox = []
        data = {"form": "profile", "first_name": "X", "last_name": "Y", "username": "puser", "email": "puser@example.com"}
        r = self.client.post(reverse("my_profile"), data=data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)


    def test_save_notifications_sends_confirmation(self):
        mail.outbox = []
        data = {
            "form": "notifications",
            "email_event_reminders": "on",
            "email_event_status_changes": "on",
            "email_recommendations": "",  
            "email_profile_changes": "on",
            "email_questionnaire_changes": "on",
            "email_news": "",  
        }
        r = self.client.post(reverse("my_profile"), data=data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_profile_lists_future_and_past_events(self):
        ev_future = Event.objects.create(
            title="Future A", city="Sofia",location_details="Center", date_time=timezone.now() + timedelta(days=3), price=10,capacity=50,
        )
        ev_past = Event.objects.create(
            title="Past A", city="Sofia", location_details="Center", date_time=timezone.now() - timedelta(days=3), price=5,capacity=10,
        )
        EventRegistration.objects.create(user=self.user, event=ev_future, status="approved", full_name="X")
        EventRegistration.objects.create(user=self.user, event=ev_past,   status="approved", full_name="X")

        r = self.client.get(reverse("my_profile"))
        self.assertEqual(r.status_code, 200)
        fut = [e.title for e in r.context["approved_events"]]
        pst = [e.title for e in r.context["past_events"]]
        self.assertIn("Future A", fut)
        self.assertIn("Past A", pst)


@override_settings(APSCHEDULER_ENABLE=False)
class EventRegistrationAdminViewsTests(_RespAssertsMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass1234")
        cls.user = User.objects.create_user(username="eva", email="eva@example.com", password="x", age=22, is_approved=True)
        cls.event_future = Event.objects.create(
            title="Future Event",
            city="Sofia",
            location_details="Center",
            date_time=timezone.now() + timedelta(days=3),
            price=30,
            capacity=50,  
        )
        cls.reg_pending = EventRegistration.objects.create(
            user=cls.user, event=cls.event_future, status="pending", full_name="Eva U"
        )
        
        NotificationSettings.objects.get_or_create(
            user=cls.user,
            defaults=dict(
                email_event_status_changes=True,
                email_event_reminders=False,
                email_recommendations=False,
                email_profile_changes=False,
                email_questionnaire_changes=False,
                email_news=False,
            ),
        )

    def setUp(self):
        self.client = Client()

    def test_admin_event_registrations_access(self):
        # не-логнат
        r = self.client.get(reverse("admin_event_registrations"))
        self.assertStatusIn(r, (302, 401, 403))
        # логнат, но не админ
        self.client.login(username="eva", password="x")
        r = self.client.get(reverse("admin_event_registrations"))
        self.assertStatusIn(r, (302, 401, 403))
        # админ
        self.client.logout()
        self.client.login(username="admin", password="pass1234")
        r = self.client.get(reverse("admin_event_registrations"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("pending_regs", r.context)
        self.assertTrue(r.context["pending_regs"].filter(id=self.reg_pending.id).exists())

    def test_approve_registration_triggers_email(self):
        self.client.login(username="admin", password="pass1234")
        mail.outbox = []
        r = self.client.get(reverse("approve_registration", kwargs={"reg_id": self.reg_pending.id}))
        self.assertEqual(r.status_code, 302)
        self.reg_pending.refresh_from_db()
        self.assertEqual(self.reg_pending.status, "approved")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_reject_registration_triggers_email(self):
        self.reg_pending.status = "pending"
        self.reg_pending.save()
        self.client.login(username="admin", password="pass1234")
        mail.outbox = []
        r = self.client.get(reverse("reject_registration", kwargs={"reg_id": self.reg_pending.id}))
        self.assertEqual(r.status_code, 302)
        self.reg_pending.refresh_from_db()
        self.assertEqual(self.reg_pending.status, "rejected")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProfileEmailsDeepTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="maria", first_name="Мария", email="maria@example.com",
            password="pass1234", is_approved=True, age=25
        )
        NotificationSettings.objects.get_or_create(
            user=self.user,
            defaults=dict(
                email_event_reminders=True,
                email_event_status_changes=True,
                email_recommendations=True,
                email_profile_changes=True,
                email_questionnaire_changes=True,
                email_news=False,
            ),
        )
        make_min_questionnaire(self.user)
        self.client.login(username="maria", password="pass1234")

    def test_profile_update_email_subject_from_and_html_alt(self):
        mail.outbox = []
        r = self.client.post(
            reverse("my_profile"),
            data={
                "form": "profile",
                "username": "maria",
                "email": "maria@example.com",
                "first_name": "Мария",
                "last_name": "Иванова",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        m = mail.outbox[0]
        self.assertTrue(m.subject.startswith("LuxeLadies – Профилът е обновен"))
        self.assertIn(self.user.email, m.to)
        self.assertEqual(m.from_email, settings.DEFAULT_FROM_EMAIL)

        self.assertTrue(hasattr(m, "alternatives") and len(m.alternatives) == 1)
        html_body, mime = m.alternatives[0]
        self.assertEqual(mime, "text/html")
        self.assertIn("Мария", m.body)      
        self.assertIn("Мария", html_body)  

    def test_notifications_email_body_contains_preferences(self):
        mail.outbox = []
        r = self.client.post(
            reverse("my_profile"),
            data={
                "form": "notifications",
                "email_event_reminders": "on",
                "email_event_status_changes": "on",
                "email_recommendations": "",   
                "email_profile_changes": "on",
                "email_questionnaire_changes": "on",
                "email_news": "",              
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertTrue(m.subject.startswith("LuxeLadies – Настройките за имейл известия са обновени"))
        self.assertRegex(m.body, r"Напомняния за събития.*ДА|НЕ")

    def test_send_templated_email_direct(self):
        mail.outbox = []
        send_templated_email(
            subject="Тестов мейл",
            to=["someone@example.com"],
            txt_template="email/profile_updated.txt",
            html_template="email/profile_updated.html",
            context={"recipient_name": "Тест"},
        )
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.subject, "Тестов мейл")
        self.assertIn("Тест", m.body)
        self.assertTrue(m.alternatives and m.alternatives[0][1] == "text/html")

        with self.assertRaises(TemplateDoesNotExist):
            send_templated_email(
                subject="X",
                to=["x@ex.com"],
                txt_template="email/does_not_exist.txt",
                html_template=None,
                context={},
            )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   APSCHEDULER_ENABLE=False)
class EventRegistrationSignalEmailDeepTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass1234"
        )
        cls.user = User.objects.create_user(
            username="sig", email="sig@example.com", password="x",
            age=30, is_approved=True
        )
        NotificationSettings.objects.get_or_create(
            user=cls.user,
            defaults=dict(
                email_event_status_changes=True,
                email_event_reminders=False,
                email_recommendations=False,
                email_profile_changes=False,
                email_questionnaire_changes=False,
                email_news=False,
            ),
        )
        cls.event = Event.objects.create(
            title="Signal Event",
            city="Sofia",
            location_details="Center",
            date_time=timezone.now() + timedelta(days=2),
            price=12,
            capacity=20,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="pass1234")

    def test_no_email_on_pending_creation(self):
        mail.outbox = []
        EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="Foo Bar"
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_email_sent_on_approve_then_not_again_if_same_status(self):
        reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="Foo Bar"
        )
        mail.outbox = []
        self.client.get(reverse("approve_registration", kwargs={"reg_id": reg.id}))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.assertIn(self.event.title, mail.outbox[0].subject)

        mail.outbox = []
        self.client.get(reverse("approve_registration", kwargs={"reg_id": reg.id}))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_sent_on_reject_and_contains_event_data(self):
        reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="Foo Bar"
        )
        mail.outbox = []
        self.client.get(reverse("reject_registration", kwargs={"reg_id": reg.id}))
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertIn(self.user.email, m.to)
        self.assertIn(self.event.title, m.subject)
        self.assertIn(self.event.title, m.body)

    def test_no_email_if_user_has_no_email(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])
        reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="No Mail"
        )
        mail.outbox = []
        self.client.get(reverse("approve_registration", kwargs={"reg_id": reg.id}))
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_if_pref_disabled(self):
        prefs = NotificationSettings.objects.get(user=self.user)
        prefs.email_event_status_changes = False
        prefs.save()

        reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="No Pref"
        )
        mail.outbox = []
        self.client.get(reverse("approve_registration", kwargs={"reg_id": reg.id}))
        self.assertEqual(len(mail.outbox), 0)

    def test_unicode_names_do_not_break_email(self):
        self.user.first_name = "Весела"
        self.user.save(update_fields=["first_name"])
        reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="Весела Потребител"
        )
        mail.outbox = []
        self.client.get(reverse("approve_registration", kwargs={"reg_id": reg.id}))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Весела", mail.outbox[0].body)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProfileEmailsEdgeCasesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="edge",
            email="edge@example.com",
            password="pass1234",
            age=22,
            is_approved=True,
        )
        prefs, _ = NotificationSettings.objects.get_or_create(user=self.user)
        prefs.email_profile_changes = True
        prefs.email_event_reminders = False
        prefs.email_event_status_changes = False
        prefs.email_recommendations = False
        prefs.email_questionnaire_changes = False
        prefs.email_news = False
        prefs.save()

        make_min_questionnaire(self.user)
        self.client.login(username="edge", password="pass1234")

    def test_profile_email_uses_username_when_first_name_missing(self):
        mail.outbox = []
        resp = self.client.post(
            reverse("my_profile"),
            data={
                "form": "profile",
                "username": "edge",
                "email": "edge@example.com",
                "first_name": "",   
                "last_name": "X",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("edge", mail.outbox[0].body)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EventEmailsUnicodeAndHtmlTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser("adm", "a@example.com", "x")
        self.user = User.objects.create_user("uni", "uni@example.com", "x", age=25, is_approved=True)
        NotificationSettings.objects.get_or_create(
            user=self.user, defaults={"email_event_status_changes": True}
        )
        self.event = Event.objects.create(
            title="Събитие с Юникод",
            city="Sofia",
            location_details="Center",
            date_time=timezone.now() + timedelta(days=5),
            price=0,
            capacity=10,
        )
        self.reg = EventRegistration.objects.create(
            user=self.user, event=self.event, status="pending", full_name="Uni User"
        )
        self.client.login(username="adm", password="x")

    def test_approve_unicode_subject_and_html_alt(self):
        mail.outbox = []
        self.client.get(reverse("approve_registration", kwargs={"reg_id": self.reg.id}))
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertIn("Събитие с Юникод", m.subject)
        if getattr(m, "alternatives", None):
            self.assertTrue(len(m.alternatives) >= 1)
            self.assertEqual(m.alternatives[0][1], "text/html")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProfileRemoveAvatarNoFileTests(TestCase):
    """Remove avatar when there is no actual file."""
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="nofile", email="nofile@example.com",
            password="pass1234", is_approved=True, age=22
        )
        NotificationSettings.objects.get_or_create(user=self.user)
        make_min_questionnaire(self.user)
        self.client.login(username="nofile", password="pass1234")

    def test_remove_avatar_without_existing_file(self):
        mail.outbox = []
        resp = self.client.post(
            reverse("my_profile"),
            data={
                "form": "profile",
                "username": "nofile",
                "email": "nofile@example.com",
                "first_name": "",
                "last_name": "",
                "remove_avatar": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.avatar))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminPanelNewestOldestSortTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("sa", "sa@example.com", "x")
        cls.u1 = User.objects.create_user("u1", "u1@ex.com", password="x", age=20, is_approved=True)
        cls.u2 = User.objects.create_user("u2", "u2@ex.com", password="x", age=21, is_approved=True)
        cls.u3 = User.objects.create_user("u3", "u3@ex.com", password="x", age=22, is_approved=True)

    def setUp(self):
        self.client = Client()
        self.client.login(username="sa", password="x")

    def _names(self, resp):
        return list(resp.context["approved_users"].values_list("username", flat=True))

    def test_newest_oldest(self):
        r = self.client.get(reverse("admin_panel") + "?sort=newest")
        self.assertEqual(self._names(r), ["u3", "u2", "u1"])
        r = self.client.get(reverse("admin_panel") + "?sort=oldest")
        self.assertEqual(self._names(r), ["u1", "u2", "u3"])
