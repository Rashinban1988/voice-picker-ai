from django.contrib import admin
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from .models.organization import Organization
from .models.user import User

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

# カスタム管理サイトを使用するように設定
admin.site = admin_site
admin.autodiscover()