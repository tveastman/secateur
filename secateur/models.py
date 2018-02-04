from functools import partial, lru_cache
import logging
import datetime
import os

import twitter
from twitter import TwitterError
from django.db import models
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User as AuthUser
from django.contrib.postgres.fields import JSONField

log = logging.getLogger(__name__)


def paged_user_iterator(bound_partial_call):
    next_cursor, prev_cursor, data = bound_partial_call(cursor=-1)
    while True:
        for item in data:
            yield Twitter.get_obj(item)
        if next_cursor:
            next_cursor, prev_cursor, data = bound_partial_call(cursor=next_cursor)
        else:
            break

def user_iterator(data):
    for item in data:
        yield Twitter.get_obj(item)

def cursor_iterator(bound_partial_call):
    next_cursor, prev_cursor, data = bound_partial_call(cursor=-1)
    while True:
        yield data
        if next_cursor:
            next_cursor, prev_cursor, data = bound_partial_call(cursor=next_cursor)
        else:
            break


class User(AuthUser):
    class Meta:
        proxy = True

    @property
    @lru_cache(1)
    def twitter_social_auth(self):
        """Get the social_auth object for this user."""
        return self.social_auth.get(provider='twitter')

    @property
    @lru_cache(1)
    def twitter_user_id(self):
        return int(self.twitter_social_auth.extra_data['access_token']['user_id'])

    @property
    @lru_cache(1)
    def twitter(self):
        user_id = self.twitter_user_id
        twitter = Twitter.get_obj(user_id)
        if not twitter.profile_updated:
            api = self.api()
            twitter = self.fetch(user_id=user_id)
        return twitter

    @property
    @lru_cache(1)
    def api(self, sleep_on_rate_limit=True):
        access_token = self.twitter_social_auth.extra_data.get('access_token')
        api = twitter.Api(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token_key=access_token.get('oauth_token'),
            access_token_secret=access_token.get('oauth_token_secret'),
            sleep_on_rate_limit=sleep_on_rate_limit
        )
        return api

    def fetch(self, screen_name=None, user_id=None):
        twitter_user = self.api.GetUser(screen_name=screen_name, user_id=user_id)
        return Twitter.get_obj(twitter_user)

    def fetch_followers(self, twitter=None):
        if twitter is None:
            twitter = self.twitter
        Follower.update_list(
            partial(self.api.GetFollowerIDsPaged, user_id=twitter.user_id),
            twitter
        )
        twitter.followers_updated = timezone.now()
        twitter.save()

    def fetch_friends(self, twitter=None):
        if twitter is None:
            twitter = self.twitter
        Friend.update_list(
            partial(self.api.GetFriendIDsPaged, user_id=twitter.user_id),
            twitter
        )
        twitter.friends_updated = timezone.now()
        twitter.save()

    def fetch_blocks(self):
        Block.update_list(
            partial(self.api.GetBlocksIDsPaged),
            self.twitter
        )
        self.twitter.blocks_updated = timezone.now()
        self.twitter.save()

    def fetch_mutes(self):
        Mute.update_list(
            partial(self.api.GetMutesIDsPaged),
            self.twitter
        )
        self.twitter.mutes_updated = timezone.now()
        self.twitter.save()

    def snip(self, twitter, type, until):
        if type == Snip.MUTE:
            t = self.mute(user_id=twitter.user_id)
        elif type == Snip.BLOCK:
            t = self.block(user_id=twitter.user_id)
        else:
            raise ValueError('type must be MUTE or BLOCK')
        snip, created = Snip.objects.update_or_create(
            user=self,
            twitter=t,
            type=type,
            defaults={
                'until': until
            }
        )
        log.info(
            '%s has %s %s until %s',
            snip.user,
            'muted' if snip.type == snip.MUTE else 'blocked',
            snip.twitter, snip.until.date()
        )

    def block(self, user_id):
        qs = self.twitter.blocks.filter(user_id=user_id)
        if qs:
            t = qs.get()
            log.debug("%s already blocked by %s", t, self)
            return t
        t = Twitter.get_obj(self.api.CreateBlock(user_id=user_id))
        Block.objects.update_or_create(from_twitter=self.twitter, to_twitter=t)
        return t

    def mute(self, user_id):
        qs = self.twitter.mutes.filter(user_id=user_id)
        if qs:
            t = qs.get()
            log.debug("%s already muted by %s", t, self)
            return t
        t = Twitter.get_obj(self.api.CreateMute(user_id=user_id))
        Mute.objects.update_or_create(from_twitter=self.twitter, to_twitter=t)
        return t

    def unmute(self, twitter):
        self.twitter.mutes.remove(twitter)
        try:
            twitter = Twitter.get_obj(self.api.DestroyMute(user_id=twitter.user_id))
        except TwitterError as e:
            log.exception("An error occurred unmuting {}".format(twitter))

    def unblock(self, twitter):
        self.twitter.blocks.remove(twitter)
        try:
            twitter = Twitter.get_obj(self.api.DestroyBlock(user_id=twitter.user_id))
        except TwitterError as e:
            log.exception("An error occurred unmuting {}".format(twitter))

    def unfriend(self, twitter):
        log.debug('%s is unfriending %s', self, twitter)
        try:
            twitter = Twitter.get_obj(self.api.DestroyFriendship(user_id=twitter.user_id))
            Friend.objects.get(from_twitter=self.twitter, to_twitter=twitter).delete()
        except TwitterError as e:
            log.exception("An error occurred unfriending {}".format(twitter))

    def mute_followers_of(self, twitter, until):
        self.fetch_followers(twitter)
        for follower in twitter.followers.all():
            self.snip(follower, Snip.MUTE, until)

    def block_followers_of(self, twitter, until):
        self.fetch_followers(twitter)
        for follower in twitter.followers.all():
            self.snip(follower, Snip.BLOCK, until)


