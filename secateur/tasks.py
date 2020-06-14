"""django-q tasks"""

import datetime
import enum
import logging
import random
from functools import partial
from typing import Optional, Callable, List, Iterable

import celery
from django.db import transaction
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from twitter.error import TwitterError

from . import models
from .celery import app
from .utils import ErrorCode, fudge_duration

logger = logging.getLogger(__name__)


# These have to match the ones for the Relationship model.
# TODO: just get the model to use the same enum
class RelationshipType(enum.IntEnum):
    BLOCK = 2
    MUTE = 3


def _twitter_retry_timeout(base: int = 900, retries: int = 0) -> int:
    """
    Twitter calculates all its rate limiting in 15 minute blocks. If we
    hit a rate limit we need to wait at least till the next 15 minute block.

    We use an exponential backoff to choose a 15 minute 'slot' in which to
    schedule our retry.
    """
    # Pick a slot using binary exponential backoff.
    # We limit slots to sometime in the next 23 hours so we don't fall afowl
    # of redis' visibility_timeout. If we use rabbitmq we can get rid of this
    # cap.
    max_slot = min(2 ** retries - 1, 23 * 4)
    slot = random.randint(0, max_slot)
    # Each slot is a 15 minute window, pick a random second within
    # that 15 minute window.
    seconds = random.randint(slot * 15 * 60, (slot + 1) * 15 * 60)
    timeout = base + seconds
    logger.debug(
        "retry timeout: base=%r retries=%r, slot=%r, seconds=%r timeout=%r",
        base,
        retries,
        slot,
        seconds,
        timeout,
    )
    return timeout


@app.task
def get_user(
    secateur_user_pk: int, user_id: int = None, screen_name: str = None
) -> "Optional[models.Account]":
    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api
    try:
        twitter_user = api.GetUser(
            user_id=user_id, screen_name=screen_name, include_entities=False
        )
    except TwitterError as e:
        if ErrorCode.from_exception(e) == ErrorCode.USER_SUSPENDED:
            return None
        elif ErrorCode.from_exception(e) == ErrorCode.USER_NOT_FOUND:
            return None
        else:
            raise
    account = models.Account.get_account(twitter_user)
    models.LogMessage.objects.create(
        user=secateur_user,
        time=timezone.now(),
        message="Retrieved profile for {}".format(account),
        account=account,
        action=models.LogMessage.Action.GET_USER,
    )
    return account


