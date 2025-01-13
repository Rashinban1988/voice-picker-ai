from django.contrib import admin
from .models import Organization, User

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone_number', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['name', 'phone_number']

class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'sei', 'mei', 'email', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['sei', 'mei', 'email']

admin.site.register(Organization, OrganizationAdmin)
admin.site.register(User, UserAdmin)