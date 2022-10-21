import logging.config
import structlog

# TODO: Make this configurable.
use_console_renderer = True

timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")
pre_chain = [
    # Add the log level and a timestamp to the event_dict if the log entry
    # is not from structlog.
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    # Add extra attributes of LogRecord objects to the event dictionary
    # so that values passed in the extra parameter of log methods pass
    # through to log output.
    structlog.stdlib.ExtraAdder(),
    timestamper,
]


def extract_from_record(_, __, event_dict):
    """
    Extract thread and process names and add them to the event dict.
    """
    record = event_dict["_record"]
    event_dict["thread_name"] = record.threadName
    event_dict["process_name"] = record.processName

    return event_dict


logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.dev.ConsoleRenderer()
                    if use_console_renderer
                    else structlog.processors.JSONRenderer(),
                ],
                "foreign_pre_chain": pre_chain,
            },
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "plain",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": "DEBUG",
                "propagate": True,
            },
            # Squelch the noisy ones, but I might miss useful info when debugging.
            "celery": {"level": "WARNING"},
            "django_structlog": {"level": "WARNING"},
            "django": {"level": "INFO", "propagate": True},
            "requests_oauthlib": {"level": "INFO"},
            "urllib3": {"level": "INFO"},
            "oauthlib": {"level": "INFO"},
            "botocore": {"level": "INFO"},
            "opentelemetry": {"level": "INFO"},
        },
    }
)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
