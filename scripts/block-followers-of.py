#!/usr/bin/env python

import sys
import logging
import datetime
import os

import django
django.setup()

from secateur.models import User, Twitter

logging.basicConfig(level=logging.INFO)
logging.getLogger('secateur').setLevel(logging.DEBUG)

user = User.objects.get(username=sys.argv[1])
target = user.fetch(screen_name=sys.argv[2])

NOW = datetime.datetime.now()
DELTA = datetime.timedelta(days=7 * 12)

user.block_followers_of(target, until=NOW + DELTA)
