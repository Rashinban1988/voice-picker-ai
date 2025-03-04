"""
otomamay_appプロジェクトのURL設定。

urlpatterns`リストはURLをビューにルーティングします。詳しくは
    https://docs.djangoproject.com/en/4.2/topics/http/urls/ を参照してください。
例
機能ビュー
    1. インポートを追加する: from my_app import views
    2. URLをurlpatternsに追加： path('', views.home, name='home')
クラスベースのビュー
    1. インポートを追加する: from other_app.views import Home
    2. URLをurlpatternsに追加する: path('', Home.as_view(), name='home')
別のURLconfを含める
    1. include() 関数をインポートします: from django.urls import include, path
    2. URL を urlpatterns に追加します: path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from member_management.admin import admin_site
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from . import views
from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    path('', views.home, name='home'),
    path('voice_picker/', include('voice_picker.urls')),
    path('admin/', admin_site.urls),
    path('job_seekers/', include('job_seekers.urls')),
    path('member_management/', include('member_management.urls')),

    path('api/', include('config.api_urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('__reload__/', include('django_browser_reload.urls')), # 開発用ブラウザ自動更新
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}), # メディアファイルの提供

        # swagger
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ]
