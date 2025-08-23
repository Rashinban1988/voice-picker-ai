from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, timedelta
from .models import PromptHistory
from member_management.models import Organization


@staff_member_required
def prompt_analytics_view(request):
    """プロンプト分析ダッシュボード"""

    # クエリパラメータから期間を取得
    year = request.GET.get('year')
    week = request.GET.get('week')
    organization_id = request.GET.get('organization')

    # デフォルトは現在の週
    if not year or not week:
        now = datetime.now()
        year = now.year
        week = now.isocalendar()[1]
    else:
        year = int(year)
        week = int(week)

    # 基本クエリセット
    queryset = PromptHistory.objects.filter(year=year, week_of_year=week)

    # 組織でフィルタリング
    selected_organization = None
    if organization_id:
        try:
            selected_organization = Organization.objects.get(id=organization_id)
            queryset = queryset.filter(organization=selected_organization)
        except Organization.DoesNotExist:
            pass

    # 年と週のリストを生成
    current_year = datetime.now().year
    years = list(range(2024, current_year + 2))  # 2024年から来年まで
    simple_weeks = list(range(1, 53))  # シンプルな週リスト

    # 週選択肢を詳細表示で生成
    week_choices = []
    for w in range(1, 53):
        # ISO週から日付を計算
        from datetime import date
        try:
            # その年の第w週の月曜日を取得
            monday = date.fromisocalendar(year, w, 1)
            sunday = date.fromisocalendar(year, w, 7)
            month_info = f"{monday.month}月"
            date_range = f"{monday.day}日〜{sunday.day}日"
            week_choices.append({
                'week': w,
                'label': f"第{w}週（{month_info} {date_range}）"
            })
        except ValueError:
            # 存在しない週の場合（年末など）
            week_choices.append({
                'week': w,
                'label': f"第{w}週"
            })

    # 統計データの集計
    context = {
        'year': year,
        'week': week,
        'years': years,
        'simple_weeks': simple_weeks,
        'week_choices': week_choices,
        'selected_organization': selected_organization,
        'organizations': Organization.objects.all(),
        'total_regenerations': queryset.count(),
        'by_type': {},
        'by_category': {},
        'popular_keywords': [],
        'recent_prompts': [],
        'weekly_trend': [],
    }

    # プロンプトタイプ別の集計
    type_stats = queryset.values('prompt_type').annotate(count=Count('id'))
    for stat in type_stats:
        context['by_type'][stat['prompt_type']] = stat['count']

    # カテゴリ別の集計
    category_stats = queryset.exclude(
        instruction_category__isnull=True
    ).exclude(
        instruction_category=''
    ).values('instruction_category').annotate(count=Count('id'))

    for stat in category_stats:
        context['by_category'][stat['instruction_category']] = stat['count']

    # キーワード分析
    all_keywords = []
    for history in queryset.exclude(instruction_keywords=[]):
        all_keywords.extend(history.instruction_keywords)

    keyword_counts = {}
    for keyword in all_keywords:
        if keyword in keyword_counts:
            keyword_counts[keyword] += 1
        else:
            keyword_counts[keyword] = 1

    # 人気キーワードトップ10
    popular_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    context['popular_keywords'] = [
        {'keyword': keyword, 'count': count}
        for keyword, count in popular_keywords
    ]

    # 最近のプロンプト（カスタム指示があるもの）
    recent_prompts = queryset.exclude(
        custom_instruction__isnull=True
    ).exclude(
        custom_instruction=''
    ).order_by('-created_at')[:10].select_related('uploaded_file', 'organization')

    context['recent_prompts'] = recent_prompts

    # 週間トレンド（過去4週間）
    for i in range(3, -1, -1):
        target_week = week - i
        target_year = year

        # 年をまたぐ場合の処理
        if target_week <= 0:
            target_year -= 1
            target_week = 52 + target_week  # 52週として計算

        week_queryset = PromptHistory.objects.filter(
            year=target_year,
            week_of_year=target_week
        )

        if selected_organization:
            week_queryset = week_queryset.filter(organization=selected_organization)

        context['weekly_trend'].append({
            'week': f'{target_year}年 第{target_week}週',
            'count': week_queryset.count()
        })

    # 組織別ランキング（全体表示の場合）
    if not selected_organization:
        org_ranking = queryset.values(
            'organization__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        context['org_ranking'] = org_ranking

    # 使用率の高い時間帯
    hour_stats = queryset.extra(
        select={'hour': 'HOUR(created_at)'}
    ).values('hour').annotate(count=Count('id')).order_by('hour')

    context['hour_stats'] = hour_stats

    # ナビゲーション用の週リスト
    navigation_weeks = []
    for i in range(-4, 5):
        nav_week = week + i
        nav_year = year

        if nav_week <= 0:
            nav_year -= 1
            nav_week = 52 + nav_week
        elif nav_week > 52:
            nav_year += 1
            nav_week = nav_week - 52

        # ナビゲーション週の日付範囲を計算
        from datetime import date
        try:
            monday = date.fromisocalendar(nav_year, nav_week, 1)
            sunday = date.fromisocalendar(nav_year, nav_week, 7)
            date_range = f"{monday.month}/{monday.day}〜{sunday.month}/{sunday.day}"
            navigation_weeks.append({
                'year': nav_year,
                'week': nav_week,
                'label': f'{nav_year}年 第{nav_week}週',
                'date_range': date_range,
                'is_current': (nav_year == year and nav_week == week)
            })
        except ValueError:
            navigation_weeks.append({
                'year': nav_year,
                'week': nav_week,
                'label': f'{nav_year}年 第{nav_week}週',
                'date_range': '',
                'is_current': (nav_year == year and nav_week == week)
            })

    context['navigation_weeks'] = navigation_weeks

    return render(request, 'admin/voice_picker/prompt_analytics.html', context)