@app.task(bind=True, max_retries=15, ignore_result=True)
@transaction.atomic
def create_relationship(
    self: celery.Task,
    secateur_user_pk: int,
    type: RelationshipType,
    user_id: Optional[int] = None,
    screen_name: Optional[str] = None,
    until: Optional[datetime.datetime] = None,
) -> None:
    ## SANITY CHECKS
    if screen_name is None and user_id is None:
        raise ValueError("Must provide either user_id or screen_name.")

    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    try:
        api = secateur_user.api
    except models.TwitterApiDisabled:
        logger.error("Twitter API not enabled for user: %s", secateur_user)
        return
    now = timezone.now()
    type = RelationshipType(type)

    if type is RelationshipType.BLOCK:
        action = models.LogMessage.Action.CREATE_BLOCK
        past_tense_verb = "blocked"
        api_function = api.CreateBlock
        rate_limit_key = "{}:{}:rate-limit".format(
            secateur_user.username, "create_block"
        )
    elif type is RelationshipType.MUTE:
        action = models.LogMessage.Action.CREATE_MUTE
        past_tense_verb = "muted"
        api_function = api.CreateMute
        rate_limit_key = "{}:{}:rate-limit".format(
            secateur_user.username, "create_mute"
        )
    else:
        raise ValueError("Don't know how to handle type %r", type)

    ## CHECK IF THIS RELATIONSHIP ALREADY EXISTS
    existing_rel_qs = models.Relationship.objects.filter(
        subject=secateur_user.account, type=type
    )
    if screen_name:
        existing_rel_qs = existing_rel_qs.filter(object__screen_name=screen_name)
    else:
        assert user_id is not None
        existing_rel_qs = existing_rel_qs.filter(object__user_id=user_id)
    updated_existing = existing_rel_qs.update(until=until)
    if updated_existing:
        logger.info(
            "%s has already %s %s.",
            secateur_user.account,
            past_tense_verb,
            existing_rel_qs.get().object,
        )
        return

    assert secateur_user.account is not None
    if secateur_user.account.follows(user_id=user_id, screen_name=screen_name):
        logger.info(
            "%s follows %s and so %s won't be %s.",
            secateur_user.account,
            user_id,
            user_id,
            past_tense_verb,
        )
        return

    ## CHECK CACHED RATE LIMIT
    rate_limited = cache.get(rate_limit_key)
    if rate_limited:
        time_remaining = (rate_limited - now).total_seconds()
        logger.debug(
            "Locally cached rate limit exceeded (%s seconds remaining)", time_remaining
        )
        self.retry(
            countdown=_twitter_retry_timeout(
                base=time_remaining + 5, retries=self.request.retries
            )
        )

    ## CALL THE TWITTER API
    try:
        api_result = api_function(
            user_id=user_id,
            screen_name=screen_name,
            include_entities=False,
            skip_status=True,
        )
    except TwitterError as e:
        if ErrorCode.from_exception(e) == ErrorCode.RATE_LIMITED_EXCEEDED:
            logger.warning("API rate limit exceeded.")
            cache.set(
                rate_limit_key, now + datetime.timedelta(seconds=15 * 60), 15 * 60
            )
            models.LogMessage.objects.create(
                user=secateur_user,
                message="Rate limited: resuming in 15 minutes.",
                action=action,
                rate_limited=True,
                time=now,
            )
            self.retry(countdown=_twitter_retry_timeout(retries=self.request.retries))
        else:
            raise

    ## UPDATE DATABASE
    account = models.Account.get_account(api_result)
    models.Relationship.add_relationships(
        type=type,
        subjects=[secateur_user.account],
        objects=[account],
        updated=now,
        until=until,
    )
    log_message = "{} {}{}".format(
        past_tense_verb,
        account,
        " until {}".format(until.strftime("%-d %B")) if until else "",
    )
    models.LogMessage.objects.create(
        user=secateur_user,
        time=now,
        message=log_message,
        action=action,
        account=account,
        until=until,
    )
    logger.info("%s has %s", secateur_user, log_message)


@app.task(bind=True, max_retries=15, rate_limit=5, ignore_result=True, priority=8)
@transaction.atomic
def destroy_relationship(
    self: celery.Task,
    secateur_user_pk: int,
    type: int,
    user_id: Optional[int] = None,
    screen_name: Optional[str] = None,
) -> None:
    if screen_name is None and user_id is None:
        raise ValueError("Must provide either user_id or screen_name.")

    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    try:
        api = secateur_user.api
    except models.TwitterApiDisabled:
        logger.error("Twitter API not enabled for user: %s", secateur_user)
        return
    now = timezone.now()

    type = RelationshipType(type)
    if type is RelationshipType.BLOCK:
        past_tense_verb = "unblocked"
        api_function = api.DestroyBlock
        rate_limit_key = "{}:{}:rate-limit".format(
            secateur_user.username, "destroy_block"
        )
        action = models.LogMessage.Action.DESTROY_BLOCK

    elif type is RelationshipType.MUTE:
        past_tense_verb = "unmuted"
        api_function = api.DestroyMute
        rate_limit_key = "{}:{}:rate-limit".format(
            secateur_user.username, "destroy_mute"
        )
        action = models.LogMessage.Action.DESTROY_MUTE
    else:
        raise ValueError("Don't know how to handle type %r", type)

    existing_qs = models.Relationship.objects.filter(
        subject=secateur_user.account, type=type
    )
    if screen_name:
        existing_qs = existing_qs.filter(object__screen_name=screen_name)
    else:
        assert user_id is not None
        existing_qs = existing_qs.filter(object__user_id=user_id)
    if not existing_qs:
        logger.info(
            "%s has already %s %s.",
            secateur_user.account,
            past_tense_verb,
            user_id if user_id else screen_name,
        )
        return

    rate_limited = cache.get(rate_limit_key)
    if rate_limited:
        time_remaining = (rate_limited - now).total_seconds()
        logger.debug("Locally cached rate limit exceeded ('%s')", rate_limited)
        self.retry(
            countdown=_twitter_retry_timeout(
                base=time_remaining, retries=self.request.retries
            )
        )

    ## CALL THE TWITTER API
    try:
        account = models.Account.get_account(
            api_function(
                user_id=user_id,
                screen_name=screen_name,
                include_entities=False,
                skip_status=True,
            )
        )
    except TwitterError as e:
        code = ErrorCode.from_exception(e)
        if code is ErrorCode.RATE_LIMITED_EXCEEDED:
            logger.warning("API rate limit exceeded.")
            wait = 15 * 60
            cache.set(rate_limit_key, now + datetime.timedelta(seconds=wait), wait)
            self.retry(countdown=_twitter_retry_timeout(retries=self.request.retries))
        elif code is ErrorCode.NOT_MUTING_SPECIFIED_USER:
            logger.warning("API: not muting specified user, removing relationship.")
            existing_qs.delete()
            return
        elif code is ErrorCode.PAGE_DOES_NOT_EXIST:
            # This error shows up when trying to unblock an account that's been deleted.
            # So we'll remove the account entirely.
            logger.warning("API: Page does not exist (user deleted?)")
            # This deletion cascades to the relationship and the profile.
            # TODO: Don't delete the account object, instead mark it as deleted.
            # existing_qs.get().object.delete()
            # return
            account = existing_qs.get().object
            pass
        else:
            raise

    models.Relationship.objects.filter(
        subject=secateur_user.account, type=type, object=account
    ).delete()
    log_message = "{} {}".format(past_tense_verb, account)
    models.LogMessage.objects.create(
        user=secateur_user,
        time=now,
        message=log_message,
        action=action,
        until=None,
        account=account,
    )
    logger.info("%s has %s", secateur_user, log_message)


