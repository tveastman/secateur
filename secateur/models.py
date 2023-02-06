import time
import os
from functools import lru_cache
from typing import Optional, Union, Tuple, List, Iterable, Any, Dict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests
import structlog
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.indexes import BrinIndex
from django.db import models, transaction
from django.db.models import QuerySet, Q
from django.utils import timezone
from django.utils.functional import cached_property

# from psqlextra.models import PostgresModel
import psqlextra.models

import twitter

import social_django.models
from django.utils.html import format_html

from . import tasks, otel
from . import utils

logger = structlog.get_logger(__name__)


class TwitterApiDisabled(Exception):
    pass


def token_bucket_time() -> float:
    # Use "days since the epoch" as the time unit for the token bucket.
    return time.time() / 24 / 60 / 60


def default_token_bucket_rate() -> float:
    return 10_000


def default_token_bucket_max() -> float:
    return 100_000.00


def default_token_bucket_value() -> float:
    # No longer used but needed by an old migration.
    return 50_000.00


@lru_cache(maxsize=32)
def get_cached_twitter_api(**kwargs):
    api = twitter.Api(**kwargs)
    # patch the API session object to use a larger connection pool and allow a retry
    https_adapter = requests.adapters.HTTPAdapter(
        pool_connections=40, pool_maxsize=40, max_retries=1
    )
    api._session.mount("https://", https_adapter)
    return api


class User(AbstractUser):
    screen_name = models.CharField(null=True, editable=False, max_length=150)
    is_twitter_api_enabled = models.BooleanField(default=True)
    account = models.ForeignKey(
        "Account", null=True, editable=False, on_delete=models.SET_NULL
    )

    token_bucket_rate = models.FloatField(null=True, blank=True)
    token_bucket_max = models.FloatField(null=True, blank=True)
    token_bucket_time = models.FloatField(default=1)
    token_bucket_value = models.FloatField(default=default_token_bucket_max)

    oauth_token = models.CharField(
        max_length=255, null=True, blank=True, editable=False
    )
    oauth_token_secret = models.CharField(
        max_length=255, null=True, blank=True, editable=False
    )
    max_until = models.DateTimeField(null=True, editable=False)

    @property
    def token_bucket(self) -> utils.TokenBucket:
        return utils.TokenBucket(
            time=self.token_bucket_time,
            value=self.token_bucket_value,
            rate=self.token_bucket_rate
            if self.token_bucket_rate is not None
            else default_token_bucket_rate(),
            max=self.token_bucket_max
            if self.token_bucket_max is not None
            else default_token_bucket_max(),
        )

    @token_bucket.setter
    def token_bucket(self, value: utils.TokenBucket) -> None:
        self.token_bucket_time = value.time
        self.token_bucket_value = value.value

    @property
    def current_tokens(self) -> int:
        return int(self.token_bucket.value_at(token_bucket_time()))

    def withdraw_tokens(self, value: int) -> None:
        if value > self.current_tokens:
            raise ValueError("Rate limit exceeded.")
        self.token_bucket = self.token_bucket.withdraw(
            time=token_bucket_time(), value=value
        )
        otel.tokens_consumed_counter.add(value)

    @cached_property
    def twitter_social_auth(self) -> social_django.models.UserSocialAuth:
        """Get the social_auth object for this user."""
        return social_django.models.UserSocialAuth.objects.filter(
            user=self, provider="twitter"
        ).order_by("-modified")[0]

    @cached_property
    def twitter_user_id(self) -> int:
        return int(self.twitter_social_auth.uid)

    @cached_property
    def api(self) -> twitter.Api:
        if not self.is_twitter_api_enabled:
            raise TwitterApiDisabled()
        if not self.oauth_token:
            raise TwitterApiDisabled(f"User {self} oauth_token not set")
        api = get_cached_twitter_api(
            consumer_key=os.environ.get("CONSUMER_KEY"),
            consumer_secret=os.environ.get("CONSUMER_SECRET"),
            access_token_key=self.oauth_token,
            access_token_secret=self.oauth_token_secret,
            sleep_on_rate_limit=False,
        )
        return api

    def get_account_by_screen_name(self, screen_name: str) -> "Optional[Account]":
        logger.debug("Fetching user %s from Twitter API.", screen_name)
        return tasks.get_user(self.pk, screen_name=screen_name)

    def remove_unneeded_credentials(self):
        days_since_login = 28

        if self.oauth_token is None and self.oauth_token_secret is None:
            self.max_until = None
            self.save(update_fields=["max_until"])
            return

        if timezone.now() - timedelta(days=days_since_login) < self.last_login:
            return

        max_until = Relationship.objects.filter(
            subject_id=self.account_id,
            until__isnull=False,
        ).aggregate(models.Max("until"))["until__max"]

        if max_until:
            self.max_until = max_until
            self.save(update_fields=["max_until"])
            logger.info(
                "Keeping credentials at least until",
                username=self.username,
                max_until=max_until,
            )
        else:
            self.max_until = None
            self.oauth_token = None
            self.oauth_token_secret = None
            logger.info("Erasing OAuth credentials", username=self.username)
            self.save(update_fields=["max_until", "oauth_token", "oauth_token_secret"])

    @classmethod
    def remove_all_unneeded_credentials(cls):
        days_since_login = 28
        for user in cls.objects.filter(
            max_until__lt=timezone.now(),
            oauth_token__isnull=False,
            oauth_token_secret__isnull=False,
            last_login__lt=timezone.now() - timedelta(days=days_since_login),
        ):
            logger.debug(
                "Checking if we can remove credentials", username=user.username
            )
            user.remove_unneeded_credentials()