class Twitter(models.Model):
    user_id = models.BigIntegerField(primary_key=True, editable=False)
    screen_name = models.CharField(max_length=30, null=True, editable=False, db_index=True)

    profile_updated = models.DateTimeField(null=True, editable=False)

    followers = models.ManyToManyField(
        'Twitter',
        through='Follower',
        through_fields=('from_twitter', 'to_twitter'),
        related_name='followed_by'
    )
    followers_updated = models.DateTimeField(null=True, editable=False)

    friends = models.ManyToManyField(
        'Twitter',
        through='Friend',
        through_fields=('from_twitter', 'to_twitter'),
        related_name='friended_by'
    )
    friends_updated = models.DateTimeField(null=True, editable=False)

    mutes = models.ManyToManyField(
        'Twitter',
        through='Mute',
        through_fields=('from_twitter', 'to_twitter'),
        related_name='muted_by'
    )
    mutes_updated = models.DateTimeField(null=True, editable=False)

    blocks = models.ManyToManyField(
        'Twitter',
        through='Block',
        through_fields=('from_twitter', 'to_twitter'),
        related_name='blocked_by'
    )
    blocks_updated = models.DateTimeField(null=True, editable=False)

    def __str__(self):
        return self.screen_name if self.screen_name else str(self.user_id)

    class Meta:
        ordering = ['screen_name', 'user_id']

    @classmethod
    def get_obj(cls, user):
        if isinstance(user, int):
            obj, created = cls.objects.get_or_create(user_id=user)
        else:
            obj, created = cls.objects.update_or_create(user_id=user.id,
                defaults={
                    'screen_name': user.screen_name,
                    'profile_updated': timezone.now()
                }
            )
            full_profile, created = FullProfile.objects.update_or_create(
                twitter=obj,
                defaults={
                    'json': user.AsJsonString()
                }
            )
        return obj

    @classmethod
    def get_objs(cls, users):
        return [cls.get_obj(user) for user in users]

