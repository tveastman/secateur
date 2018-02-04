#!/usr/bin/env python

import sys
import logging
import datetime

import django
django.setup()

import secateur.models

logging.basicConfig(level=logging.INFO)
logging.getLogger('secateur').setLevel(logging.DEBUG)
log = logging.getLogger(__name__)

secateur.models.Snip.expire_all()
