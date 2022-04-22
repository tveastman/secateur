#!/usr/bin/env python3

"""
Do a pass through all users, and if the user's API key is disabled and they have
blocks with an "until", set them to until=None.
"""

import django
from django.db.models.functions import Now

django.setup()

import secateur.models

for user in secateur.models.User.objects.filter(is_twitter_api_enabled=False):
    number_updated = secateur.models.Relationship.objects.filter(
        subject=user.account_id, type__in=[2, 3], until__lt=Now()
    ).update(until=None)
    print(f"user = {user}, unset = {number_updated}")
