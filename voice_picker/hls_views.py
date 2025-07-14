import os
import hmac
import hashlib
import time
from django.http import HttpResponse, Http404
from django.views.static import serve
from django.conf import settings
from .models import UploadedFile
import logging

api_logger = logging.getLogger('api')

def generate_signed_url(file_id, filename, expires):
    """
    署名付きURL生成ヘルパー関数
    """
    secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
    message = f"hls:{file_id}:{expires}"
    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"/api/hls-stream/{file_id}/{filename}?expires={expires}&signature={signature}"


def serve_hls_content(request, file_id, filename):
    """
    署名付きHLSコンテンツ配信
    """
    # 署名検証
    expires = request.GET.get('expires')
    signature = request.GET.get('signature')

    if not all([expires, signature]):
        return HttpResponse("Invalid parameters", status=401)

    # 有効期限チェック
    if int(expires) < int(time.time()):
        return HttpResponse("URL expired", status=401)

    # 署名検証
    secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
    message = f"hls:{file_id}:{expires}"
    expected_signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return HttpResponse("Invalid signature", status=401)

    # master.m3u8の場合は動的生成
    if filename == 'master.m3u8':
        return generate_dynamic_master_playlist(file_id, expires, signature)

    # HLSファイルパス構築
    hls_path = os.path.join(settings.MEDIA_ROOT, 'hls', str(file_id), filename)

    if not os.path.exists(hls_path):
        raise Http404("File not found")

    # MIMEタイプ設定
    if filename.endswith('.m3u8'):
        content_type = 'application/x-mpegURL'
    elif filename.endswith('.ts'):
        content_type = 'video/MP2T'
    else:
        content_type = 'application/octet-stream'

    # CORSヘッダー設定（必要に応じて）
    response = serve(request, os.path.relpath(hls_path, settings.MEDIA_ROOT), document_root=settings.MEDIA_ROOT)
    response['Content-Type'] = content_type
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'max-age=3600'

    return response


def generate_dynamic_master_playlist(file_id, expires, signature):
    """
    署名付きURLを含む動的master.m3u8生成
    """
    # HLSディレクトリの存在確認
    hls_dir = os.path.join(settings.MEDIA_ROOT, 'hls', str(file_id))
    if not os.path.exists(hls_dir):
        raise Http404("HLS directory not found")

    # 利用可能な品質バリアントを検索
    variants = []

    # 360pと720pのディレクトリをチェック
    for variant_name in ['360p', '720p']:
        variant_dir = os.path.join(hls_dir, variant_name)
        playlist_file = os.path.join(variant_dir, 'playlist.m3u8')

        if os.path.exists(playlist_file):
            # playlist.m3u8の内容を読んで解像度・帯域幅情報を取得
            try:
                with open(playlist_file, 'r') as f:
                    content = f.read()

                # 署名付きURL生成
                signed_url = generate_signed_url(file_id, f"{variant_name}/playlist.m3u8", expires)

                # バリアント情報を追加
                if variant_name == '360p':
                    bandwidth = 564000  # 500k video + 64k audio
                    resolution = "640x360"
                elif variant_name == '720p':
                    bandwidth = 1628000  # 1500k video + 128k audio
                    resolution = "1280x720"

                variants.append({
                    'bandwidth': bandwidth,
                    'resolution': resolution,
                    'url': signed_url
                })

            except Exception as e:
                api_logger.warning(f"Failed to read {variant_name} playlist: {e}")
                continue

    if not variants:
        raise Http404("No valid HLS variants found")

    # 動的master.m3u8生成
    master_content = "#EXTM3U\n#EXT-X-VERSION:3\n"

    for variant in variants:
        master_content += f"#EXT-X-STREAM-INF:BANDWIDTH={variant['bandwidth']},RESOLUTION={variant['resolution']}\n"
        master_content += f"{variant['url']}\n"

    # レスポンス生成
    response = HttpResponse(master_content, content_type='application/x-mpegURL')
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'max-age=300'  # 5分間キャッシュ

    return response
