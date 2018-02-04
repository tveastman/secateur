#!/usr/bin/env python

import sys
import logging

import django
django.setup()

from secateur.models import User, Twitter

logging.basicConfig(level=logging.INFO)
logging.getLogger('secateur').setLevel(logging.DEBUG)
log = logging.getLogger(__name__)

user = User.objects.get(username=sys.argv[1])

user.fetch_friends()
user.fetch_followers()
user.fetch_mutes()
user.fetch_blocks()
