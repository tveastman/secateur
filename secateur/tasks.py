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


# These have to match the ones for the Relationship model.
# TODO: just get the model to use the same enum
class RelationshipType(enum.IntEnum):
    BLOCK = 2
    MUTE = 3


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


@app.task(bind=True)
def create_relationship(self, secateur_user_pk, type, user_id=None, screen_name=None, until=None):
    ## SANITY CHECKS
    if screen_name is None and user_id is None:
        raise ValueError("Must provide either user_id or screen_name.")

    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api
    now = timezone.now()
    type = RelationshipType(type)
    if type is RelationshipType.BLOCK:
        past_tense_verb = 'blocked'
        api_function = api.CreateBlock
    elif type is RelationshipType.MUTE:
        past_tense_verb = 'muted'
        api_function = api.CreateMute
    else:
        raise ValueError("Don't know how to handle type %r", type)

    ## CHECK IF THIS RELATIONSHIP ALREADY EXISTS
    existing_rel_qs = models.Relationship.objects.filter(
        subject=secateur_user.account,
        type=type,
    )
    if screen_name:
        existing_rel_qs = existing_rel_qs.filter(object__screen_name=screen_name)
    else:
        existing_rel_qs = existing_rel_qs.filter(object__user_id=user_id)
    updated_existing = existing_rel_qs.update(until=until)
    if updated_existing:
        logger.info(
            "%s has already %s %s.",
            secateur_user.account,
            past_tense_verb,
            user_id if user_id else screen_name
        )
        return

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
            logger.warning("Rate limit exceeded, scheduling a retry.")
            self.retry(countdown=_twitter_retry_timeout(self.request.retries))
        else:
            raise

    ## UPDATE DATABASE
    account = models.Account.get_account(api_result)
    models.Relationship.add_relationships(
        type=type, subjects=[secateur_user.account], objects=[account],
        updated=now, until=until
    )
    logger.info(
        "%s has %s %s %s",
        secateur_user,
        past_tense_verb,
        account,
        "until {}".format(until) if until else "",
    )


@app.task(bind=True)
def destroy_relationship(self, secateur_user_pk, type, user_id=None, screen_name=None):
    if screen_name is None and user_id is None:
        raise ValueError("Must provide either user_id or screen_name.")

    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api

    type = RelationshipType(type)
    if type is RelationshipType.BLOCK:
        past_tense_verb = 'unblocked'
        api_function = api.DestroyBlock
    elif type is RelationshipType.MUTE:
        past_tense_verb = 'unmuted'
        api_function = api.DestroyMute
    else:
        raise ValueError("Don't know how to handle type %r", type)

    existing_qs = models.Relationship.objects.filter(
        subject=secateur_user.account,
        type=type,
    )
    if screen_name:
        existing_qs = existing_qs.filter(object__screen_name=screen_name)
    else:
        existing_qs = existing_qs.filter(object__user_id=user_id)
    if not existing_qs:
        logger.info(
            "%s has already %s %s.",
            secateur_user.account,
            past_tense_verb,
            user_id if user_id else screen_name
        )
        return

    account = models.Account.get_account(
        api_function(
            user_id=user_id,
            screen_name=screen_name,
            include_entities=False,
            skip_status=True,
        )
    )
    models.Relationship.objects.filter(
        subject=secateur_user.account, type=type, object=account
    ).delete()
    logger.info("%s has %s %s", secateur_user, past_tense_verb, account)


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
        Q(type=models.Relationship.BLOCKS),
        subject=secateur_user.account,
        until__lt=now,
    ).select_related('object')

    for expired_block in expired_blocks[:500]:
        blocked_account = expired_block.object
        destroy_relationship.delay(
            secateur_user_pk=secateur_user.pk,
            type=2,
            user_id=blocked_account.user_id
        )
