from django.contrib import admin
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from .models.organization import Organization
from .models.user import User
from .models.subscription import Subscription, SubscriptionPlan
from voice_picker.models import Environment, ScheduledRecording

# スーパーユーザーのみがアクセスできるデコレーター
def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone_number', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['name', 'phone_number']

class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'organization', 'last_name', 'first_name', 'email', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['last_name', 'first_name', 'email']

class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'max_duration', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'stripe_price_id']

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'plan', 'status', 'current_period_start', 'current_period_end', 'created_at']
    list_filter = ['status', 'created_at', 'cancel_at_period_end']
    search_fields = ['organization__name', 'stripe_customer_id', 'stripe_subscription_id']

class EnvironmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'value', 'exist', 'created_at', 'updated_at']
    list_filter = ['exist', 'created_at']
    search_fields = ['code', 'value']

class ScheduledRecordingAdmin(admin.ModelAdmin):
    list_display = ['id', 'meeting_topic', 'status', 'scheduled_start_time', 'created_at', 'updated_at']
    list_filter = ['status', 'recording_type', 'created_at']
    search_fields = ['meeting_topic', 'meeting_id', 'host_email']

class CustomAdminSite(admin.AdminSite):
    site_header = "カスタム管理サイト"
    site_title = "管理サイト"
    index_title = "管理サイトのダッシュボード"

    @method_decorator(superuser_required)  # ここでデコレーターを適用
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

admin_site = CustomAdminSite(name='custom_admin')
admin_site.register(Organization, OrganizationAdmin)
admin_site.register(User, UserAdmin)
admin_site.register(SubscriptionPlan, SubscriptionPlanAdmin)
admin_site.register(Subscription, SubscriptionAdmin)
admin_site.register(Environment, EnvironmentAdmin)
admin_site.register(ScheduledRecording, ScheduledRecordingAdmin)

# カスタム管理サイトを使用するように設定
admin.site = admin_site
admin.autodiscover()