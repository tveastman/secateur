import logging
import sys

import celery
import structlog
from celery.signals import setup_logging, worker_process_init
from django_structlog.celery.steps import DjangoStructLogInitStep

logger = structlog.get_logger(__name__)

app = celery.Celery("secateur")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.steps["worker"].add(DjangoStructLogInitStep)


@worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    import secateur.otel


@setup_logging.connect
def receiver_setup_logging(  # type: ignore
    loglevel, logfile, format, colorize, **kwargs
):  # pragma: no cover
    import secateur.logging


@app.task(bind=True)
def debug_task(self: celery.Task) -> None:
    logger.info("debug_task", self_obj=str(self), request=str(self.request))
    return
