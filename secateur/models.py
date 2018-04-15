import os
import logging
import random

logging.basicConfig(level=logging.DEBUG)

from django.contrib.auth.models import User as AuthUser
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from django.utils.functional import cached_property
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.db.models import F

import twitter

from . import tasks
from .utils import twitter_error_code


logger = logging.getLogger(__name__)


class User(AuthUser):
    """A Secateur User"""
    class Meta:
        proxy = True

    @cached_property
    def twitter_social_auth(self):
        """Get the social_auth object for this user."""
        return self.social_auth.get(provider='twitter')

    @cached_property
    def twitter_user_id(self):
        return int(self.twitter_social_auth.extra_data['access_token']['user_id'])

    @cached_property
    def account(self):
        user_id = self.twitter_user_id
        return Account.get_account(user_id)

    @cached_property
    def api(self):
        access_token = self.twitter_social_auth.extra_data.get('access_token')
        api = twitter.Api(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token_key=access_token.get('oauth_token'),
            access_token_secret=access_token.get('oauth_token_secret'),
            sleep_on_rate_limit=False
        )
        return api

    def get_account_by_screen_name(self, screen_name):
        queryset = Account.objects.filter(screen_name=screen_name)
        if queryset:
            return queryset.get()
        else:
            logger.debug('Fetching user %s from Twitter API.', screen_name)
            return tasks.twitter_update_account(self, screen_name=screen_name)

    def cut(self, accounts, type, duration=None, now=None, action=False):
        if now is None:
            now = timezone.now()
        if duration is None:
            duration = timezone.timedelta(days=7 * 6)  # three months

        for account in accounts:
            extra_duration = timezone.timedelta(
                seconds=random.random() * duration.total_seconds() * 0.1
            )
            until = now + duration + extra_duration

            obj, created = Cut.objects.update_or_create(
                user=self,
                account=account,
                type=type,
                defaults={
                    'until': until
                }
            )
            logger.debug('%s %s', obj, 'created' if created else 'updated')
            if action:
                tasks.action_cut(obj.pk)

    def block(self, screen_name=None, user_id=None):
        now = timezone.now()
        blocked_user = self.api.CreateBlock(
            user_id=user_id,
            screen_name=screen_name,
            include_entities=False,
            skip_status=True
        )
        blocked_account = Account.get_account(blocked_user)
        self.account.add_blocks([blocked_account], updated=now)
        logger.debug('%s has blocked %s', self, blocked_account)

    def unblock(self, screen_name=None, user_id=None):
        now = timezone.now()
        logger.debug(
            'self.api.DestroyBlock(self=%r, user_id=%r, screen_name=%r)',
            self, user_id, screen_name
        )
        unblocked_user = self.api.DestroyBlock(
                user_id=user_id,
                screen_name=screen_name,
                include_entities=False,
                skip_status=True
        )
        unblocked_user = Account.get_account(unblocked_user)
        Relationship.objects.filter(
            subject=self.account,
            type=Relationship.BLOCKS,
            object=unblocked_user
        ).delete()
        logger.debug('%s unblocked %s', self, unblocked_user)

    def mute(self, screen_name=None, user_id=None):
        now = timezone.now()
        muted_user = self.api.CreateMute(
            user_id=user_id,
            screen_name=screen_name,
            include_entities=False,
            skip_status=True
        )
        self.account.add_mutes([Account.get_account(muted_user)], updated=now)

    def unmute(self, screen_name=None, user_id=None):
        now = timezone.now()
        unmuted_user = self.api.DestroyMute(
            user_id=user_id,
            screen_name=screen_name,
            include_entities=False,
            skip_status=True
        )
        unmuted_user = Account.get_account(unmuted_user)
        Relationship.objects.filter(
            subject=self.account,
            type=Relationship.MUTES,
            object=unmuted_user
        ).delete()


class Profile(models.Model):
    user_id = models.BigIntegerField(primary_key=True, editable=False)
    json = JSONField()

