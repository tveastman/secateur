"""django-q tasks"""

from functools import partial
import logging
import random

from django.utils import timezone
from django_q.tasks import async, schedule

from twitter.error import TwitterError

from . import models
from . import utils

logger = logging.getLogger(__name__)


def twitter_update_account(secateur_user, user_id=None, screen_name=None):
    secateur_user.refresh_from_db()
    api = secateur_user.api

    logger.info('Twitter API: Calling GetUser(user_id=%r, screen_name=%r)', user_id, screen_name)
    twitter_user = api.GetUser(user_id=user_id, screen_name=screen_name)

    return models.Account.get_account(twitter_user)

def twitter_paged_call_iterator(api_function, accounts_handlers, finish_handlers, cursor=-1, max_pages=20):
    try:
        next_cursor, previous_cursor, data = api_function(cursor=cursor)
    except TwitterError as e:
        if e.message == [{'code': 88, 'message': 'Rate limit exceeded'}]:
            schedule(
                'secateur.tasks.twitter_paged_call_iterator',
                api_function=api_function, accounts_handlers=accounts_handlers,
                finish_handlers=finish_handlers, cursor=cursor, max_pages=max_pages,
                schedule_type='O', repeats=0,
                next_run=timezone.now() + timezone.timedelta(seconds=60 * 15)
            )
            return
        else:
            raise
    accounts = models.Account.get_accounts(*data)
    for accounts_handler in accounts_handlers:
        accounts_handler(accounts)
    if next_cursor and max_pages:
        async(
            twitter_paged_call_iterator, api_function,
            accounts_handlers, finish_handlers, cursor=next_cursor, max_pages=max_pages - 1
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
    async(twitter_paged_call_iterator, api_function, accounts_handlers, finish_handlers)

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
    async(twitter_paged_call_iterator, api_function, accounts_handlers, finish_handlers)

def twitter_update_blocks(secateur_user):
    """Trigger django-q tasks to update the block list of a secateur user."""
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account

    api_function = partial(api.GetBlocksIDsPaged)
    accounts_handlers = [partial(account.add_blocks, updated=now)]
    finish_handlers = [partial(account.remove_blocks_older_than, now)]
    async(twitter_paged_call_iterator, api_function, accounts_handlers, finish_handlers)

def twitter_update_mutes(secateur_user):
    """Trigger django-q tasks to update the mute list of a secateur user."""
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account

    api_function = partial(api.GetMutesIDsPaged)
    accounts_handlers = [partial(account.add_mutes, updated=now)]
    finish_handlers = [partial(account.remove_mutes_older_than, now)]
    async(twitter_paged_call_iterator, api_function, accounts_handlers, finish_handlers)

def twitter_cut_followers(secateur_user, account, type, duration=None, now=None):
    if now is None:
        now = timezone.now()
    api = secateur_user.api

    api_function = partial(api.GetFollowerIDsPaged, user_id=account.user_id)
    accounts_handlers = [
        partial(account.add_followers, updated=now),
        partial(
            secateur_user.cut,
            type=type, duration=duration, now=now, action=True
        )
    ]
    finish_handlers = [partial(account.remove_followers_older_than, now)]
    async(twitter_paged_call_iterator, api_function, accounts_handlers, finish_handlers)


def action_cuts():
    for pk in models.Cut.actionable().values_list('pk', flat=True):
        action_cut(pk)

def action_cut(pk):
    async(models.Cut.action, pk)