@app.task(bind=True, ignore_result=True)
def twitter_paged_call_iterator(
    self: celery.Task,
    api_function: Callable,
    # It's a list of callables, where each callable takes a single argument which is
    # an iterable of Account objects, and it returns None
    accounts_handlers: "List[Callable[[Iterable[models.Account]], None]]",
    # It's a list of callables that take no arguments and return no result
    finish_handlers: "List[Callable[[], None]]",
    cursor: int = -1,
    max_pages: int = 100,
    current_page: int = 1,
) -> None:
    try:
        logger.debug("Calling %r with cursor page %r", api_function, cursor)
        next_cursor, previous_cursor, data = api_function(cursor=cursor)
        if data:
            logger.debug("Received %r results", len(data))
    except TwitterError as e:
        if ErrorCode.from_exception(e) == ErrorCode.RATE_LIMITED_EXCEEDED:
            logger.warning("Rate limit exceeded, scheduling a retry.")
            self.retry(
                countdown=_twitter_retry_timeout(base=900, retries=self.request.retries)
            )
        else:
            raise

    accounts = models.Account.get_accounts(*data)
    for accounts_handler in accounts_handlers:
        accounts_handler(accounts)
    if next_cursor and max_pages:
        twitter_paged_call_iterator.delay(
            api_function,
            accounts_handlers,
            finish_handlers,
            cursor=next_cursor,
            max_pages=max_pages - 1,
            current_page=current_page + 1,
        )
    if not next_cursor:
        # We only run the finish_handler if we actually made it to the end of the list.
        # The consequence of this is that if a list is longer than our max_pages, then
        # we'll end up never removing people from it.
        for finish_handler in finish_handlers:
            finish_handler()