class Account(psqlextra.models.PostgresModel):
    """A Twitter account"""

    class Meta:
        indexes = (
            models.Index(fields=["screen_name"]),
            BrinIndex(fields=["profile_updated"], autosummarize=True),
        )

    user_id = models.BigIntegerField(primary_key=True, editable=False)

    profile_updated = models.DateTimeField(null=True, editable=False)

    # TWITTER PROFILE FIELDS
    screen_name = models.CharField(max_length=100, null=True, editable=False)
    name = models.CharField(max_length=200, null=True, editable=False)
    description = models.CharField(max_length=1000, null=True, editable=False)
    location = models.CharField(max_length=1000, null=True, editable=False)
    profile_image_url_https = models.CharField(
        max_length=1000, null=True, editable=False
    )
    profile_banner_url = models.CharField(max_length=1000, null=True, editable=False)
    created_at = models.DateTimeField(null=True, editable=False)
    favourites_count = models.IntegerField(null=True, editable=False)
    followers_count = models.IntegerField(null=True, editable=False)
    friends_count = models.IntegerField(null=True, editable=False)
    statuses_count = models.IntegerField(null=True, editable=False)
    listed_count = models.IntegerField(null=True, editable=False)

    def __str__(self) -> str:
        # return "{}".format(
        #    self.screen_name if self.screen_name is not None else f"id={self.user_id}"
        # )
        return f"{self.user_id}" + (
            f" ({self.screen_name})" if self.screen_name else ""
        )

    @classmethod
    def get_account(
        cls, arg: Union[int, twitter.User], now: datetime = None
    ) -> "Account":
        return cls.get_accounts(arg, now=now).get()

    @classmethod
    def get_accounts(
        cls, *args: Union[int, twitter.User], now: Optional[datetime] = None
    ) -> "QuerySet[Account]":
        """Update account objects from a result returned from the Twitter API.

        Twitter API calls either return lists of big-integer User IDs, or lists
        of instances of 'twitter.model.User' objects.

        Either way, we need to create an 'Account' object for each twitter ID
        we see, and if we see a User object we also want to update the profile
        and 'screen_name' of the Account.

        This method unmagically does the right thing with whatever you pass it.
        """
        if not args:
            return cls.objects.none()
        if now is None:
            now = timezone.now()
        rows = []
        ids = []
        if isinstance(args[0], int):
            for user_id in args:
                rows.append(dict(user_id=user_id))
            ids = args
        elif isinstance(args[0], twitter.User):
            for twitter_user in args:
                rows.append(cls.dict_from_twitter_user(twitter_user, now))
                ids.append(twitter_user.id)
        if rows:
            cls.objects.bulk_upsert(conflict_target=["user_id"], rows=rows)
        return cls.objects.filter(user_id__in=ids)

    @classmethod
    def dict_from_twitter_user(
        cls, user: twitter.User, now: Optional[datetime] = None
    ) -> dict:
        return {
            "user_id": user.id,
            "screen_name": user.screen_name,
            "name": user.name,
            "profile_updated": now,
            "description": user.description,
            "location": user.location,
            "profile_image_url_https": user.profile_image_url_https,
            "profile_banner_url": user.profile_banner_url,
            "favourites_count": user.favourites_count,
            "followers_count": user.followers_count,
            "friends_count": user.friends_count,
            "statuses_count": user.statuses_count,
            "listed_count": user.listed_count,
            "created_at": (
                parsedate_to_datetime(user.created_at) if user.created_at else None
            ),
        }

    @property
    def twitter_url(self) -> str:
        """URL for this account on twitter.com"""
        return f"https://twitter.com/i/user/{self.user_id}/"

    @property
    def blocks(self) -> "QuerySet[Account]":
        return Account.objects.filter(
            relationship_object_set__type=Relationship.BLOCKS,
            relationship_object_set__subject_id=self,
        )

    @property
    def friends(self) -> "QuerySet[Account]":
        return Account.objects.filter(
            relationship_object_set__type=Relationship.FOLLOWS,
            relationship_object_set__subject_id=self,
        )

    @property
    def followers(self) -> "QuerySet[Account]":
        return Account.objects.filter(
            relationship_subject_set__type=Relationship.FOLLOWS,
            relationship_subject_set__object_id=self,
        )

    @property
    def mutes(self) -> "QuerySet[Account]":
        return Account.objects.filter(
            relationship_object_set__type=Relationship.MUTES,
            relationship_object_set__subject_id=self,
        )

    def follows(
        self, user_id: Optional[int] = None, screen_name: Optional[str] = None
    ) -> bool:
        """Return True if self follows the user specified in either user_id or screen_name"""
        assert (
            user_id is not None or screen_name is not None
        ), "Must specify either user_id or screen_name"
        assert (
            user_id is None or screen_name is None
        ), "Must not specify both user_id and screen_name"
        if user_id is not None:
            return self.friends.filter(user_id=user_id).exists()
        else:
            return self.friends.filter(screen_name=screen_name).exists()

    def add_blocks(
        self,
        new_blocks: "Iterable[Account]",
        updated: datetime,
        until: Optional[datetime] = None,
    ) -> "QuerySet[Relationship]":
        return Relationship.add_relationships(
            subjects=[self],
            type=Relationship.BLOCKS,
            objects=new_blocks,
            updated=updated,
            until=until,
        )

    def remove_blocks_older_than(self, updated: datetime) -> int:
        return Relationship.remove_relationships(
            subject=self, type=Relationship.BLOCKS, updated__lt=updated
        )

    def add_followers(
        self, new_followers: "Iterable[Account]", updated: datetime
    ) -> "QuerySet[Relationship]":
        return Relationship.add_relationships(
            subjects=new_followers,
            type=Relationship.FOLLOWS,
            objects=[self],
            updated=updated,
        )

    def remove_followers_older_than(self, updated: datetime) -> int:
        return Relationship.remove_relationships(
            type=Relationship.FOLLOWS, object=self, updated__lt=updated
        )

    def add_friends(
        self, new_friends: "Iterable[Account]", updated: datetime
    ) -> "QuerySet[Relationship]":
        return Relationship.add_relationships(
            subjects=[self],
            type=Relationship.FOLLOWS,
            objects=new_friends,
            updated=updated,
        )

    def remove_friends_older_than(self, updated: datetime) -> int:
        return Relationship.remove_relationships(
            type=Relationship.FOLLOWS, subject=self, updated__lt=updated
        )

    def add_mutes(
        self, new_mutes: "Iterable[Account]", updated: datetime
    ) -> "QuerySet[Relationship]":
        return Relationship.add_relationships(
            subjects=[self], type=Relationship.MUTES, objects=new_mutes, updated=updated
        )

    def remove_mutes_older_than(self, updated: datetime) -> int:
        return Relationship.remove_relationships(
            subject=self, type=Relationship.MUTES, updated__lt=updated
        )


