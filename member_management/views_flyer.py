from django.views import View
from django.http import HttpResponse
from .models import CampaignTracking
import logging

logger = logging.getLogger('django')


class CampaignStatsView(View):
    """キャンペーン統計情報を表示するビュー"""

    def get(self, request):
        # 管理者権限チェック
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponse('Unauthorized', status=401)

        # 統計情報を取得
        flyer_stats = CampaignTracking.get_stats(source=CampaignTracking.Source.FLYER)
        all_stats = CampaignTracking.get_stats()

        # 最近のアクセス
        recent_flyer_access = CampaignTracking.objects.filter(
            source=CampaignTracking.Source.FLYER
        ).order_by('-accessed_at')[:10]

        # 最近の登録
        recent_registrations = CampaignTracking.objects.filter(
            source=CampaignTracking.Source.FLYER,
            registered_user__isnull=False
        ).order_by('-registered_at')[:10]

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>キャンペーン統計</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #333;
                    border-bottom: 2px solid #4CAF50;
                    padding-bottom: 10px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }}
                .stat-card {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border-radius: 8px;
                    border-left: 4px solid #4CAF50;
                }}
                .stat-value {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #4CAF50;
                }}
                .stat-label {{
                    color: #666;
                    margin-top: 5px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #4CAF50;
                    color: white;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>チラシキャンペーン統計</h1>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{flyer_stats['total_access']}</div>
                        <div class="stat-label">チラシからのアクセス数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{flyer_stats['total_registered']}</div>
                        <div class="stat-label">チラシ経由の登録数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{flyer_stats['conversion_rate']:.1f}%</div>
                        <div class="stat-label">コンバージョン率</div>
                    </div>
                </div>

                <h2>全体統計</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{all_stats['total_access']}</div>
                        <div class="stat-label">総アクセス数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{all_stats['total_registered']}</div>
                        <div class="stat-label">総登録数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{all_stats['conversion_rate']:.1f}%</div>
                        <div class="stat-label">全体コンバージョン率</div>
                    </div>
                </div>

                <h2>最近のチラシアクセス</h2>
                <table>
                    <thead>
                        <tr>
                            <th>アクセス日時</th>
                            <th>セッションID</th>
                            <th>IPアドレス</th>
                            <th>登録状況</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        for access in recent_flyer_access:
            registered = "✅ 登録済" if access.registered_user else "未登録"
            html_content += f"""
                        <tr>
                            <td>{access.accessed_at.strftime('%Y-%m-%d %H:%M')}</td>
                            <td>{access.session_id[:8]}...</td>
                            <td>{access.ip_address or 'N/A'}</td>
                            <td>{registered}</td>
                        </tr>
            """

        html_content += """
                    </tbody>
                </table>

                <h2>最近の登録ユーザー（チラシ経由）</h2>
                <table>
                    <thead>
                        <tr>
                            <th>登録日時</th>
                            <th>ユーザー名</th>
                            <th>アクセス→登録の経過時間</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        for reg in recent_registrations:
            if reg.registered_at and reg.accessed_at:
                elapsed = reg.registered_at - reg.accessed_at
                hours = int(elapsed.total_seconds() // 3600)
                minutes = int((elapsed.total_seconds() % 3600) // 60)
                elapsed_str = f"{hours}時間{minutes}分"
            else:
                elapsed_str = "N/A"

            user_name = reg.registered_user.email if reg.registered_user else "N/A"
            html_content += f"""
                        <tr>
                            <td>{reg.registered_at.strftime('%Y-%m-%d %H:%M') if reg.registered_at else 'N/A'}</td>
                            <td>{user_name}</td>
                            <td>{elapsed_str}</td>
                        </tr>
            """

        html_content += """
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

        return HttpResponse(html_content, content_type='text/html')