def twitter_update_followers(
    secateur_user: "models.User", account: "Optional[models.Account]" = None
) -> None:
    """Trigger django-q tasks to update the followers list of a twitter account.

    If the account is unspecified, it'll update the followers list of the user.
    """
    now = timezone.now()
    api = secateur_user.api

    if account is None:
        account = secateur_user.account

    assert account is not None
    api_function = partial(api.GetFollowerIDsPaged, user_id=account.user_id)
    accounts_handlers = [partial(account.add_followers, updated=now)]
    finish_handlers = [partial(account.remove_followers_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def twitter_update_friends(
    secateur_user: "models.User",
    account: "Optional[models.Account]" = None,
    get_profiles: bool = False,
) -> None:
    """Trigger django-q tasks to update the friends list of a twitter account.

    If the account is unspecified, it'll update the friends list of the user.
    """
    now = timezone.now()
    api = secateur_user.api
    if account is None:
        account = secateur_user.account
    assert account is not None

    if get_profiles:
        api_function = partial(api.GetFriendsPaged, user_id=account.user_id)
    else:
        api_function = partial(api.GetFriendIDsPaged, user_id=account.user_id)
    accounts_handlers = [partial(account.add_friends, updated=now)]
    finish_handlers = [partial(account.remove_friends_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def twitter_update_blocks(secateur_user: "models.User") -> None:
    """Trigger django-q tasks to update the block list of a secateur user."""
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account
    assert account is not None

    api_function = partial(api.GetBlocksIDsPaged)
    accounts_handlers = [partial(account.add_blocks, updated=now)]
    finish_handlers = [partial(account.remove_blocks_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def twitter_update_mutes(secateur_user: "models.User") -> None:
    """Trigger django-q tasks to update the mute list of a secateur user."""
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account
    assert account is not None

    api_function = partial(api.GetMutesIDsPaged)
    accounts_handlers = [partial(account.add_mutes, updated=now)]
    finish_handlers = [partial(account.remove_mutes_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


# Used as a partial() in twitter_block_followers()
def _block_multiple(
    accounts: "Iterable[models.Account]",
    type: int,
    secateur_user_pk: int,
    duration: datetime.timedelta,
) -> None:
    for i, account in enumerate(accounts):
        until: Optional[datetime.datetime]
        if duration:
            # Add a random 5% component to the block duration.
            fudged_duration = fudge_duration(duration, 0.05)
            until = timezone.now() + fudged_duration
        else:
            until = None
        create_relationship.apply_async(
            [],
            {
                "secateur_user_pk": secateur_user_pk,
                "type": type,
                "user_id": account.user_id,
                "until": until,
            },
            # I can't decide if there should be a timeout here. Probably what ought
            # to happen instead is that blocks are handled by a different celery
            # queue, so they can start right away and not block paged_iterator tasks.
            # countdown=1 + int(i * (60 * 15 / 5000)),
            max_retries=20,
            priority=random.randint(1, 9),
        )


def twitter_block_followers(
    secateur_user: "models.User",
    type: int,
    account: "models.Account",
    duration: Optional[datetime.timedelta],
) -> None:
    api = secateur_user.api
    now = timezone.now()

    api_function = partial(api.GetFollowerIDsPaged, user_id=account.user_id)
    accounts_handlers = [
        # I'm removing the task of updating the relationship table to track the followers.
        # This should save IO and I'm not using this data for anything.
        # partial(account.add_followers, updated=now),
        partial(
            _block_multiple,
            type=type,
            secateur_user_pk=secateur_user.pk,
            duration=duration,
        ),
    ]
    finish_handlers = [
        # partial(account.remove_followers_older_than, now)
    ]
    models.LogMessage.objects.create(
        user=secateur_user,
        time=now,
        action=(
            models.LogMessage.Action.BLOCK_FOLLOWERS
            if type == models.Relationship.BLOCKS
            else models.LogMessage.Action.MUTE_FOLLOWERS
        ),
        account=account,
        until=now + duration if duration else None,
        message=None,
    )
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


@app.task(priority=9)
def unblock_expired(now: Optional[datetime.datetime] = None) -> None:
    if now is None:
        now = timezone.now()

        expired_blocks = (
            models.Relationship.objects.filter(
                Q(type=models.Relationship.BLOCKS) | Q(type=models.Relationship.MUTES),
                until__lt=now,
                subject__user__is_twitter_api_enabled=True,
            )
            .select_related("object", "subject")
            .prefetch_related("subject__user_set")
        )

        for expired_block in expired_blocks.iterator():
            secateur_user = expired_block.subject.user_set.get()
            blocked_account = expired_block.object
            destroy_relationship.apply_async(
                [],
                {
                    "secateur_user_pk": secateur_user.pk,
                    "type": expired_block.type,
                    "user_id": blocked_account.user_id,
                },
                countdown=random.randint(1, 60 * 60),
                max_retries=15,
            )


def update_user_details(secateur_user: "models.User") -> None:
    """Update the details of a secateur user.

    Fetches a user's friends, blocks and mutes lists, and
    their own twitter profile.
    """
    account = secateur_user.account
    assert account is not None

    get_user.delay(secateur_user.pk, user_id=account.pk).forget()

    ## I'm not convinced I need to update these, and any secateur user
    ## might have a lot of them.
    twitter_update_mutes(secateur_user)
    twitter_update_blocks(secateur_user)

    ## Definitely need this one.
    twitter_update_friends(secateur_user)
    ## TODO: Add twitter list support.


@app.task
def remove_unneeded_credentials() -> None:
    models.User.remove_unneeded_credentials()