class Relationship(psqlextra.models.PostgresModel):
    class Meta:
        unique_together = (("type", "subject", "object"),)
        indexes = (
            models.Index(
                fields=["until", "subject"],
                condition=Q(until__isnull=False),
                name="until_btree",
            ),
        )

    FOLLOWS = 1
    BLOCKS = 2
    MUTES = 3

    TYPE_CHOICES = ((FOLLOWS, "follows"), (BLOCKS, "blocks"), (MUTES, "mutes"))

    subject = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        editable=False,
        related_name="relationship_subject_set",
        db_index=False,
    )
    type = models.IntegerField(choices=TYPE_CHOICES, editable=False)
    object = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        editable=False,
        related_name="relationship_object_set",
        db_index=False,
    )
    updated = models.DateTimeField(editable=False)
    until = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return "{subject} {type} {object}".format(
            subject=self.subject, type=self.get_type_display(), object=self.object
        )

    @classmethod
    def add_relationships(
        cls,
        type: int,
        subjects: Iterable[Account],
        objects: Iterable[Account],
        updated: datetime,
        until: Optional[datetime] = None,
    ) -> "QuerySet[Relationship]":
        rows = []
        for object in objects:
            for subject in subjects:
                rows.append(
                    dict(
                        type=type,
                        subject=subject,
                        object=object,
                        updated=updated,
                        until=until,
                    )
                )
        cls.objects.bulk_upsert(
            conflict_target=["type", "subject", "object"], rows=rows
        )
        result = cls.objects.filter(type=type, subject__in=subjects, object__in=objects)
        return result

    @classmethod
    def remove_relationships(cls, **kwargs: Any) -> int:
        relationships = cls.objects.filter(**kwargs)
        if relationships:
            logger.debug("Removing relationships: {}".format(relationships))
        return relationships.delete()[0]