class Relationship(models.Model):
    from_twitter = models.ForeignKey(Twitter, on_delete=models.CASCADE, editable=False, related_name='+')
    to_twitter = models.ForeignKey(Twitter, on_delete=models.CASCADE, editable=False, related_name='+')
    cursor_page_number = models.IntegerField(null=True, blank=True, editable=False)

    @classmethod
    def _update_page(cls, twitter, cursor_page, cursor_page_number, reversed=False):
        """Update one page worth of relationships.

        'twitter'
        'page' is a page of data from the twitter module
        'page_number' is an integer
        """
        removal_set = set(
            cls.objects.filter(from_twitter=twitter, cursor_page_number=cursor_page_number).values_list('to_twitter__pk', flat=True)
        )
        for object in user_iterator(cursor_page):
            rel_obj, created = cls.objects.update_or_create(
                from_twitter=twitter, to_twitter=object,
                defaults = {
                    'cursor_page_number': cursor_page_number
                }
            )
            removal_set.discard(object.pk)
        log.debug('Removal set: %s', removal_set)
        cls.objects.filter(to_twitter__pk=removal_set).delete()

    @classmethod
    def update_page(cls, twitter, cursor_page, cursor_page_number, reversed=False):
        """Update one page worth of relationships.

        'twitter'
        'page' is a page of data from the twitter module
        'page_number' is an integer
        """
        current_page = {
            obj.to_twitter.pk: obj for obj in
            cls.objects.filter(from_twitter=twitter, cursor_page_number=cursor_page_number).select_related('to_twitter')
        }
        num_updated = 0
        num_created = 0
        num_removed = 0
        for object in user_iterator(cursor_page):
            created = False
            if object.pk not in current_page:
                rel_obj, created = cls.objects.update_or_create(
                    from_twitter=twitter, to_twitter=object,
                    defaults = {
                        'cursor_page_number': cursor_page_number
                    }
                )
            if created:
                num_created += 1
            else:
                num_updated += 1
            current_page.pop(object.pk, None)
        leftovers = [i.pk for i in current_page.values()]
        num_removed, _ = cls.objects.filter(id__in=leftovers).delete()
        log.debug('%s for %s page %d: %d created, %d updated, %d removed.',
            cls, twitter, cursor_page_number, num_created, num_updated, num_removed
        )

    @classmethod
    def update_list(cls, bound_api_call, twitter, reversed=False):
        for cursor_page_number, cursor_page in enumerate(cursor_iterator(bound_api_call)):
            cls.update_page(twitter, cursor_page, cursor_page_number, reversed=False)

    class Meta:
        abstract = True

class Block(Relationship):
    pass

class Follower(Relationship):
    pass

class Mute(Relationship):
    pass

class Friend(Relationship):
    pass

class FullProfile(models.Model):
    twitter = models.OneToOneField('Twitter', on_delete=models.CASCADE)
    json = JSONField(null=True, blank=True, editable=False)

class Snip(models.Model):
    MUTE = 1
    BLOCK = 2
    TYPE_CHOICES = (
        (MUTE, 'Mute'),
        (BLOCK, 'Block')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    twitter = models.ForeignKey(Twitter, on_delete=models.CASCADE)
    type = models.IntegerField(choices=TYPE_CHOICES)
    until = models.DateTimeField(db_index=True)

    def unsnip(self):
        if self.type == Snip.MUTE:
            self.user.unmute(self.twitter)
        elif self.type == Snip.BLOCK:
            self.user.unblock(self.twitter)
        self.delete()
        log.info(
            '%s %s by %s',
            self.twitter,
            'unmuted' if self.type == self.MUTE else 'unblocked',
            self.user
        )

    @classmethod
    def expire_all(cls):
        for snip in cls.objects.filter(until__lt=timezone.now()):
            snip.unsnip()

    class Meta:
        unique_together = (
            ('user', 'twitter', 'type')
        )
