from typing import Any, List, Iterable
from dataclasses import dataclass, replace
from enum import Enum
import logging
import random
from datetime import timedelta

import structlog

import secateur.models

import twitter

logger = structlog.get_logger(__name__)


class ErrorCode(Enum):
    RATE_LIMITED_EXCEEDED = 88
    USER_SUSPENDED = 63
    ACCOUNT_SUSPENDED = 64
    USER_NOT_FOUND = 50
    NOT_MUTING_SPECIFIED_USER = 272
    PAGE_DOES_NOT_EXIST = 34
    INVALID_OR_EXPIRED_TOKEN = 89

    ACCOUNT_TEMPORARILY_LOCKED = 326

    NOT_AUTHORIZED = "Not authorized."

    @classmethod
    def from_exception(
        cls, twitter_error_exception: twitter.error.TwitterError
    ) -> "ErrorCode":
        message = twitter_error_exception.message
        if isinstance(message, list):
            code = message[0]["code"]
            result = cls(code)
        elif isinstance(message, str):
            result = cls(message)
        else:
            raise ValueError(f"Didn't recognize exception {twitter_error_exception!r}")
        logger.debug("Parsed twitter exception.", message=message, result=result)
        return result


def fudge_duration(duration: timedelta, fraction: float) -> timedelta:
    """Adds a random fraction to a timedelta"""
    total_seconds = duration.total_seconds()
    max_fudge = int(total_seconds * fraction)
    return duration + timedelta(seconds=random.randint(0, max_fudge))


def pipeline_user_account_link(
    *, user: "secateur.models.User", uid: int, details: dict, **kwargs: Any
) -> None:
    """social auth pipeline: update secateur.models.User.account"""
    account = secateur.models.Account.get_account(uid)
    update_fields = []
    if user.account != account:
        user.account = account
        update_fields.append("account")
    username = details.get("username")
    if username and user.screen_name != username:
        user.screen_name = username
        update_fields.append("screen_name")
    if update_fields:
        user.save(update_fields=update_fields)


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


def chunks(iterable: Iterable[Any], size: int) -> List[Any]:
    for chunk in (iterable[i : i + size] for i in range(0, len(iterable), size)):
        yield chunk