class LogMessage(psqlextra.models.PostgresModel):
    class Meta:
        indexes = (models.Index(name="log_user_id", fields=["user", "-id"]),)

    class Action(models.IntegerChoices):
        GET_USER = 1
        CREATE_BLOCK = 2
        DESTROY_BLOCK = 3
        CREATE_MUTE = 4
        DESTROY_MUTE = 5
        GET_FOLLOWERS = 6
        GET_FRIENDS = 7
        GET_BLOCKS = 8
        GET_MUTES = 9
        MUTE_FOLLOWERS = 10
        BLOCK_FOLLOWERS = 11
        LOG_IN = 12
        LOG_OUT = 13
        DISCONNECT = 14
        UNBLOCK_EVERYBODY = 15

    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE, db_index=False)
    time = models.DateTimeField()
    action = models.IntegerField(choices=Action.choices)
    account = models.ForeignKey(
        Account, null=True, on_delete=models.SET_NULL, db_index=False
    )
    until = models.DateTimeField(null=True)
    rate_limited = models.BooleanField(null=True)

    def format_message(self) -> str:
        if self.action == self.Action.CREATE_BLOCK:
            assert self.account is not None
            return format_html(
                'blocked {} (<a href="{}">@{}</a>){}',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
                f' until {self.until.strftime("%B %d, %Y")}' if self.until else "",
            )
        elif self.rate_limited:
            return format_html(
                "Hit Twitter API rate limit, pausing operation for 15 minutes."
            )
        elif self.action == self.Action.CREATE_MUTE:
            assert self.account is not None
            return format_html(
                'muted {} (<a href="{}">@{}</a>){}',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
                f' until {self.until.strftime("%B %d, %Y")}' if self.until else "",
            )
        elif self.action == self.Action.DESTROY_MUTE:
            assert self.account is not None
            return format_html(
                'unmuted {} (<a href="{}">@{}</a>)',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
            )
        elif self.action == self.Action.DESTROY_BLOCK:
            assert self.account is not None
            return format_html(
                'unblocked {} (<a href="{}">@{}</a>)',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
            )
        elif self.action == self.Action.BLOCK_FOLLOWERS:
            assert self.account is not None
            return format_html(
                'started blocking followers of {} (<a href="{}">@{}</a>)',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
            )
        elif self.action == self.Action.MUTE_FOLLOWERS:
            assert self.account is not None
            return format_html(
                'started muting followers of {} (<a href="{}">@{}</a>)',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
            )
        elif self.action == self.Action.LOG_IN:
            return format_html("logged in")
        elif self.action == self.Action.LOG_OUT:
            return format_html("logged out")
        elif self.action == self.Action.GET_USER:
            assert self.account is not None
            return format_html(
                'retrieved profile for {} (<a href="{}">@{}</a>)',
                self.account.name,
                self.account.twitter_url,
                self.account.screen_name,
            )
        elif self.action == self.Action.UNBLOCK_EVERYBODY:
            return format_html(
                "Rescheduled all expiries to unblock everybody.",
            )
        else:
            return format_html("{}", self.action)
