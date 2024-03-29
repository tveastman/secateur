from typing import Optional

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import HttpRequest
from django.template.response import TemplateResponse

import social_django.admin
from django.utils.html import format_html

from . import models


## MONKEYPATCH: Hide the 'extra_data' field from the 'user social auth'
## model. That's the field that has a user's oauth credentials in it,
## They're sensitive and we don't want them to be exposed if anyone gets
## access to an admin account. They'd still be exposed if an attacker
## achieves code execution, but that's a higher bar than nabbing admin
## access credentials.
# social_django.admin.UserSocialAuthOption.exclude = ["extra_data"]


def update_user_details(
    modeladmin: ModelAdmin, request: WSGIRequest, queryset: QuerySet
) -> Optional[TemplateResponse]:
    import secateur.tasks

    for secateur_user in queryset:
        secateur.tasks.update_user_details(secateur_user)
    return None


class SecateurUserAdmin(UserAdmin):
    fieldsets = (
        (
            "Secateur",
            {
                "fields": (
                    "screen_name",
                    "oauth_token",
                    "twitter_url",
                    "is_twitter_api_enabled",
                    "account",
                    "current_tokens",
                    "token_bucket_max",
                    "token_bucket_rate",
                    "token_bucket_time",
                    "token_bucket_value",
                    "max_until",
                )
            },
        ),
    ) + UserAdmin.fieldsets
    list_display = (
        "screen_name",
        "last_login",
        "current_tokens",
        "has_access_token",
        "is_twitter_api_enabled",
    )
    search_fields = ("username", "screen_name")  # , "account_id", "pk"
    ordering = ("-last_login",)
    list_editable = ("is_twitter_api_enabled",)
    readonly_fields = (
        "twitter_url",
        "account",
        "current_tokens",
        "screen_name",
        "oauth_token",
        "max_until",
    ) + UserAdmin.readonly_fields

    actions = [update_user_details]

    def twitter_url(self, obj: models.User) -> str:
        return format_html('<a href="{url}">{url}</a>', url=obj.account.twitter_url)

    def has_access_token(self, obj: models.User) -> bool:
        return bool(obj.oauth_token)

    has_access_token.boolean = True  # type: ignore


admin.site.register(models.User, SecateurUserAdmin)


# This ridiculousness is just to stop mypy complaining about the 'short_description' attribute
# on the function.
class GetUserFunction:
    __name__ = "get_user"
    short_description: str = "Update profile from Twitter."

    def __call__(
        self, modeladmin: ModelAdmin, request: WSGIRequest, queryset: QuerySet
    ) -> Optional[TemplateResponse]:
        # Let's not accidentally do the whole database.
        TOO_MANY = 200
        import secateur.tasks

        for account in queryset[:TOO_MANY]:
            secateur.tasks.get_user.delay(request.user.pk, account.user_id).forget()
        return None


get_user = GetUserFunction()


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "user_id",
        "screen_name",
        "name",
        "followers_count",
        "description",
    )
    search_fields = ("user_id", "screen_name__iexact")
    readonly_fields = (
        "user_id",
        "twitter_url",
        "screen_name",
        "profile_updated",
        "name",
        "description",
        "location",
        "profile_image_url_https",
        "profile_banner_url",
        "favourites_count",
        "followers_count",
        "friends_count",
        "statuses_count",
        "listed_count",
        "created_at",
    )
    actions = [get_user]
    show_full_result_count = False

    def twitter_url(self, obj: models.Account) -> str:
        return format_html('<a href="{url}">{url}</a>', url=obj.twitter_url)

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            queryset = queryset.filter(screen_name__iexact=search_term)
        return queryset, False

    def get_paginator(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        per_page: int,
        orphans=0,
        allow_empty_first_page=True,
    ) -> Paginator:
        MAX = 10_000
        queryset = queryset[:MAX]
        return super().get_paginator(
            request=request,
            queryset=queryset,
            per_page=per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
        )


@admin.register(models.Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    search_fields = ("object__screen_name__iexact", "subject__screen_name__iexact")
    list_display = ("subject", "type", "object", "until", "updated")
    list_filter = ("type",)
    date_hierarchy = "updated"
    readonly_fields = ("subject", "type", "object", "updated")
    show_full_result_count = False

    def get_paginator(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        per_page: int,
        orphans=0,
        allow_empty_first_page=True,
    ) -> Paginator:
        MAX = 10_000
        queryset = queryset[:MAX]
        return super().get_paginator(
            request=request,
            queryset=queryset,
            per_page=per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
        )


@admin.register(models.LogMessage)
class LogMessageAdmin(admin.ModelAdmin):
    list_display = ("time", "user", "action", "account", "get_followers_count", "until")
    list_filter = ("action", "user")
    # date_hierarchy = "time"
    raw_id_fields = ("account",)
    show_full_result_count = False

    def get_followers_count(self, obj):
        return obj.account.followers_count if obj.account else None

    get_followers_count.short_description = "Followers"

    def get_paginator(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        per_page: int,
        orphans=0,
        allow_empty_first_page=True,
    ) -> Paginator:
        MAX = 10_000
        queryset = queryset[:MAX]
        return super().get_paginator(
            request=request,
            queryset=queryset,
            per_page=per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
        )
