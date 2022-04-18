#!/usr/bin/env python3

import django

django.setup()

import social_django.models

usas = social_django.models.UserSocialAuth.objects.exclude(extra_data=None)
for usa in usas:
    user = usa.user
    if user.oauth_token:
        print(f"Skipping {user}")
        continue
    user.oauth_token = usa.extra_data["access_token"]["oauth_token"]
    user.oauth_token_secret = usa.extra_data["access_token"]["oauth_token_secret"]
    user.save(update_fields=["oauth_token", "oauth_token_secret"])
    print(f"Updated {user}")
