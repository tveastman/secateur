from django.contrib import admin
from . import models

# Register your models here.


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    search_fields = ("username",)
    fields = ["username"]
    readonly_fields = ["username"]


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("user_id", "screen_name")
    search_fields = ("user_id", "screen_name")
    readonly_fields = ("user_id", "screen_name", "profile_updated", "profile")


@admin.register(models.Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ("subject", "type", "object", "until", "updated")
    list_filter = ("type",)
    date_hierarchy = "updated"
    readonly_fields = ("subject", "type", "object", "updated")


@admin.register(models.Cut)
class CutAdmin(admin.ModelAdmin):
    list_display = ("user", "account", "type", "until", "activated")
    list_filter = ("user", "type", "activated")
    date_hierarchy = "until"
    autocomplete_fields = ("user", "account")
    readonly_fields = ("activated",)
