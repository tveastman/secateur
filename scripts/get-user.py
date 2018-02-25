#!/usr/bin/env python

import sys
import logging
import argparse

import django
django.setup()

logging.basicConfig(level=logging.INFO)
logging.getLogger('secateur').setLevel(logging.DEBUG)
log = logging.getLogger(__name__)

import django_q

import secateur.tasks
import secateur.models

parser = argparse.ArgumentParser("Secateur CLI")
parser.add_argument(
    '--as', dest='secateur_username', type=str, nargs=1, required=True
)
parser.add_argument('accounts', metavar='ACCOUNT', nargs='*', type=str)
args = parser.parse_args()
log.debug('args: %s', args)

user = secateur.models.User.objects.get(username=args.secateur_username[0])
for account_screen_name in args.accounts:
    account = user.get_account_by_screen_name(account_screen_name)
    secateur.tasks.twitter_update_followers(user, account)
    secateur.tasks.twitter_update_friends(user, account)
