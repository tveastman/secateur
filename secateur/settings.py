"""
Django settings for secateur project.

Generated by 'django-admin startproject' using Django 2.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os
import secrets
import sys

import dj_database_url

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", secrets.token_urlsafe(50))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost").split()
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "django.contrib.flatpages",
    "django.contrib.postgres",
    "django_celery_beat",
    "social_django",
    "bootstrap4",
    "request",
    "psqlextra",
    "waffle",
    "secateur.apps.SecateurConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "xff.middleware.XForwardedForMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "request.middleware.RequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
    "csp.middleware.CSPMiddleware",
    "waffle.middleware.WaffleMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
    "django_structlog.middlewares.CeleryMiddleware",
]

XFF_TRUSTED_PROXY_DEPTH = 1

ROOT_URLCONF = "secateur.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "secateur.wsgi.application"

POSTGRES_EXTRA_AUTO_EXTENSION_SET_UP = False
DATABASES = {
    "default": dj_database_url.config(default="postgres://postgres@postgres/postgres")
}
DATABASES["default"]["ENGINE"] = "psqlextra.backend"

# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Pacific/Auckland"

USE_I18N = True

# USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

AUTH_USER_MODEL = "secateur.User"

# DJANGO SOCIAL AUTH TWITTER SUPPORT
AUTHENTICATION_BACKENDS = ("social_core.backends.twitter.TwitterOAuth",)
SOCIAL_AUTH_TWITTER_KEY = os.environ.get("CONSUMER_KEY")
SOCIAL_AUTH_TWITTER_SECRET = os.environ.get("CONSUMER_SECRET")
LOGIN_URL = "/login/twitter/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
SOCIAL_AUTH_STRATEGY = "social_django.strategy.DjangoStrategy"
SOCIAL_AUTH_STORAGE = "social_django.models.DjangoStorage"
SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.user.user_details",
    ## 'debug' puts PII in your log file, use with care.
    # "social_core.pipeline.debug.debug",
    "secateur.utils.pipeline_user_account_link",
)

LOGGING = None
import secateur.logging

# A fix for a timezone issue
DJANGO_CELERY_BEAT_TZ_AWARE = False

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis/1")
if CELERY_BROKER_URL.lower().startswith("redis"):
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "visibility_timeout": 60 * 60 * 24,
        "queue_order_strategy": "priority",
    }
elif CELERY_BROKER_URL.lower().startswith("sqs"):
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "visibility_timeout": 60 * 60 * 12,
        "region": os.environ.get("SQS_QUEUE_REGION"),
        "polling_interval": 5.0,
        "wait_time_seconds": 20,
        "queue_name_prefix": os.environ.get("SQS_QUEUE_NAME_PREFIX"),
    }
CELERY_RESULT_BACKEND = "redis://redis/1"
CELERY_IMPORTS = ["secateur.tasks"]
CELERY_TASK_SERIALIZER = (
    "pickle"  # 'pickle' because I'm passing partial functions around.
)
CELERY_RESULT_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["pickle"]
CELERY_TASK_ROUTES = {
    "secateur.tasks.create_relationship": {"queue": "blocker"},
    "secateur.tasks.create_relationships": {"queue": "blocker"},
    "secateur.tasks.destroy_relationship": {"queue": "blocker"},
    "secateur.tasks.mem_top": {"queue": "blocker"},
}


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_LOCATION", "redis://redis:6379/2"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "secateur:",
    }
}

BOOTSTRAP4 = {
    "include_jquery": True,
    "css_url": {
        "href": "/static/css/bootstrap.min.css",
        "integrity": "sha384-WskhaSGFgHYWDcbwN70/dfYBj47jz9qbsMId/iRN3ewGhXQFZCSftd1LZCfmhktB",
        "crossorigin": "anonymous",
    },
    "javascript_url": {
        "url": "/static/js/bootstrap.min.js",
        "integrity": "sha384-smHYKdLADwkXOn1EmN1qk/HfnUcbVRZyYmZ4qpPea6sjB/pTJ0euyQp0Mk8ck+5T",
        "crossorigin": "anonymous",
    },
    "jquery_url": {
        "url": "/static/js/jquery-3.4.1.min.js",
        "integrity": "sha384-vk5WoKIaW/vJyUAd9n/wmopsmNhiy+L2Z+SBxGYnUkunIxVxAv/UtMOhba/xskxh",
        "crossorigin": "anonymous",
    },
    "popper_url": {
        "url": "/static/js/popper.min.js",
        "integrity": "sha384-ZMP7rVo3mIykV+2+9J3UJ46jBk0WLaUAdn689aCwoqbBJiSnjAK/l8WvCWPIPm49",
        "crossorigin": "anonymous",
    },
}

CSP_IMG_SRC = ["'self'", "pbs.twimg.com"]
CSP_EXCLUDE_URL_PREFIXES = ("/admin/request/request/overview/",)

# By forcing people to log in if they haven't used the app for a day, we know
# that User.last_login being old will accurately convey that they haven't used
# the app for a while, we can remove the oauth credentials of anyone who
# (a) hasn't used the app in a while, and (b) has no pending scheduled
# operations (like unblocks or unmutes).
SESSION_COOKIE_AGE = 60 * 60 * 18  # 18 hours: gotta log in every day.


# WAFFLE SETTING
WAFFLE_CREATE_MISSING_FLAGS = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
