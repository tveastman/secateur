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
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain_console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(colors=False),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "plain_console",
                },
            },
            "loggers": {
                "django_structlog": {
                    "handlers": [
                        "console",
                    ],  # "flat_line_file", "json_file"],
                    "level": "DEBUG",
                },
                "django_celery_beat": {
                    "handlers": [
                        "console",
                    ],  # "flat_line_file", "json_file"],
                    "level": "DEBUG",
                },
                "celery": {
                    "handlers": [
                        "console",
                    ],  # "flat_line_file", "json_file"],
                    "level": "INFO",
                },
                "secateur": {
                    "handlers": [
                        "console",
                    ],  # "flat_line_file", "json_file"],
                    "level": "DEBUG",
                },
                "urllib3": {
                    "handlers": [
                        "console",
                    ],  # "flat_line_file", "json_file"],
                    "level": "DEBUG",
                },
            },
        }
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=structlog.threadlocal.wrap_dict(dict),
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@app.task(bind=True)
def debug_task(self: celery.Task) -> None:
    logger.info("debug_task", self_obj=str(self), request=str(self.request))
    return
