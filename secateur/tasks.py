"""django-q tasks"""

from functools import partial
import logging
import random
import pprint

from django.utils import timezone

from twitter.error import TwitterError

from . import models
from . import utils
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
    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api
    now = timezone.now()

    ## TODO: Grab the relationship here to lock the API call and not call if
    ## already blocked

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
    secateur_user = models.User.objects.get(pk=secateur_user_pk)
    api = secateur_user.api

    unblocked_user = self.api.DestroyBlock(
        user_id=user_id,
        screen_name=screen_name,
        include_entities=False,
        skip_status=True,
    )
    unblocked_account = Account.get_account(unblocked_user)
    Relationship.objects.filter(
        subject=self.account, type=Relationship.BLOCKS, object=unblocked_user
    ).delete()
    logger.debug("%s has unblocked %s", secateur_user, blocked_account)


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
        if utils.twitter_error_code(e) == 88:  # Rate limit exceeded
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


@app.task
def action_cuts():
    for pk in models.Cut.actionable().values_list("pk", flat=True):
        action_cut(pk)


@app.task
def action_cut(pk):
    models.Cut.action(pk)
