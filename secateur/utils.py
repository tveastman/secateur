from typing import Any
from dataclasses import dataclass, replace
from enum import Enum
import logging
import random
from datetime import timedelta

import secateur.models

import twitter

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    RATE_LIMITED_EXCEEDED = 88
    USER_SUSPENDED = 63
    USER_NOT_FOUND = 50
    NOT_MUTING_SPECIFIED_USER = 272
    PAGE_DOES_NOT_EXIST = 34
    INVALID_OR_EXPIRED_TOKEN = 89

    @classmethod
    def from_exception(
        cls, twitter_error_exception: twitter.error.TwitterError
    ) -> "ErrorCode":
        code = twitter_error_exception.message[0]["code"]
        return cls(code)


def fudge_duration(duration: timedelta, fraction: float) -> timedelta:
    """Adds a random fraction to a timedelta"""
    total_seconds = duration.total_seconds()
    max_fudge = int(total_seconds * fraction)
    return duration + timedelta(seconds=random.randint(0, max_fudge))


def pipeline_user_account_link(
    *, user: "secateur.models.User", uid: int, **kwargs: Any
) -> None:
    """social auth pipeline: update secateur.models.User.account"""
    account = secateur.models.Account.get_account(uid)
    if user.account != account:
        user.account = account
        user.save(update_fields=("account",))


@dataclass(frozen=True)
class TokenBucket:
    time: float
    value: float
    rate: float
    max: float

    def value_at(self, time: float) -> float:
        time_difference = time - self.time
        value_difference = self.rate * time_difference
        return min(value_difference + self.value, self.max)

    def can_withdraw(self, time: float, amount: float) -> bool:
        return self.value_at(time) >= amount

    def withdraw(self, time: float, value: float) -> "TokenBucket":
        value_at = self.value_at(time)
        new_value = value_at - value
        if new_value < 0:
            raise ValueError(
                f"Cannot withdraw {value} at time {time}, new value would be {new_value}"
            )
        return replace(self, time=time, value=new_value)
