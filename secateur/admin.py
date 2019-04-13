from pprint import pformat

from django.contrib import admin
from . import models
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html, escape

admin.site.register(models.User, UserAdmin)

@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("user_id", "screen_name", "name")
    search_fields = ("user_id", "screen_name_lower")
    readonly_fields = ("user_id", "screen_name", "name", "screen_name_lower", "profile_updated", "profile")


@admin.register(models.Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ("subject", "type", "object", "until", "updated")
    list_filter = ("type",)
    date_hierarchy = "updated"
    readonly_fields = ("subject", "type", "object", "updated")

@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("screen_name", "name", "description")
    readonly_fields = ("description", "formatted_json")
    search_fields = ("json__description",)

    def formatted_json(self, obj):
        return format_html(
            "<pre>{}</pre>",
            pformat(obj.json),
        )
