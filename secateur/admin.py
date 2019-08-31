from pprint import pformat

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

import social_django.admin

from . import models


## MONKEYPATCH: Hide the 'extra_data' field from the 'user social auth'
## model. That's the field that has a user's oauth credentials in it,
## They're sensitive and we don't want them to be exposed if anyone gets
## access to an admin account. They'd still be exposed if an attacker
## achieves code execution, but that's a higher bar than nabbing admin
## access credentials.
social_django.admin.UserSocialAuthOption.exclude = ["extra_data"]


def update_user_details(modeladmin, request, queryset):
    import secateur.tasks

    for secateur_user in queryset:
        secateur.tasks.update_user_details(secateur_user)


class SecateurUserAdmin(UserAdmin):
    fieldsets = (
        ("Secateur", {"fields": ("is_twitter_api_enabled", "account")}),
    ) + UserAdmin.fieldsets
    list_display = (
        "username",
        "first_name",
        "last_name",
        "last_login",
        "is_twitter_api_enabled",
        "is_staff",
    )
    list_editable = ("is_twitter_api_enabled",)
    readonly_fields = ("account",) + UserAdmin.readonly_fields

    actions = [update_user_details]


admin.site.register(models.User, SecateurUserAdmin)


def get_user(modeladmin, request, queryset):
    # Let's not accidentally do the whole database.
    TOO_MANY = 200
    import secateur.tasks

    for account in queryset[:TOO_MANY]:
        secateur.tasks.get_user.delay(request.user.pk, account.user_id).forget()


get_user.short_description = "Update profile from Twitter."


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("user_id", "screen_name", "name")
    search_fields = ("user_id", "screen_name_lower")
    readonly_fields = (
        "user_id",
        "screen_name",
        "name",
        "screen_name_lower",
        "profile_updated",
        "profile",
    )
    actions = [get_user]


@admin.register(models.Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    search_fields = ("object__screen_name_lower", "subject__screen_name_lower")
    list_display = ("subject", "type", "object", "until", "updated")
    list_filter = ("type",)
    date_hierarchy = "updated"
    readonly_fields = ("subject", "type", "object", "updated")


@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("screen_name", "name", "description")
    readonly_fields = (
        "screen_name",
        "name",
        "description",
        "location",
        "formatted_json",
    )
    search_fields = ("json__description", "json__screen_name")

    def formatted_json(self, obj):
        return format_html("<pre>{}</pre>", pformat(obj.json))


@admin.register(models.LogMessage)
class LogMessageAdmin(admin.ModelAdmin):
    list_display = ("time", "user", "message")
    list_filter = ("user",)
    date_hierarchy = "time"
