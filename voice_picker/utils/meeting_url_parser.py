import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

def detect_meeting_platform(url):
    """URLからミーティングプラットフォームを検出"""
    if 'zoom.us' in url:
        return 'zoom'
    elif 'teams.microsoft.com' in url or 'teams.live.com' in url:
        return 'teams'
    elif 'meet.google.com' in url:
        return 'meet'
    else:
        return None

def extract_meeting_info(url):
    """ミーティングURLから情報を抽出"""
    platform = detect_meeting_platform(url)
    if not platform:
        raise ValueError("サポートされていないミーティングプラットフォームです")
    
    info = {
        'platform': platform,
        'url': url,
        'scheduled_time': datetime.now(),
        'duration_minutes': 120
    }
    
    if platform == 'zoom':
        info.update(_parse_zoom_url(url))
    elif platform == 'teams':
        info.update(_parse_teams_url(url))
    elif platform == 'meet':
        info.update(_parse_meet_url(url))
    
    return info

def _parse_zoom_url(url):
    """Zoom URLの解析"""
    match = re.search(r'/j/(\d+)', url)
    if match:
        meeting_id = match.group(1)
        return {'meeting_id': meeting_id}
    return {}

def _parse_teams_url(url):
    """Teams URLの解析"""
    return {}

def _parse_meet_url(url):
    """Google Meet URLの解析"""
    return {}
