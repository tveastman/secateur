from enum import Enum
import logging
import random
import datetime

import secateur.models

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    RATE_LIMITED_EXCEEDED = 88
    USER_SUSPENDED = 63
    USER_NOT_FOUND = 50
    NOT_MUTING_SPECIFIED_USER = 272
    PAGE_DOES_NOT_EXIST = 34
    INVALID_OR_EXPIRED_TOKEN = 89

    @classmethod
    def from_exception(cls, twitter_error_exception):
        code = twitter_error_exception.message[0]["code"]
        try:
            return cls(code)
        except ValueError:
            return code


def fudge_duration(duration, fraction):
    """Adds a random fraction to a timedelta"""
    total_seconds = duration.total_seconds()
    max_fudge = int(total_seconds * fraction)
    return duration + datetime.timedelta(seconds=random.randint(0, max_fudge))


def pipeline_user_account_link(*args, **kwargs):
    """social auth pipeline: update secateur.models.User.account"""
    user = kwargs["user"]
    uid = kwargs["uid"]
    account = secateur.models.Account.get_account(uid)
    if user.account != account:
        user.account = account
        user.save(update_fields=("account",))
