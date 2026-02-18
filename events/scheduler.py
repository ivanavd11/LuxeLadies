import os
from django.conf import settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django_apscheduler.models import DjangoJobExecution

_scheduler = None 

def delete_old_job_executions(max_age=60 * 60 * 24):
    """
    Cleaning up old performance recordings.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)

def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), "default")

    scheduler.add_job(
        func="events.jobs:send_event_reminders_job",
        trigger=IntervalTrigger(minutes=5),
        id="send_event_reminders_job",
        name="Изпраща напомняния (5 дни / 1 ден / 1 час) за предстоящи събития",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        func="events.scheduler:delete_old_job_executions",
        trigger=IntervalTrigger(hours=24),
        id="cleanup_job_executions",
        name="Почиства стари записи на job изпълненията",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    register_events(scheduler)
    scheduler.start()
    _scheduler = scheduler
    return _scheduler

def maybe_start_scheduler():
    if settings.DEBUG:
        if os.environ.get("RUN_MAIN") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            start_scheduler()
    else:
        start_scheduler()