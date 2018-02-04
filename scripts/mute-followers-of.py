#!/usr/bin/env python

import sys
import logging
import datetime

import django
from django.utils.timezone import now
django.setup()

from secateur.models import User, Twitter

logging.basicConfig(level=logging.DEBUG)
#logging.getLogger('secateur').setLevel(logging.DEBUG)

user = User.objects.get(username=sys.argv[1])
target = user.fetch(screen_name=sys.argv[2])

NOW = now()
DELTA = datetime.timedelta(days=7 * 2)

user.mute_followers_of(target, until=NOW + DELTA)
