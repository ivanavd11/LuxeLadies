from django.apps import AppConfig
from django.core.signals import request_started
from django.conf import settings

_scheduler_started = False


def _start_scheduler_once(**kwargs):
    """
    Starts APScheduler once per process and only if it is enabled.
    """
    global _scheduler_started
    if _scheduler_started or not getattr(settings, "APSCHEDULER_ENABLE", True):
        return
    from .scheduler import maybe_start_scheduler
    maybe_start_scheduler()
    _scheduler_started = True


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        from . import signals 

        if getattr(settings, "APSCHEDULER_ENABLE", True):
            request_started.connect(
                _start_scheduler_once,
                dispatch_uid="events.start_scheduler_once",
            )
