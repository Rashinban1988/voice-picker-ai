"""
matching_appプロジェクトのURL設定。

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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('job_seekers/', include('job_seekers.urls')),
    # path('common/', include('common.urls')),
    # path('companies/', include('companies.urls')),
    # path('calendar/', include('calendar_app.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('__reload__/', include('django_browser_reload.urls')), # 開発用ブラウザ自動更新
    ]
