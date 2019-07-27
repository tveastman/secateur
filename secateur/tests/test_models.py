
import twitter.models
from django.test import TestCase
from django.utils import timezone
from secateur import models


class TestAccounts(TestCase):
    def test_get_accounts_no_args(self):
        assert list(models.Account.get_accounts()) == []

    def test_get_accounts_some_combinations(self):
        result = models.Account.get_accounts(1)
        user_1 = result.get()
        assert user_1.user_id == 1
        assert user_1.profile is None

        user_1, user_2 = models.Account.get_accounts(1, 2).order_by("user_id")
        assert user_1.user_id == 1
        assert user_1.profile is None
        assert user_2.user_id == 2
        assert user_2.profile is None

        now = timezone.now()
        twitter_user_2 = twitter.models.User(id=2, screen_name="two")
        twitter_user_3 = twitter.models.User(id=3, screen_name="three")
        user_2, user_3 = models.Account.get_accounts(
            twitter_user_2, twitter_user_3, now=now
        ).order_by("user_id")
        assert user_2.screen_name == "two"
        assert user_2.user_id == 2
        assert user_2.profile_updated == now
        assert user_2.profile.json["screen_name"] == "two"
        assert user_2.profile.user_id == 2

        assert user_3.screen_name == "three"
        assert user_3.user_id == 3
        assert user_3.profile_updated == now
        assert user_3.profile.json["screen_name"] == "three"
        assert user_3.profile.user_id == 3

        new_now = timezone.now()
        twitter_user_3 = twitter.models.User(id=3, screen_name="3")
        user_3 = models.Account.get_account(twitter_user_3, now=new_now)
        assert user_3.screen_name == "3"
        assert user_3.profile_updated == new_now

    def test_relationship_helpers(self):
        now = timezone.now()
        a0, a1, a2, a3 = models.Account.get_accounts(*range(4)).order_by("user_id")
        a0_followers = [a1, a2]
        a1_followers = [a2, a3]
        a0.add_followers(a0_followers, updated=now)
        a1.add_followers(a1_followers, updated=now)
        assert list(a0.followers.order_by("user_id")) == a0_followers
        assert list(a1.friends.order_by("user_id")) == [a0]
        assert list(a2.friends.order_by("user_id")) == [a0, a1]

        a3_friends = [a0, a1, a2]
        a3.add_friends(a3_friends, now)
        assert list(a3.friends.order_by("user_id")) == a3_friends
        a2.add_blocks([a3], now)
        assert list(a2.blocks) == [a3]
        a2.add_mutes([a3], now)
        assert list(a2.mutes) == [a3]


class TestAddRelationships(TestCase):
    def test_some_combinations(self):
        now = timezone.now()
        users = list(models.Account.get_accounts(*range(10)).order_by("user_id"))
        result = models.Relationship.add_relationships(
            type=models.Relationship.FOLLOWS,
            subjects=users[0:1],
            objects=users[1:2],
            updated=now,
        )
        assert len(result) == 1

        new_now = timezone.now()
        assert now != new_now
        result = models.Relationship.add_relationships(
            type=models.Relationship.FOLLOWS,
            subjects=users[0:1],
            objects=users[1:3],
            updated=new_now,
        )
        assert len(result) == 2
