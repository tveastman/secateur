"""django-q tasks"""

from functools import partial
import logging
import random
import pprint
import enum

from django.utils import timezone
from django.db.models import Q

from twitter.error import TwitterError
from .utils import ErrorCode

from . import models
from .celery import app

logger = logging.getLogger(__name__)


def _twitter_retry_timeout(retries=0):
    # Wait 15 minutes, plus a randomised exponential backoff in 15 minute chunks
    base = 15 * 60
    exponential_backoff = (2 ** retries) * 15 * 60
    return base + random.randint(0, exponential_backoff)


@app.task
def get_user(secateur_user_pk, user_id=None, screen_name=None):
    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api

    twitter_user = api.GetUser(
        user_id=user_id, screen_name=screen_name, include_entities=False
    )
    account = models.Account.get_account(twitter_user)


@app.task
def block(secateur_user_pk, user_id=None, screen_name=None, until=None):
    if screen_name is None and user_id is None:
        raise ValueError("Must provide either user_id or screen_name.")
    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api
    now = timezone.now()

    existing_block_qs = models.Relationship.objects.filter(
        subject=secateur_user.account,
        type=models.Relationship.BLOCKS,
    )
    if screen_name:
        existing_block_qs = existing_block_qs.filter(object__screen_name=screen_name)
    else:
        existing_block_qs = existing_block_qs.filter(object__user_id=user_id)
    updated_existing = existing_block_qs.update(until=until)
    if updated_existing:
        logger.info(
            "%s has already blocked %s.",
            secateur_user.account,
            user_id if user_id else screen_name
        )
        return

    blocked_user = api.CreateBlock(
        user_id=user_id,
        screen_name=screen_name,
        include_entities=False,
        skip_status=True,
    )
    logger.debug("Return from API: %r", blocked_user)
    blocked_account = models.Account.get_account(blocked_user)
    secateur_user.account.add_blocks([blocked_account], updated=now, until=until)
    logger.info(
        "%s has blocked %s %s",
        secateur_user,
        blocked_account,
        "until {}".format(until) if until else "",
    )


@app.task
def unblock(secateur_user_pk, user_id=None, screen_name=None):
    if screen_name is None and user_id is None:
        raise ValueError("Must provide either user_id or screen_name.")

    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api

    existing_block_qs = models.Relationship.objects.filter(
        subject=secateur_user.account,
        type=models.Relationship.BLOCKS,
    )
    if screen_name:
        existing_block_qs = existing_block_qs.filter(object__screen_name=screen_name)
    else:
        existing_block_qs = existing_block_qs.filter(object__user_id=user_id)
    if not existing_block_qs:
        logger.info(
            "%s has not blocked %s.",
            secateur_user.account,
            user_id if user_id else screen_name
        )
        return

    unblocked_account = models.Account.get_account(
        api.DestroyBlock(
            user_id=user_id,
            screen_name=screen_name,
            include_entities=False,
            skip_status=True,
        )
    )
    models.Relationship.objects.filter(
        subject=secateur_user.account, type=models.Relationship.BLOCKS, object=unblocked_account
    ).delete()
    logger.info("%s has unblocked %s", secateur_user, unblocked_account)


@app.task(bind=True)
def twitter_paged_call_iterator(
    self, api_function, accounts_handlers, finish_handlers, cursor=-1, max_pages=100
):
    try:
        logger.debug("Calling %r with cursor page %r", api_function, cursor)
        next_cursor, previous_cursor, data = api_function(cursor=cursor)
        if data:
            logger.debug("Received %r results", len(data))
    except TwitterError as e:
        if ErrorCode.from_exception(e) == ErrorCode.RATE_LIMITED_EXCEEDED:
            logger.warning("Rate limit exceeded, scheduling a retry.")
            self.retry(countdown=_twitter_retry_timeout(self.request.retries))
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
        )
    if not next_cursor:
        # We only run the finish_handler if we actually made it to the end of the list.
        # The consequence of this is that if a list is longer than our max_pages, then
        # we'll end up never removing people from it.
        for finish_handler in finish_handlers:
            finish_handler()


def twitter_update_followers(secateur_user, account=None):
    """Trigger django-q tasks to update the followers list of a twitter account.

    If the account is unspecified, it'll update the followers list of the user.
    """
    now = timezone.now()
    api = secateur_user.api
    if account is None:
        account = secateur_user.account

    api_function = partial(api.GetFollowerIDsPaged, user_id=account.user_id)
    accounts_handlers = [partial(account.add_followers, updated=now)]
    finish_handlers = [partial(account.remove_followers_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def twitter_update_friends(secateur_user, account=None):
    """Trigger django-q tasks to update the friends list of a twitter account.

    If the account is unspecified, it'll update the friends list of the user.
    """
    now = timezone.now()
    api = secateur_user.api
    if account is None:
        account = secateur_user.account

    api_function = partial(api.GetFriendIDsPaged, user_id=account.user_id)
    accounts_handlers = [partial(account.add_friends, updated=now)]
    finish_handlers = [partial(account.remove_friends_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def twitter_update_blocks(secateur_user):
    """Trigger django-q tasks to update the block list of a secateur user."""
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account

    api_function = partial(api.GetBlocksIDsPaged)
    accounts_handlers = [partial(account.add_blocks, updated=now)]
    finish_handlers = [partial(account.remove_blocks_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def twitter_update_mutes(secateur_user):
    """Trigger django-q tasks to update the mute list of a secateur user."""
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account

    api_function = partial(api.GetMutesIDsPaged)
    accounts_handlers = [partial(account.add_mutes, updated=now)]
    finish_handlers = [partial(account.remove_mutes_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)

# Used as a partial() in twitter_block_followers()
def _block_multiple(accounts, secateur_user_pk, until):
    for account in accounts:
        block.delay(
            secateur_user_pk=secateur_user_pk, user_id=account.user_id, until=until
        )


def twitter_block_followers(secateur_user, account, until):
    api = secateur_user.api
    now = timezone.now()

    api_function = partial(api.GetFollowerIDsPaged, user_id=account.user_id)
    accounts_handlers = [
        partial(account.add_followers, updated=now),
        partial(_block_multiple, secateur_user_pk=secateur_user.pk, until=until),
    ]
    finish_handlers = [partial(account.remove_followers_older_than, now)]
    twitter_paged_call_iterator.delay(api_function, accounts_handlers, finish_handlers)


def unblock_expired(secateur_user, now=None):
    if now is None:
        now = timezone.now()

    expired_blocks = models.Relationship.objects.filter(
        subject=secateur_user.account,
        type=models.Relationship.BLOCKS,
        until__lt=now
    ).select_related('object')

    for expired_block in expired_blocks[:500]:
        blocked_account = expired_block.object
        unblock.delay(
            secateur_user_pk=secateur_user.pk,
            user_id=blocked_account.user_id
        )