class Account(models.Model):
    """A Twitter account"""
    class Meta:
        indexes = (
            models.Index(fields=['screen_name']),
        )

    user_id = models.BigIntegerField(primary_key=True, editable=False)
    screen_name = models.CharField(max_length=30, null=True, editable=False)
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, null=True, editable=False)
    profile_updated = models.DateTimeField(null=True, editable=False)

    def __str__(self):
        return '{}'.format(self.screen_name if self.screen_name is not None else self.user_id)

    @classmethod
    def get_account(cls, arg, now=None):
        return cls.get_accounts(arg, now=now).get()

    @classmethod
    @transaction.atomic
    def get_accounts(cls, *args, now=None):
        """Update account objects from a result returned from the Twitter API.

        Twitter API calls either return lists of big-integer User IDs, or lists
        of instances of 'twitter.model.User' objects.

        Either way, we need to create an 'Account' object for each twitter ID
        we see, and if we see a User object we also want to update the profile
        and 'screen_name' of the Account.

        This method unmagically does the right thing with whatever you pass it.
        """
        if not args:
            raise ValueError('get_accounts() requires ints or instances of twitter.models.User')
        if isinstance(args[0], int):
            if len(args) == 1:
                # The simplest case, make one and return it.
                account, account_created = cls.objects.get_or_create(user_id=args[0])
                return cls.objects.filter(user_id=args[0])
            else:
                # Create a bunch of account objects as efficiently as possible.
                # This tries to do clever bulk_create stuff coz it'll usually
                # be a list of 5000 numbers passed in.

                # Nab the IDs of all the already-existing Account objects.
                existing = set(cls.objects.filter(user_id__in=args).values_list('user_id', flat=True))
                # Work out which objects we need to create
                to_create = set(args) - existing
                # Create the missing account objects a single SQL query and bulk_create
                cls.objects.bulk_create(cls(user_id=user_id) for user_id in to_create)
                # finally, return an un-materialized queryset of all the new objects.
                return cls.objects.filter(user_id__in=args)
        elif isinstance(args[0], twitter.models.User):
            # If we're dealing with User objects, we need need to do it the boring
            # way with a couple SQL queries per object. I'd sure love to make this
            # cleverer.
            if now is None:
                now = timezone.now()
            ids = []
            for arg in args:
                ids.append(arg.id)
                profile, profile_updated = Profile.objects.update_or_create(
                    user_id=arg.id,
                    defaults={
                        'json': arg.AsDict()
                    }
                )
                account, account_updated = cls.objects.update_or_create(
                    user_id=arg.id,
                    defaults={
                        'screen_name': arg.screen_name,
                        'profile_updated': now,
                        'profile': profile
                    }
                )
            return cls.objects.filter(user_id__in=ids)

    @property
    def blocks(self):
        return Account.objects.filter(
            relationship_object_set__type=Relationship.BLOCKS,
            relationship_object_set__subject_id=self,
        )

    @property
    def friends(self):
        return Account.objects.filter(
            relationship_object_set__type=Relationship.FOLLOWS,
            relationship_object_set__subject_id=self,
        )

    @property
    def followers(self):
        return Account.objects.filter(
            relationship_subject_set__type=Relationship.FOLLOWS,
            relationship_subject_set__object_id=self
        )

    @property
    def mutes(self):
        return Account.objects.filter(
            relationship_object_set__type=Relationship.MUTES,
            relationship_object_set__subject_id=self,
        )

    def add_blocks(self, new_blocks, updated):
        return Relationship.add_relationships(
            subjects=[self],
            type=Relationship.BLOCKS,
            objects=new_blocks,
            updated=updated
        )

    def remove_blocks_older_than(self, updated):
        return Relationship.remove_relationships(
            subject=self,
            type=Relationship.BLOCKS,
            updated__lt=updated
        )

    def add_followers(self, new_followers, updated):
        return Relationship.add_relationships(
            subjects=new_followers,
            type=Relationship.FOLLOWS,
            objects=[self],
            updated=updated
        )

    def remove_followers_older_than(self, updated):
        return Relationship.remove_relationships(
            type=Relationship.FOLLOWS,
            object=self,
            updated__lt=updated
        )

    def add_friends(self, new_friends, updated):
        return Relationship.add_relationships(
            subjects=[self],
            type=Relationship.FOLLOWS,
            objects=new_friends,
            updated=updated
        )

    def remove_friends_older_than(self, updated):
        return Relationship.remove_relationships(
            type=Relationship.FOLLOWS,
            subject=self,
            updated__lt=updated
    )

    def add_mutes(self, new_mutes, updated):
        return Relationship.add_relationships(
            subjects=[self],
            type=Relationship.MUTES,
            objects=new_mutes,
            updated=updated
        )

    def remove_mutes_older_than(self, updated):
        return Relationship.remove_relationships(
            subject=self,
            type=Relationship.MUTES,
            updated__lt=updated
        )



