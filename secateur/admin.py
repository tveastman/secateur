from django.contrib import admin

from . import models


@admin.register(models.Twitter)
class TwitterAdmin(admin.ModelAdmin):
    readonly_fields = [
        'screen_name', 'user_id', 'profile_updated', 'friends_updated',
        'followers_updated', 'blocks_updated', 'mutes_updated',
        'blocks', 'mutes']
    list_display = ['user_id', 'screen_name', 'profile_updated']
    ordering = ['screen_name']
    search_fields = ['user_id', 'screen_name']

@admin.register(models.Snip)
class SnipAdmin(admin.ModelAdmin):
    list_display = ['twitter', 'user', 'type', 'until']
    list_filter = ['user', 'type']
