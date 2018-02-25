"""django-q tasks"""

from functools import partial
from django.utils import timezone

from django_q.tasks import async, schedule
from twitter.error import TwitterError

from . import models
from . import utils

def twitter_update_account(secateur_user, user_id=None, screen_name=None):
    secateur_user.refresh_from_db()
    api = secateur_user.api

    twitter_user = api.GetUser(user_id=user_id, screen_name=screen_name)

    return models.Account.get_account(twitter_user)

def twitter_paged_call_iterator(api_function, accounts_handler, finish_handler, cursor=-1, max_pages=20):
    try:
        next_cursor, previous_cursor, data = api_function(cursor=cursor)
    except TwitterError as e:
        if e.message == [{'code': 88, 'message': 'Rate limit exceeded'}]:
            schedule(
                'secateur.tasks.twitter_paged_call_iterator',
                api_function=api_function, accounts_handler=accounts_handler,
                finish_handler=finish_handler, cursor=cursor, max_pages=max_pages,
                schedule_type='O', repeats=0,
                next_run=timezone.now() + timezone.timedelta(seconds=60 * 15)
            )
            return
    accounts = models.Account.get_accounts(*data)
    accounts_handler(accounts)
    if next_cursor and max_pages:
        async(
            twitter_paged_call_iterator, api_function,
            accounts_handler, finish_handler, cursor=next_cursor, max_pages=max_pages - 1
        )
    if not next_cursor:
        # We only run the finish_handler if we actually made it to the end of the list.
        # The consequence of this is that if a list is longer than our max_pages, then
        # we'll end up never removing people from it.
        finish_handler()

def twitter_update_followers(secateur_user, account=None):
    now = timezone.now()
    api = secateur_user.api
    if account is None:
        account = secateur_user.account

    api_function = partial(api.GetFollowerIDsPaged, user_id=account.user_id)
    accounts_handler = partial(account.add_followers, updated=now)
    finish_handler = partial(account.remove_followers_older_than, now)
    async(twitter_paged_call_iterator, api_function, accounts_handler, finish_handler)

def twitter_update_friends(secateur_user, account=None):
    now = timezone.now()
    api = secateur_user.api
    if account is None:
        account = secateur_user.account

    api_function = partial(api.GetFriendIDsPaged, user_id=account.user_id)
    accounts_handler = partial(account.add_friends, updated=now)
    finish_handler = partial(account.remove_friends_older_than, now)
    async(twitter_paged_call_iterator, api_function, accounts_handler, finish_handler)

def twitter_update_blocks(secateur_user):
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account

    api_function = partial(api.GetBlocksIDsPaged)
    accounts_handler = partial(account.add_blocks, updated=now)
    finish_handler = partial(account.remove_blocks_older_than, now)
    async(twitter_paged_call_iterator, api_function, accounts_handler, finish_handler)

def twitter_update_mutes(secateur_user):
    now = timezone.now()
    api = secateur_user.api
    account = secateur_user.account

    api_function = partial(api.GetMutesIDsPaged)
    accounts_handler = partial(account.add_mutes, updated=now)
    finish_handler = partial(account.remove_mutes_older_than, now)
    async(twitter_paged_call_iterator, api_function, accounts_handler, finish_handler)