class Relationship(models.Model):
    class Meta:
        unique_together = (
            ('type', 'subject', 'object'),
        )
        indexes = (
            models.Index(fields=['type', 'subject']),
            models.Index(fields=['type', 'object']),
        )
    FOLLOWS = 1
    BLOCKS = 2
    MUTES = 3

    TYPE_CHOICES = (
        (FOLLOWS, 'follows'),
        (BLOCKS, 'blocks'),
        (MUTES, 'mutes')
    )

    subject = models.ForeignKey(Account, on_delete=models.CASCADE, editable=False, related_name='relationship_subject_set')
    type = models.IntegerField(choices=TYPE_CHOICES, editable=False)
    object = models.ForeignKey(Account, on_delete=models.CASCADE, editable=False, related_name='relationship_object_set')
    updated = models.DateTimeField(editable=False)

    def __str__(self):
        return '{subject} {type} {object}'.format(
            subject=self.subject, type=self.get_type_display(), object=self.object
        )

    @classmethod
    @transaction.atomic
    def add_relationships(cls, type, subjects, objects, updated):
        existing = cls.objects.filter(
            type=type, subject__in=subjects, object__in=objects
        )
        existing_set = set(existing.values_list('subject', 'object'))
        to_create = []
        for object in objects:
            for subject in subjects:
                if (subject.pk, object.pk) not in existing_set:
                    to_create.append(
                        cls(type=type, subject=subject, object=object, updated=updated)
                    )
        cls.objects.bulk_create(to_create)
        existing.update(updated=updated)
        return cls.objects.filter(type=type, subject__in=subjects, object__in=objects)

    @classmethod
    def remove_relationships(cls, **kwargs):
        relationships = cls.objects.filter(**kwargs)
        if relationships:
            logger.debug('Removing relationships: {}'.format(relationships))
        return relationships.delete()


class Cut(models.Model):
    BLOCK = 1
    MUTE = 2
    TYPE_CHOICES = (
        (BLOCK, 'block'),
        # Mute not implemented yet
        #(MUTE, 'mute'),
    )

    class Meta:
        unique_together = ('user', 'account', 'type')

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    type = models.IntegerField(choices=TYPE_CHOICES)
    until = models.DateTimeField()
    activated = models.BooleanField(default=False, editable=False)

    def __str__(self):
        return '%s %s %s' % (
            self.user,
            'blocking' if self.type == self.BLOCK else 'muting',
            self.account
        )

    @classmethod
    def actionable(cls, now=None):
        """Returns a queryset of all Cuts that need to be actioned."""
        if now is None:
            now = timezone.now()
        qs = cls.objects.filter(
            Q(activated=True, until__lt=now) |
            Q(activated=False, until__gt=now)
        )
        return qs

    @staticmethod
    @transaction.atomic
    def action(cut_pk, now=None):
        """Action a cut -- either mute, unmute, block, or unblock.

        This method runs with locked rows in a transaction, which should
        prevent two of the same call happening to the twitter API at once.

        Effectively I'm using the database lock to lock the Twitter API calls.
        """
        if now is None:
            now = timezone.now()

        cut_qs = Cut.objects.filter(pk=cut_pk).select_for_update()
        if not cut_qs:
            logger.debug("Cut with pk %r doesn't exist.", cut_pk)
            return
        cut = cut_qs.get()
        if cut.type == Cut.BLOCK:
            if not cut.activated and now < cut.until:
                cut._activate_block()
            elif cut.activated and cut.until < now:
                cut._deactivate_block()

    def _deactivate_block(self):
        if self.type != self.BLOCK:
            raise ValueError('Called _deactivate_block() when type = MUTE')
        try:
            self.user.unblock(user_id=self.account.user_id)
        except twitter.TwitterError as e:
            if twitter_error_code(e) == 34:
                # A 34 means that this account doesn't seem to exist anymore.
                # deleting self.account will cascade to all connected objects,
                # which may not be what I want. I don't know how and when
                # suspended accounts come back. Alternatively, maybe what I
                # should do is just add more time to self.until so that it
                # tries again, say, a week later.
                logger.warning('TwitterError 34: Deleting account object %s', self.account)
                self.account.delete()
                return
            else:
                # Any other twitter errors we'll allow to bubble up.
                # TODO: Maybe we should add time to 'until' so it doesn't get
                #       retried right away.
                raise
        self.delete()

    def _activate_block(self):
        if self.type != self.BLOCK:
            raise ValueError('Called _activate_block() when type = MUTE')
        try:
            self.user.block(user_id=self.account.user_id)
        except twitter.TwitterError as e:
            if twitter_error_code(e) == 50:
                logger.warning('TwitterError 50: Deleting account object %s', self.account)
                self.account.delete()
                return
            else:
                raise
        self.activated = True
        self.save(update_fields=['activated'])
