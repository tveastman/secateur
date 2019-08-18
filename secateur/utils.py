from enum import Enum
import random
import datetime

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
