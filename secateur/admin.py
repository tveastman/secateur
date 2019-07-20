from pprint import pformat

from django.contrib import admin
from . import models
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html, escape


class SecateurUserAdmin(UserAdmin):
    fieldsets = (
        ("Secateur", {"fields": ("is_twitter_api_enabled",)}),
    ) + UserAdmin.fieldsets
    list_display = (
        "username",
        "first_name",
        "last_name",
        "is_twitter_api_enabled",
        "is_staff",
    )


admin.site.register(models.User, SecateurUserAdmin)


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
