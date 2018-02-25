from django.contrib import admin
from . import models
# Register your models here.


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'screen_name')
    readonly_fields = ('user_id', 'screen_name', 'profile_updated', 'profile')

@admin.register(models.Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ('subject', 'type', 'object', 'updated')
    list_filter = ('type',)
    date_hierarchy = 'updated'
    readonly_fields = ('subject', 'type', 'object', 'updated')
