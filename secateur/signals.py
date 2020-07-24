from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils.timezone import now

from . import models


@receiver(user_logged_in)
def log_in_log_message(sender, user, request, **kwargs):  # type: ignore
    models.LogMessage.objects.create(
        time=now(), user=user, action=models.LogMessage.Action.LOG_IN
    )


@receiver(user_logged_out)
def log_out_log_message(sender, user, request, **kwargs):  # type: ignore
    models.LogMessage.objects.create(
        time=now(), user=user, action=models.LogMessage.Action.LOG_OUT
    )
