import os
import hmac
import hashlib
from django.http import HttpResponse, Http404
from django.views.static import serve
from django.conf import settings
from .models import UploadedFile
import logging

api_logger = logging.getLogger('api')

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
    import time
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
