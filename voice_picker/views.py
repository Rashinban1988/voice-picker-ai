import json
import logging
import mimetypes
from openai import OpenAI
import os
import time
import warnings
import re
import webvtt
import uuid
import random
from typing import Optional
from moviepy.editor import VideoFileClip
# import wave

import numpy as np
import noisereduce as nr
from functools import lru_cache
from celery import shared_task
from django.db import transaction
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views import View
from dotenv import load_dotenv
from pydub import AudioSegment
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action, permission_classes
from django.views.decorators.csrf import csrf_exempt
from typing import Union
import hashlib
import hmac
from django.utils.http import urlencode
from urllib.parse import unquote
from vosk import KaldiRecognizer, Model
import torch
import whisper
from .models import Transcription, UploadedFile, Environment, ScheduledRecording
from .serializers import TranscriptionSerializer, UploadedFileSerializer, EnvironmentSerializer
from .services.zoom_bot_service import ZoomBotService
from .services.zoom_api_service import ZoomAPIService
from .services.transcription_service import transcribe_and_save
from .tasks import create_scheduled_recording
from pyannote.audio import Pipeline
from pyannote.audio import Audio
import torchaudio
from pyannote.audio.pipelines.utils.hook import ProgressHook
from django.utils import timezone
from rest_framework.renderers import StaticHTMLRenderer
from pydub.silence import detect_nonsilent

# 環境変数をロードする
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ダイアライゼーションのためのモデルをロード
pyannote_auth_token = os.getenv('PYANNOTE_AUTH_TOKEN')

# ロガーを取得
django_logger = logging.getLogger('django')
api_logger = logging.getLogger('api')
processing_logger = logging.getLogger('processing')

@lru_cache(maxsize=1)
def get_whisper_model():
    # オープンソースWhisperモデルのロード
    # GPUを使用する場合
    # device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # CPUを使用するように設定
    device = torch.device("cpu")

    whisper_model = whisper.load_model("small").to(device)

    return whisper_model

@lru_cache(maxsize=1)
def get_diarization_model():
    diarization_model = Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=pyannote_auth_token)
    return diarization_model

def openai_transcribe_with_retry(file_path: str, max_retries: int = 5) -> Optional[dict]:
    """
    OpenAI APIでのレート制限対策付き文字起こし処理

    Args:
        file_path (str): 音声ファイルのパス
        max_retries (int): 最大リトライ回数

    Returns:
        Optional[dict]: 文字起こし結果、失敗時はNone
    """
    for attempt in range(max_retries):
        try:
            # Exponential backoff with jitter
            if attempt > 0:
                base_delay = min(60, 2 ** attempt)  # 最大60秒
                jitter = random.uniform(0.1, 0.5)
                delay = base_delay + jitter
                processing_logger.info(f"リトライ {attempt}/{max_retries}: {delay:.1f}秒待機中...")
                time.sleep(delay)

            # API呼び出し
            with open(file_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ja",
                    response_format="verbose_json"
                )

            # 成功時は結果を返す
            result = {
                "text": response.text,
                "segments": [
                    {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text
                    }
                    for segment in response.segments
                ]
            }

            # レート制限対策：成功した場合も少し待機
            if attempt > 0:  # リトライ後の成功の場合
                time.sleep(1)
            else:  # 初回成功の場合
                time.sleep(0.5)

            return result

        except Exception as e:
            error_str = str(e).lower()

            # 429エラー（レート制限）の場合
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                processing_logger.warning(f"レート制限エラー (attempt {attempt + 1}/{max_retries}): {e}")

                # 最後の試行の場合はNoneを返す
                if attempt == max_retries - 1:
                    processing_logger.error(f"最大リトライ回数に達しました: {file_path}")
                    return None

                # レート制限の場合は長めに待機
                if "quota" in error_str:
                    processing_logger.error(f"クォータ制限に達しました。APIキーと課金設定を確認してください: {e}")
                    return None

                continue

            # その他のエラーの場合
            else:
                processing_logger.error(f"API呼び出しエラー: {e}")
                return None

    processing_logger.error(f"すべてのリトライが失敗しました: {file_path}")
    return None

class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
    permission_classes = []
    lookup_field = 'code'

    @action(detail=False, methods=['post'])
    def update(self, request, *args, **kwargs):
        try:
            instance = Environment.objects.get(code=kwargs['code'])
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except Environment.DoesNotExist:
            # 存在しない場合は新規作成
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(code=kwargs['code'])
            return Response(serializer.data, status=status.HTTP_201_CREATED)

class UploadedFileViewSet(viewsets.ModelViewSet):
    queryset = UploadedFile.objects.all()
    serializer_class = UploadedFileSerializer
    parser_classes = (MultiPartParser, FormParser,)  # ファイルアップロードを許可するパーサーを追加
    permission_classes = [IsAuthenticated] # 認証を要求

    def list(self, request, *args, **kwargs):
        api_logger.info(f"UploadedFile list request: {request.GET}")
        user = request.user  # 現在のユーザーを取得
        organization = user.organization  # ユーザーの組織を取得

        if not organization:
            api_logger.error("organization_idがない")
            return Response({"detail": "不正なリクエストです"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = UploadedFile.objects.all()
        queryset = queryset.filter(organization=organization) # 組織に紐づいたUploadedFileを取得
        queryset = queryset.order_by('-created_at') # 作成日時の降順で取得

        serializer = self.get_serializer(queryset, many=True) # シリアライズ
        response = Response(serializer.data) # json形式でレスポンス

        # レスポンスデータ内のファイル名をデコード
        for item in response.data:
            if 'file' in item and isinstance(item['file'], str):  # itemが辞書であり、fileが存在することを確認
                item['file'] = unquote(item['file'])  # ファイル名をデコード
        response['Content-Type'] = 'application/json; charset=utf-8'

        api_logger.info(f"UploadedFile list response: {response.data}")
        return response

    @action(detail=False, methods=['post'])
    def total_duration(self, request, *args, **kwargs):
        api_logger.info(f"UploadedFile total_duration request: {request.POST}")
        user = request.user
        organization = user.organization

        subscription = organization.get_subscription()
        if subscription and subscription.is_active() and subscription.is_within_contract_period():
            uploaded_files = UploadedFile.objects.filter(
                organization=organization,
                exist=True,
                created_at__gte=subscription.current_period_start,
                created_at__lte=subscription.current_period_end
            )
        else:
            # サブスクリプションがない、または無効な場合は、現在の月でフィルタリング
            now = timezone.now()
            uploaded_files = UploadedFile.objects.filter(
                organization=organization,
                exist=True,
                created_at__year=now.year,
                created_at__month=now.month
            )
        total_duration = sum(uploaded_file.duration or 0 for uploaded_file in uploaded_files)

        # userをget_max_durationに渡すように修正
        max_duration = organization.get_max_duration(user=user)

        # ログ出力
        if user.is_superuser or user.is_staff:
            api_logger.info(f"Admin user {user.username}: Unlimited upload enabled")
        elif os.getenv('TESTING_MODE') == 'true' and os.getenv('TEST_UNLIMITED_UPLOAD') == 'true':
            api_logger.info("Testing mode: Unlimited upload enabled")

        return Response({
            "total_duration": total_duration,
            "max_duration": max_duration
        })

    @action(detail=True, methods=['post'])
    def stream_url(self, request, *args, **kwargs):
        """
        ストリーミング用の一時認証URL生成
        """
        user = request.user
        organization = user.organization

        if not organization:
            return Response({"detail": "不正なリクエストです"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            instance = self.get_object()

            # ユーザーが所属する組織のファイルかチェック
            if instance.organization != organization:
                return Response({"detail": "アクセス権限がありません"}, status=status.HTTP_403_FORBIDDEN)

            # 一時的な署名を生成（30分有効）
            import time
            timestamp = int(time.time())
            expires = timestamp + 1800  # 30分後

            # 署名生成
            secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
            message = f"{instance.id}:{expires}"
            signature = hmac.new(
                secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            # ストリーミングURL生成
            base_url = f"/api/upload-files/stream/{instance.id}/"
            params = urlencode({
                'expires': expires,
                'signature': signature
            })
            stream_url = f"{base_url}?{params}"

            return Response({
                "stream_url": stream_url,
                "expires_at": expires,
                "content_type": mimetypes.guess_type(instance.file.path)[0] or 'application/octet-stream'
            })

        except UploadedFile.DoesNotExist:
            return Response({"detail": "ファイルが見つかりません"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            api_logger.error(f"ストリーミングURL生成中にエラー: {e}")
            return Response({"detail": "内部エラーが発生しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def hls_info(self, request, *args, **kwargs):
        """
        HLS配信情報を取得
        """
        try:
            uploaded_file = self.get_object()

            # ユーザーの組織を確認
            if uploaded_file.organization != request.user.organization:
                return Response({"detail": "アクセス権限がありません"}, status=status.HTTP_403_FORBIDDEN)

            # HLSプレイリストが存在するか確認
            if not uploaded_file.hls_playlist_path:
                return Response({
                    "hls_available": False,
                    "message": "HLS形式はまだ準備されていません"
                })

            # 署名付きURL生成（HLS用）
            import time
            timestamp = int(time.time())
            expires = timestamp + 3600  # 1時間有効

            # 署名生成
            secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
            message = f"hls:{uploaded_file.id}:{expires}"
            signature = hmac.new(
                secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            # HLSマスタープレイリストURL
            hls_url = f"/api/hls-stream/{uploaded_file.id}/master.m3u8?expires={expires}&signature={signature}"

            # 利用可能な品質情報
            qualities = [
                {
                    "name": "360p",
                    "bandwidth": 564000,  # 500k video + 64k audio
                    "resolution": "640x360",
                    "description": "低画質（モバイル向け）"
                },
                {
                    "name": "720p",
                    "bandwidth": 1628000,  # 1500k video + 128k audio
                    "resolution": "1280x720",
                    "description": "高画質（デスクトップ向け）"
                }
            ]

            return Response({
                "hls_available": True,
                "hls_url": hls_url,
                "master_playlist_url": hls_url,
                "expires_at": expires,
                "content_type": "application/x-mpegURL",
                "qualities": qualities
            })

        except UploadedFile.DoesNotExist:
            return Response({"detail": "ファイルが見つかりません"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def stream(self, request, *args, **kwargs):
        """
        署名付きストリーミングエンドポイント（認証不要）
        """
        # 署名検証
        expires = request.GET.get('expires')
        signature = request.GET.get('signature')
        file_id = kwargs.get('pk')

        if not all([expires, signature, file_id]):
            return HttpResponse("Invalid parameters", status=401)

        # 有効期限チェック
        import time
        if int(expires) < int(time.time()):
            return HttpResponse("URL expired", status=401)

        # 署名検証
        secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
        message = f"{file_id}:{expires}"
        expected_signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return HttpResponse("Invalid signature", status=401)

        # ファイル取得と配信
        try:
            instance = UploadedFile.objects.get(id=file_id)
            file_path = instance.file.path

            if not os.path.exists(file_path):
                return HttpResponse("File not found", status=404)

            # Range Request対応
            return self._serve_file_with_range(request, file_path, instance.file.name)

        except UploadedFile.DoesNotExist:
            return HttpResponse("File not found", status=404)
        except Exception as e:
            api_logger.error(f"ストリーミング中にエラー: {e}")
            return HttpResponse("Internal error", status=500)

    def _serve_file_with_range(self, request, file_path, filename):
        """
        Range Request対応のファイル配信
        """
        file_size = os.path.getsize(file_path)
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

        range_header = request.META.get('HTTP_RANGE')
        if range_header:
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

                if start >= file_size:
                    return HttpResponse(status=416)

                end = min(end, file_size - 1)
                content_length = end - start + 1

                with open(file_path, 'rb') as f:
                    f.seek(start)
                    data = f.read(content_length)

                response = HttpResponse(
                    data,
                    status=206,
                    content_type=content_type
                )
                response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                response['Content-Length'] = str(content_length)
                response['Accept-Ranges'] = 'bytes'
                response['Content-Disposition'] = f'inline; filename="{filename}"'
                response['Cache-Control'] = 'no-cache'

                return response

        # 通常のレスポンス
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=False
        )
        response['Content-Length'] = file_size
        response['Accept-Ranges'] = 'bytes'
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Cache-Control'] = 'no-cache'

        return response

    @action(detail=False, methods=['get'])
    def audio(self, request, *args, **kwargs):
        """
        音声・動画ファイルのデータを取得する。
        """
        api_logger.info(f"UploadedFile audio request: {request.GET}")
        user = request.user
        organization = user.organization

        if not organization:
            api_logger.error("organization_idがない")
            return Response({"detail": "不正なリクエストです"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = UploadedFile.objects.filter(organization=organization)
        # UUIDフィールドに対応するため、pkを直接使用
        queryset = queryset.filter(id=kwargs['pk'])

        if not queryset.exists():
            api_logger.error("UploadedFileが見つかりません")
            return Response({"detail": "UploadedFileが見つかりません"}, status=status.HTTP_404_NOT_FOUND)

        instance = queryset.first()

        # ファイルが関連付けられていない場合（録画中など）
        if not instance.file:
            api_logger.info(f"ファイルがまだ関連付けられていません: {instance.id}")
            return Response({"detail": "ファイルがまだ利用できません。録画完了後に再度お試しください。"}, status=status.HTTP_404_NOT_FOUND)

        file_path = instance.file.path

        if not os.path.exists(file_path):
            api_logger.error(f"ファイルが見つかりません: {file_path}")
            return Response({"detail": "ファイルが見つかりません"}, status=status.HTTP_404_NOT_FOUND)

        file_extension = os.path.splitext(file_path)[1].lower()
        supported_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov', '.wmv']

        if file_extension not in supported_extensions:
            api_logger.error(f"サポートされていないファイル形式: {file_extension}")
            return Response({"detail": "サポートされていないファイル形式です"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_size = os.path.getsize(file_path)

            mime_types = {
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.ogg': 'audio/ogg',
                '.m4a': 'audio/mp4',
                '.mp4': 'video/mp4',
                '.avi': 'video/x-msvideo',
                '.mov': 'video/quicktime',
                '.wmv': 'video/x-ms-wmv'
            }
            content_type = mime_types.get(file_extension, 'application/octet-stream')
            filename = os.path.basename(file_path)

            range_header = request.META.get('HTTP_RANGE')
            if range_header:
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

                    if start >= file_size:
                        return HttpResponse(status=416)

                    end = min(end, file_size - 1)
                    content_length = end - start + 1

                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        data = f.read(content_length)

                    response = HttpResponse(
                        data,
                        status=206,
                        content_type=content_type
                    )
                    response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                    response['Content-Length'] = str(content_length)
                    response['Accept-Ranges'] = 'bytes'
                    response['Content-Disposition'] = f'inline; filename="{filename}"'
                    response['Access-Control-Allow-Origin'] = '*'
                    response['Access-Control-Allow-Credentials'] = 'true'
                    response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Range'

                    api_logger.info(f"Range request: {start}-{end}/{file_size} for {filename}")
                    return response

            response = FileResponse(
                open(file_path, 'rb'),
                content_type=content_type,
                as_attachment=False
            )
            response['Content-Length'] = file_size
            response['Accept-Ranges'] = 'bytes'
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
            response['ETag'] = f'"{instance.id}"'
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Range'

            api_logger.info(f"Full file response: {filename} ({file_size} bytes)")
            return response

        except Exception as e:
            api_logger.error(f"ファイル返却中にエラーが発生しました: {e}")
            return Response({"detail": "ファイルの取得に失敗しました"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        api_logger.info(f"UploadedFile create request: {request.POST}")

        # ユーザーを取得
        user = request.user
        organization = user.organization  # ユーザーの組織を取得

        # リクエストデータに組織IDを追加
        request.data['organization_id'] = organization.id

        # 組織IDを取得
        organization_id = request.data.get('organization_id')

        file_serializer = UploadedFileSerializer(data=request.data)
        if file_serializer.is_valid():
            try:
                uploaded_file = file_serializer.save(organization_id=organization_id)

                file_path = uploaded_file.file.path
                if os.path.exists(file_path):
                    file_extension = os.path.splitext(file_path)[1].lower()
                    supported_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov', '.wmv']

                    if file_extension in supported_extensions:
                        processing_logger.info(f"Improving audio index for: {file_path}")
                        improve_audio_index(file_path)

                if uploaded_file.file.name.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov', '.wmv')):
                    duration = get_video_duration(uploaded_file.file.path)
                    if duration is not None:
                        uploaded_file.duration = duration
                        uploaded_file.save()
                        file_serializer = UploadedFileSerializer(uploaded_file)

                # 非同期処理を並列で実行
                try:
                    django_logger.info("Starting async task imports...")
                    from .tasks import transcribe_and_save_async, generate_hls_async
                    django_logger.info("Tasks imported successfully")

                    # 正しいファイルパスを構築
                    file_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.file.name)
                    django_logger.info(f"File path for async tasks: {file_path}")

                    # 文字起こし処理を非同期で実行（全ファイル対象）
                    # HLS変換は文字起こし完了後に自動的に開始されます
                    django_logger.info(f"Queuing transcription task for {uploaded_file.id}")
                    transcribe_result = transcribe_and_save_async.delay(file_path, str(uploaded_file.id))
                    django_logger.info(f"Transcription task queued with ID: {transcribe_result.id}")

                    if uploaded_file.file.name.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm')):
                        django_logger.info(f"HLS conversion will be queued automatically after transcription completes")

                except Exception as task_error:
                    django_logger.error(f"Error queuing async tasks: {task_error}", exc_info=True)

                return Response(file_serializer.data, status=status.HTTP_202_ACCEPTED)

            except Exception as e:
                django_logger.error(f"ファイル保存中にエラーが発生しました: {e}")
                return Response({"error": "ファイルの保存に失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            django_logger.info(f"ファイルアップロードに失敗しました: {file_serializer.errors}")
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def retrieve(self, request, *args, **kwargs):
        api_logger.info(f"UploadedFile retrieve request: {request.GET}")
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        response = Response(serializer.data)
        api_logger.info(f"UploadedFile retrieve response: {response.data}")
        return Response(serializer.data, status=status.HTTP_200_OK)

class TranscriptionViewSet(viewsets.ModelViewSet):
    queryset = Transcription.objects.all()
    serializer_class = TranscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        uploadedfileのIDに基づいてtranscriptionのクエリセットをフィルタリングする。
        """
        api_logger.info(f"TranscriptionViewSet get_queryset request: {self.kwargs}")
        queryset = super().get_queryset().order_by('created_at')
        # URLからuploadedfileのIDを取得するためのキーを修正する
        uploadedfile_id = self.kwargs.get('uploadedfile_id')
        if uploadedfile_id is not None:
            queryset = queryset.filter(uploaded_file__id=uploadedfile_id)
        api_logger.info(f"TranscriptionViewSet get_queryset response: {queryset}")
        return queryset

class TranscriptionSaveViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(detail=False, methods=['post'])
    def save_transcriptions(self, request, *args, **kwargs):
        """
        文字起こし結果を一括で保存するエンドポイント
        """
        api_logger.info(f"TranscriptionSaveViewSet save_transcriptions request: {request.data}")

        try:
            transcriptions = request.data.get('transcriptions')
            uploaded_file_id = request.data.get('uploaded_file_id')

            if not uploaded_file_id:
                return Response(
                    {"error": "uploaded_file_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            for transcription in transcriptions:
                save_transcription(
                    transcription_text = transcription.get('text'),
                    start = transcription.get('start'),
                    uploaded_file_id = uploaded_file_id,
                    speaker = transcription.get('speaker')
                )

            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            result = text_generation_save(uploaded_file)
            if not isinstance(result, UploadedFile):
                raise Exception("テキスト生成に失敗しました")

            # 処理ステータスの更新
            UploadedFile.objects.filter(id=uploaded_file_id).update(
                status = UploadedFile.Status.COMPLETED
            )

            return Response(
                {"message": "Transcriptions saved successfully"},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            api_logger.error(f"Error saving transcriptions: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TranscribeView(View):
    def get(self, request, *args, **kwargs):
        api_logger.info(f"TranscribeView get request: {request.GET}")
        command = TranscribeCommand()
        command.handle()
        api_logger.info(f"TranscribeView get response: {'status': 'transcription started'}")
        return JsonResponse({'status': 'transcription started'})

# FP16に関するワーニングを無視
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

def file_upload_view(request):
    api_logger.info(f"file_upload_view get request: {request.GET}")
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # ファイルの処理
            handle_uploaded_file(request.FILES['file'])
            api_logger.info(f"file_upload_view get response: {'status': 'file uploaded'}")
            return render(request, 'transcription/success.html')  # 成功時のテンプレート
    else:
        form = FileUploadForm()

    api_logger.info(f"file_upload_view get response: {'status': 'file uploaded'}")
    return render(request, 'transcription/upload.html', {'form': form})

def handle_uploaded_file(f):
    api_logger.info(f"handle_uploaded_file get request: {f}")
    # 一時ファイルとして保存
    with open('temp_file', 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

    api_logger.info(f"handle_uploaded_file get response: {'status': 'file uploaded'}")

# 音声ファイルの処理
def process_audio(file_path, file_extension):
    processing_logger.info(f"process_audio get request: {file_path}")
    processing_logger.info(f"process_audio get request: {file_extension}")
    if file_extension == ".wav":
        return file_path, file_extension

    # メモリ効率化のため、大きなファイルは分割処理
    file_size = os.path.getsize(file_path)
    max_chunk_size = 100 * 1024 * 1024  # 100MB

    try:
        if file_size > max_chunk_size:
            # 大きなファイルは分割処理
            return process_large_audio_file(file_path, file_extension)
        else:
            # 通常処理
            return process_normal_audio_file(file_path, file_extension)
    except Exception as e:
        processing_logger.error(f"Audio processing failed: {e}")
        raise

def process_normal_audio_file(file_path, file_extension):
    """通常サイズのファイル処理"""
    # 音声ファイルを読み込む
    audio = AudioSegment.from_file(file_path, format=file_extension.replace(".", ""), frame_rate=16000, sample_width=2, channels=1)
    processing_logger.info(f"audio: {audio}")

    # 音声の正規化
    audio = audio.normalize()

    # ノイズ除去（メモリ使用量を抑制）
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)  # float32で精度を保ちつつメモリ節約

    # CPUのみで動作するように設定（GPUエラーを回避）
    reduced_noise = nr.reduce_noise(
        y=samples,
        sr=audio.frame_rate,
        prop_decrease=0.5,
        time_constant_s=4,
        freq_mask_smooth_hz=500,
        time_mask_smooth_ms=50,
        thresh_n_mult_nonstationary=1.5,
        sigmoid_slope_nonstationary=15,
        n_std_thresh_stationary=1.5,
        clip_noise_stationary=True,
        use_tqdm=False,
        n_jobs=1,
        use_torch=False,  # torchを使用しない
        device="cpu"      # CPUのみ使用
    )

    # 音声データの再構築
    audio = AudioSegment(
        reduced_noise.tobytes(),
        frame_rate=audio.frame_rate,
        sample_width=audio.sample_width,
        channels=audio.channels
    )

    # 新しいファイル名を作成
    new_file_path = file_path.rsplit(".", 1)[0] + ".wav"

    # WAV形式でエクスポート
    try:
        audio.export(new_file_path, format="wav")
    except Exception as e:
        raise RuntimeError(f"ファイルのエクスポートに失敗しました: {e}")

    # 新しいファイルが作成されたか確認
    if not os.path.exists(new_file_path):
        raise FileNotFoundError(f"エクスポートされたファイルが見つかりません: {new_file_path}")

    return new_file_path, ".wav"

def process_large_audio_file(file_path, file_extension):
    """大きなファイルの分割処理"""
    processing_logger.info("Processing large audio file in chunks")

    # 一時的に元のファイルを16kHz WAVに変換（ノイズ除去は省略）
    temp_audio = AudioSegment.from_file(file_path, format=file_extension.replace(".", ""))
    temp_audio = temp_audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    new_file_path = file_path.rsplit(".", 1)[0] + ".wav"
    temp_audio.export(new_file_path, format="wav")

    processing_logger.info(f"Large file converted without noise reduction: {new_file_path}")
    return new_file_path, ".wav"

def millisec(timeStr):
    """
    文字列形式（HH:MM:SS）からミリ秒に変換
    """
    spl = timeStr.split(":")
    s = (int)((int(spl[0]) * 60 * 60 + int(spl[1]) * 60 + float(spl[2])) * 1000)
    return s

def perform_diarization(file_path):
    """
    音声ファイルをダイアライゼーション（話者分離）する。
    """
    pipeline = Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=pyannote_auth_token)

    # オーディオ ファイルをメモリに事前にロードすると、処理が高速化される可能性があります。
    waveform, sample_rate = torchaudio.load(file_path)

    # パイプラインの進行状況を監視
    with ProgressHook() as hook:
        diarization = pipeline({"waveform": waveform, "sample_rate": sample_rate}, hook=hook)

    return diarization

def save_diarization_output(dz):
    """
    ダイアライゼーション（話者分離）の結果を保存する。（テスト用）
    """
    with open("diarization.rttm", "w") as rttm:
        dz.write_rttm(rttm)
    with open("diarization.txt", "w") as text_file:
        text_file.write(str(dz))

def extract_speakers(dz):
    """
    ダイアライゼーションの結果から話者情報を抽出する。
    """
    spacer_milli = 1000
    speakers = set()
    dzList = []
    for line in dz:
        processing_logger.info(f"line: {line}")
        start, end = tuple(re.findall(r'[0-9]+:[0-9]+:[0-9]+\.[0-9]+', string=line))
        processing_logger.info(f"start: {start}")
        processing_logger.info(f"end: {end}")
        start = millisec(start) - spacer_milli
        end = millisec(end) - spacer_milli
        processing_logger.info(f"start: {start}")
        processing_logger.info(f"end: {end}")
        speaker_match = re.findall(r'SPEAKER_\d+', line)
        processing_logger.info(f"speaker_match: {speaker_match}")
        speaker = speaker_match[0] if speaker_match else None
        processing_logger.info(f"speaker: {speaker}")
        speakers.add(speaker)
        processing_logger.info(f"speakers: {speakers}")
        dzList.append([start, end, speaker])
        processing_logger.info(f"dzList: {dzList}")
    return dzList

def save_transcription(transcription_text, start, uploaded_file_id, speaker):
    """
    文字起こし結果を保存する。
    """
    processing_logger.info(f"Saving transcription: start_time={start}, text={transcription_text}, speaker={speaker}")

    try:
        serializer = TranscriptionSerializer(data={
            "start_time": int(start),
            "text": transcription_text,
            "uploaded_file": uploaded_file_id,
            "speaker": speaker,
        })

        if serializer.is_valid():
            serializer.save()
            processing_logger.info(f"Transcription saved successfully: {serializer.data}")
        else:
            processing_logger.error(f"Validation error: {serializer.errors}")

    except Exception as e:
        processing_logger.error(f"Error saving transcription: {e}")

def transcribe_without_diarization(file_path, uploaded_file_id, is_free_user: bool = False):
    """
    話者分離なしで文字起こしを実行する関数
    30秒を超えるまでは1レコードにまとめる

    Args:
        file_path (str): 音声ファイルのパス
        uploaded_file_id (str): アップロードファイルのID
        is_free_user (bool): 無料ユーザーかどうか

    Returns:
        bool: 処理成功時True、失敗時False
    """
    try:
        # pyannoteはwavファイルの方が精度が高いので、wavファイルに変換する
        is_wav_file = True
        temp_file_path = file_path
        file_extension = os.path.splitext(file_path)[1]
        if file_extension != ".wav":
            temp_file_path, file_extension = process_audio(file_path, file_extension)
            is_wav_file = False

        # Whisperで文字起こしを実行
        all_result = transcribe_openai(temp_file_path)

        # 30秒制限でセグメントをまとめる
        segment_limit_time = 30  # 30秒の制限
        temp_threshold_time = segment_limit_time
        temp_segment_transcription_text = ""
        temp_segment_start_time = 0
        temp_segment_speaker = "UNKNOWN_SPEAKER"

        # 文字起こし結果を時間順にソート
        segments = sorted(all_result['segments'], key=lambda x: x['start'])

        for result in segments:
            result_start = int(result['start'])
            result_end = int(result['end'])
            result_text = result['text']

            # 30秒を超える場合、現在のセグメントを保存して新しいセグメントを開始
            if result_end > temp_threshold_time:
                # 現在のセグメントを保存（空でない場合のみ）
                if temp_segment_transcription_text.strip():
                    save_transcription(
                        temp_segment_transcription_text.strip(),
                        temp_segment_start_time,
                        uploaded_file_id,
                        temp_segment_speaker
                    )
                    print(f"[{temp_segment_start_time}s - {temp_threshold_time}s] {temp_segment_speaker}: {temp_segment_transcription_text.strip()}")
                    print("------------------------------------------------------------------------------------------------")

                # 新しいセグメントを開始
                temp_segment_transcription_text = result_text
                temp_segment_start_time = result_start
                temp_threshold_time = result_start + segment_limit_time
            else:
                # 30秒以内の場合は現在のセグメントに追加
                if temp_segment_transcription_text:
                    temp_segment_transcription_text += " " + result_text
                else:
                    temp_segment_transcription_text = result_text
                    temp_segment_start_time = result_start

        # 最後のセグメントが残っている場合は保存
        if temp_segment_transcription_text.strip():
            save_transcription(
                temp_segment_transcription_text.strip(),
                temp_segment_start_time,
                uploaded_file_id,
                temp_segment_speaker
            )
            print(f"[{temp_segment_start_time}s - {temp_threshold_time}s] {temp_segment_speaker}: {temp_segment_transcription_text.strip()}")
            print("------------------------------------------------------------------------------------------------")

        # ファイルを削除
        if not is_wav_file:
            os.remove(temp_file_path)

        return True

    except Exception as e:
        processing_logger.error(f"文字起こしでエラーが発生しました: {e}")
        return False

def get_file_size_mb(file_path: str) -> float:
    """
    ファイルサイズをMB単位で取得する。

    Args:
        file_path (str): ファイルパス

    Returns:
        float: ファイルサイズ（MB）
    """
    return os.path.getsize(file_path) / (1024 * 1024)

def find_silence_points(audio: AudioSegment, min_silence_len: int = 1000, silence_thresh: int = -40) -> list:
    """
    音声ファイル内の無音区間を検出して分割ポイントを取得する。

    Args:
        audio (AudioSegment): 音声データ
        min_silence_len (int): 最小無音長（ミリ秒）
        silence_thresh (int): 無音判定の閾値（dB）

    Returns:
        list: 分割ポイントのリスト（ミリ秒）
    """
    # 無音区間を検出
    silence_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )

    # 無音区間の開始点を分割ポイントとして使用
    split_points = []
    for start, end in silence_ranges:
        # 無音区間の中央を分割ポイントとする
        split_point = (start + end) // 2
        split_points.append(split_point)

    return split_points

def split_audio_file(file_path: str, max_size_mb: float = 24.0) -> list:
    """
    音声ファイルを25MB制限に合わせて分割する。

    Args:
        file_path (str): 音声ファイルのパス
        max_size_mb (float): 最大ファイルサイズ（MB）

    Returns:
        list: 分割されたファイルパスのリスト
    """
    try:
        # ファイルサイズをチェック
        file_size_mb = get_file_size_mb(file_path)
        if file_size_mb <= max_size_mb:
            # 25MB以下なら分割不要
            return [file_path]

        # 音声ファイルを読み込み
        audio = AudioSegment.from_file(file_path)
        total_duration_ms = len(audio)

        # より効率的な分割ロジック
        # ファイルサイズと時間の比率から適切な分割時間を計算
        target_chunk_duration_ms = int((max_size_mb / file_size_mb) * total_duration_ms * 0.9)  # 安全マージン

        # 最小分割時間を設定（30秒 = 30000ms）
        min_chunk_duration_ms = 30000
        if target_chunk_duration_ms < min_chunk_duration_ms:
            target_chunk_duration_ms = min_chunk_duration_ms

        # 無音区間を検出して分割ポイントを取得
        silence_points = find_silence_points(audio)

        split_files = []
        temp_dir = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        start_time = 0
        chunk_index = 0

        while start_time < total_duration_ms:
            # チャンクの終了時間を計算
            end_time = min(start_time + target_chunk_duration_ms, total_duration_ms)

            # 無音区間を優先して分割ポイントを調整
            best_silence_point = None
            for silence_point in silence_points:
                if start_time < silence_point < end_time:
                    # 終了時間に近い無音区間を選択
                    if best_silence_point is None or abs(silence_point - end_time) < abs(best_silence_point - end_time):
                        best_silence_point = silence_point

            if best_silence_point:
                end_time = best_silence_point

            # 音声を分割
            chunk = audio[start_time:end_time]

            # 分割ファイルのパスを生成
            chunk_path = os.path.join(temp_dir, f"{base_name}_chunk_{chunk_index:03d}.wav")

            # 分割ファイルを保存
            chunk.export(chunk_path, format="wav")

            # ファイルサイズをチェック
            chunk_size_mb = get_file_size_mb(chunk_path)
            if chunk_size_mb > max_size_mb:
                # ファイルサイズが大きすぎる場合は削除して再分割
                os.remove(chunk_path)
                # より小さく分割（現在のチャンクをさらに分割）
                sub_chunks = split_audio_file(chunk_path, max_size_mb)
                split_files.extend(sub_chunks)
            else:
                split_files.append(chunk_path)

            start_time = end_time
            chunk_index += 1

            # 無限ループ防止
            if chunk_index > 50:  # より現実的な上限
                processing_logger.error("音声ファイルの分割が無限ループに陥りました")
                break

        processing_logger.info(f"音声ファイルを{len(split_files)}個に分割しました（予想: {int(file_size_mb / max_size_mb) + 1}個）")
        return split_files

    except Exception as e:
        processing_logger.error(f"音声ファイルの分割中にエラーが発生しました: {e}")
        return [file_path]

def merge_transcription_results(results: list, time_offsets: list) -> dict:
    """
    分割された文字起こし結果を結合する。

    Args:
        results (list): 各分割ファイルの文字起こし結果のリスト
        time_offsets (list): 各分割ファイルの時間オフセットのリスト

    Returns:
        dict: 結合された文字起こし結果
    """
    merged_segments = []

    for i, (result, time_offset) in enumerate(zip(results, time_offsets)):
        if not result or 'segments' not in result:
            continue

        for segment in result['segments']:
            # 時間を調整
            adjusted_segment = segment.copy()
            adjusted_segment['start'] = segment['start'] + time_offset
            adjusted_segment['end'] = segment['end'] + time_offset
            merged_segments.append(adjusted_segment)

    # 時間順にソート
    merged_segments.sort(key=lambda x: x['start'])

    # 結合されたテキストを作成
    merged_text = ' '.join(segment['text'] for segment in merged_segments)

    return {
        'text': merged_text,
        'segments': merged_segments
    }

def transcribe_openai(file_path: str) -> dict:
    """
    OpenAIのAPIを使用して音声ファイルを文字起こしする。
    25MB制限を超える場合は自動的に分割して処理する。

    Args:
        file_path (str): 音声ファイルのパス

    Returns:
        dict: 文字起こし結果
    """
    try:
        # ファイルサイズをチェック
        file_size_mb = get_file_size_mb(file_path)

        if file_size_mb <= 24.0:  # 安全マージンとして24MB以下
            # 25MB以下なら通常通り処理（レート制限対策付き）
            result = openai_transcribe_with_retry(file_path)
            if result is None:
                raise Exception("OpenAI APIでの文字起こしに失敗しました")
            return result
        else:
            # 25MBを超える場合は分割処理
            processing_logger.info(f"ファイルサイズが{file_size_mb:.2f}MBのため、分割処理を実行します")

            # 音声ファイルを分割
            split_files = split_audio_file(file_path)
            processing_logger.info(f"音声ファイルを{len(split_files)}個に分割しました")

            if len(split_files) == 1:
                # 分割できなかった場合は通常処理（レート制限対策付き）
                result = openai_transcribe_with_retry(file_path)
                if result is None:
                    raise Exception("OpenAI APIでの文字起こしに失敗しました")
                return result

            # 各分割ファイルを処理
            results = []
            time_offsets = []
            audio = AudioSegment.from_file(file_path)

            failed_files = []

            for i, split_file in enumerate(split_files):
                try:
                    processing_logger.info(f"分割ファイル {i+1}/{len(split_files)} を処理中...")

                    # レート制限対策付きで分割ファイルの文字起こし
                    result_dict = openai_transcribe_with_retry(split_file)

                    if result_dict is None:
                        processing_logger.error(f"分割ファイル {split_file} の文字起こしに失敗しました")
                        failed_files.append(split_file)
                        continue

                    # 時間オフセットを計算
                    split_audio = AudioSegment.from_file(split_file)
                    time_offset = len(audio[:len(audio) * i // len(split_files)]) / 1000.0

                    results.append(result_dict)
                    time_offsets.append(time_offset)

                    processing_logger.info(f"分割ファイル {i+1}/{len(split_files)} の処理が完了しました")

                except Exception as e:
                    processing_logger.error(f"分割ファイル {split_file} の処理中にエラーが発生しました: {e}")
                    failed_files.append(split_file)
                finally:
                    # 一時ファイルを削除
                    if os.path.exists(split_file):
                        os.remove(split_file)

            # 結果の処理
            if results:
                if failed_files:
                    processing_logger.warning(f"分割ファイルのうち {len(failed_files)}/{len(split_files)} 個の処理に失敗しました")
                    processing_logger.warning(f"成功: {len(results)}/{len(split_files)} 個のファイル")

                merged_result = merge_transcription_results(results, time_offsets)
                processing_logger.info("分割された文字起こし結果を結合しました")
                return merged_result
            else:
                processing_logger.error("すべての分割ファイルの処理に失敗しました")
                processing_logger.error("対処方法: 1) OpenAI APIキーを確認 2) 課金設定を確認 3) 使用量制限を確認")
                return {"text": "", "segments": []}

    except Exception as e:
        processing_logger.error(f"OpenAIで文字起こしに失敗しました: {e}")
        return {"text": "", "segments": []}

@transaction.atomic
def text_generation_save(uploaded_file: UploadedFile) -> Union[UploadedFile, bool]:
    """
    文字起こし結果を分析して、要約・課題・取り組み案を保存する。

    Args:
        uploaded_file (UploadedFile): UploadedFileのインスタンス

    Returns:
        UploadedFile | bool: 成功した場合はUploadedFileのインスタンス、失敗した場合はFalse
    """
    processing_logger.info(f"summarize_and_save が呼び出されました。uploaded_file_id: {uploaded_file.id}")

    try:
        uploaded_file = UploadedFile.objects.select_for_update().get(id=uploaded_file.id)
        transcriptions = uploaded_file.transcription.all()

        if not transcriptions.exists():
            processing_logger.warning(f"文字起こしデータがありません。uploaded_file_id: {uploaded_file.id}")
            return False

        all_transcription_text = "".join(transcription.text for transcription in transcriptions)

        summary_text = summarize_text(all_transcription_text)
        uploaded_file.summarization = summary_text
        uploaded_file.issue = definition_issue(all_transcription_text)
        uploaded_file.solution = definition_solution(all_transcription_text)
        uploaded_file.save()

        return uploaded_file
    except Exception as e:
        processing_logger.error(f"summarize_and_save でエラーが発生しました: {e}")
        return False

def remove_markdown_blocks(text: str) -> str:
    """
    Markdown ブロックを除去する。

    Args:
        text (str): 処理対象のテキスト
    Returns:
        str: Markdown ブロックを除去したテキスト
    """
    result = text
    if result.startswith("```markdown\n"):
        result = result[12:]
    if result.endswith("\n```"):
        result = result[:-4]
    return result.strip()

def summarize_text(text: str) -> str:
    """
    テキストを要約する。

    Args:
        text (str): 要約するテキスト
    Returns:
        str: マークダウン形式で要約されたテキスト
    """
    return summarize_text_with_instruction(text, "")

def definition_issue(text: str) -> str:
    """
    テキストを分析し、主要な課題点を特定する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: マークダウン形式で主要な課題点
    """
    return definition_issue_with_instruction(text, "")

def definition_solution(text: str) -> str:
    """
    テキストを分析し、取り組み案を特定する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: マークダウン形式で取り組み案
    """
    return definition_solution_with_instruction(text, "")

def create_meeting_minutes(text: str) -> str:
    """
    テキストを分析し、議事録を作成する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: マークダウン形式で議事録
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、議事録を作成する専門家です。応答は必ずマークダウン形式で出力してください。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、マークダウン形式で議事録を作成してください：\\n\\n{text}"}
            ],
            max_tokens=1500  # 応答の最大長を制限（詳細な構造化出力のため増量）
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"議事録作成中にエラーが発生しました: {e}")
        return "議事録作成に失敗しました。"

def summarize_text_with_instruction(text: str, instruction: str = "") -> str:
    """
    カスタム指示付きでテキストを要約する。

    Args:
        text (str): 要約するテキスト
        instruction (str): カスタム指示
    Returns:
        str: マークダウン形式で要約されたテキスト
    """
    try:
        base_prompt = "あなたは会議内容を分析し、包括的な要約を作成する専門家です。応答は必ずマークダウン形式で、構造化された内容で出力してください。"
        user_prompt = f"""以下の会議内容を分析し、マークダウン形式で要約を作成してください。

以下の構造で出力してください：
# 会議要約

## 会議概要
（会議の目的と全体的な内容を2-3文で要約）

## 主要な議題
1. **議題名**: 内容の説明
2. **議題名**: 内容の説明
（必要に応じて追加）

## 決定事項
- 具体的な決定内容
- 承認された事項
（箇条書きで列挙）

## 次回アクション
今後の取り組みや次回までのアクションアイテムを記載

会議内容：
{text}"""

        if instruction.strip():
            user_prompt += f"\n\n追加の指示: {instruction}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"テキスト要約中にエラーが発生しました: {e}")
        return "要約に失敗しました。"

def definition_issue_with_instruction(text: str, instruction: str = "") -> str:
    """
    カスタム指示付きでテキストを分析し、主要な課題点を特定する。

    Args:
        text (str): 分析するテキスト
        instruction (str): カスタム指示
    Returns:
        str: マークダウン形式で主要な課題点
    """
    try:
        base_prompt = "あなたは会議内容を分析し、重要度別に課題を特定・分類する専門家です。応答は必ずマークダウン形式で出力してください。"
        user_prompt = f"""以下の会議内容を分析し、重要度別に課題を特定してマークダウン形式で出力してください。

以下の構造で出力してください：
# 特定された課題

## 緊急度の高い課題

### 1. 課題名
- **問題**: 具体的な問題の説明
- **影響**: この課題が与える影響
- **期限**: 対応期限（判明している場合）

## 中程度の課題

### 2. 課題名
- **問題**: 具体的な問題の説明
- **影響**: この課題が与える影響
- **対応**: 必要な対応策

## 軽微な課題

### 3. 課題名
- **問題**: 具体的な問題の説明
- **影響**: この課題が与える影響
- **対応**: 推奨される対応策

会議内容：
{text}"""

        if instruction.strip():
            user_prompt += f"\n\n追加の指示: {instruction}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"

def definition_solution_with_instruction(text: str, instruction: str = "") -> str:
    """
    カスタム指示付きでテキストを分析し、取り組み案を特定する。

    Args:
        text (str): 分析するテキスト
        instruction (str): カスタム指示
    Returns:
        str: マークダウン形式で取り組み案
    """
    try:
        base_prompt = "あなたは会議内容を分析し、実行可能な改善施策を時間軸別に提案する専門家です。応答は必ずマークダウン形式で出力してください。"
        user_prompt = f"""以下の会議内容を分析し、改善提案・取り組み案をマークダウン形式で出力してください。

以下の構造で出力してください：
# 改善提案・取り組み案

## 重点的な取り組み

### 1. 施策名
**目標**: 達成したい目標
- **短期施策**:
  - 具体的なアクション1
  - 具体的なアクション2
- **中期施策**:
  - 中期的な取り組み1
  - 中期的な取り組み2
- **期待効果**: 期待される成果

## プロセス改善

### 2. 改善施策名
**目標**: 達成したい目標
- **具体的施策**:
  - 実施すべき項目1
  - 実施すべき項目2
- **ツール活用**:
  - 活用するツールや仕組み
- **期待効果**: 期待される成果

## 継続的改善

### 3. 長期戦略名
**目標**: 長期的な目標
- **教育・研修**:
  - 実施する教育施策
- **組織改善**:
  - 組織レベルでの改善
- **期待効果**: 期待される成果

会議内容：
{text}"""

        if instruction.strip():
            user_prompt += f"\n\n追加の指示: {instruction}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"

class RegenerateAnalysisViewSet(viewsets.ViewSet):
    """
    AI分析結果の再生成を行うViewSet
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='summary')
    def regenerate_summary(self, request):
        """要約の再生成"""
        try:
            uploaded_file_id = request.data.get('uploaded_file_id')
            instruction = request.data.get('instruction', '')

            if not uploaded_file_id:
                return Response(
                    {"error": "uploaded_file_idが必要です"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = request.user
            organization = user.organization

            try:
                uploaded_file = UploadedFile.objects.get(
                    id=uploaded_file_id,
                    organization=organization
                )
            except UploadedFile.DoesNotExist:
                return Response(
                    {"error": "ファイルが見つかりません"},
                    status=status.HTTP_404_NOT_FOUND
                )

            transcriptions = uploaded_file.transcription.all().order_by('start_time')
            if not transcriptions.exists():
                return Response(
                    {"error": "文字起こしデータがありません"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            all_transcription_text = "".join(transcription.text for transcription in transcriptions)

            summary_text = summarize_text_with_instruction(all_transcription_text, instruction)
            uploaded_file.summarization = summary_text
            uploaded_file.save()

            return Response({
                "message": "要約が再生成されました",
                "summary": summary_text
            }, status=status.HTTP_200_OK)

        except Exception as e:
            processing_logger.error(f"要約再生成中にエラーが発生しました: {e}")
            return Response(
                {"error": "要約の再生成に失敗しました"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='issues')
    def regenerate_issues(self, request):
        """課題の再生成"""
        try:
            uploaded_file_id = request.data.get('uploaded_file_id')
            instruction = request.data.get('instruction', '')

            if not uploaded_file_id:
                return Response(
                    {"error": "uploaded_file_idが必要です"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = request.user
            organization = user.organization

            try:
                uploaded_file = UploadedFile.objects.get(
                    id=uploaded_file_id,
                    organization=organization
                )
            except UploadedFile.DoesNotExist:
                return Response(
                    {"error": "ファイルが見つかりません"},
                    status=status.HTTP_404_NOT_FOUND
                )

            transcriptions = uploaded_file.transcription.all().order_by('start_time')
            if not transcriptions.exists():
                return Response(
                    {"error": "文字起こしデータがありません"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            all_transcription_text = "".join(transcription.text for transcription in transcriptions)

            issue_text = definition_issue_with_instruction(all_transcription_text, instruction)
            uploaded_file.issue = issue_text
            uploaded_file.save()

            return Response({
                "message": "課題が再生成されました",
                "issues": issue_text
            }, status=status.HTTP_200_OK)

        except Exception as e:
            processing_logger.error(f"課題再生成中にエラーが発生しました: {e}")
            return Response(
                {"error": "課題の再生成に失敗しました"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='solutions')
    def regenerate_solutions(self, request):
        """取り組み案の再生成"""
        try:
            uploaded_file_id = request.data.get('uploaded_file_id')
            instruction = request.data.get('instruction', '')

            if not uploaded_file_id:
                return Response(
                    {"error": "uploaded_file_idが必要です"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = request.user
            organization = user.organization

            try:
                uploaded_file = UploadedFile.objects.get(
                    id=uploaded_file_id,
                    organization=organization
                )
            except UploadedFile.DoesNotExist:
                return Response(
                    {"error": "ファイルが見つかりません"},
                    status=status.HTTP_404_NOT_FOUND
                )

            transcriptions = uploaded_file.transcription.all().order_by('start_time')
            if not transcriptions.exists():
                return Response(
                    {"error": "文字起こしデータがありません"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            all_transcription_text = "".join(transcription.text for transcription in transcriptions)

            solution_text = definition_solution_with_instruction(all_transcription_text, instruction)
            uploaded_file.solution = solution_text
            uploaded_file.save()

            return Response({
                "message": "取り組み案が再生成されました",
                "solutions": solution_text
            }, status=status.HTTP_200_OK)

        except Exception as e:
            processing_logger.error(f"取り組み案再生成中にエラーが発生しました: {e}")
            return Response(
                {"error": "取り組み案の再生成に失敗しました"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

def get_video_duration(file_path: str) -> float:
    """
    動画・音声ファイルの再生時間を取得する。

    Args:
        file_path (str): 動画・音声ファイルのパス

    Returns:
        float: 再生時間（秒）
    """
    try:
        if file_path.endswith(('.mp3', '.wav', '.ogg', '.m4a')):
            # 音声ファイルの場合
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000.0  # ミリ秒を秒に変換
            return duration
        elif file_path.endswith(('.mp4', '.avi', '.mov', '.wmv')):
            # 動画ファイルの場合
            video = VideoFileClip(file_path)
            duration = video.duration
            video.close()
            return duration
        else:
            return None
    except Exception as e:
        processing_logger.error(f"ファイルの再生時間取得中にエラーが発生しました: {e}")
        return None


def improve_audio_index(file_path: str) -> bool:
    """
    音声・動画ファイルのインデックス情報を改善してシーク精度を向上させる。
    元のファイル形式は変更せず、メタデータのみを最適化する。

    Args:
        file_path (str): 音声・動画ファイルのパス

    Returns:
        bool: 成功した場合True、失敗した場合False
    """
    try:
        import subprocess

        file_extension = os.path.splitext(file_path)[1].lower()
        temp_path = file_path + '.tmp'

        if file_extension in ['.mp3']:
            cmd = [
                'ffmpeg', '-i', file_path,
                '-c', 'copy',
                '-write_xing', '1',
                '-f', 'mp3',
                '-y', temp_path
            ]
        elif file_extension in ['.m4a', '.mp4']:
            cmd = [
                'ffmpeg', '-i', file_path,
                '-c', 'copy',
                '-movflags', 'faststart',
                '-f', 'mp4' if file_extension == '.mp4' else 'ipod',
                '-y', temp_path
            ]
        elif file_extension in ['.wav']:
            cmd = [
                'ffmpeg', '-i', file_path,
                '-c', 'copy',
                '-f', 'wav',
                '-y', temp_path
            ]
        elif file_extension in ['.ogg']:
            cmd = [
                'ffmpeg', '-i', file_path,
                '-c', 'copy',
                '-f', 'ogg',
                '-y', temp_path
            ]
        elif file_extension in ['.avi', '.mov', '.wmv']:
            cmd = [
                'ffmpeg', '-i', file_path,
                '-c', 'copy',
                '-movflags', 'faststart',
                '-f', 'mp4' if file_extension == '.avi' else 'mov',
                '-y', temp_path
            ]
        else:
            processing_logger.warning(f"Unsupported format for index improvement: {file_extension}")
            return False

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            os.replace(temp_path, file_path)
            processing_logger.info(f"Audio index improved for: {file_path}")
            return True
        else:
            processing_logger.error(f"ffmpeg failed for {file_path}: {result.stderr}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    except Exception as e:
        processing_logger.error(f"Error improving audio index for {file_path}: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        return False

# Zoom会議録画用API Views
from rest_framework.decorators import api_view

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_zoom_meeting_url(request):
    """Zoom会議URLの妥当性を検証"""
    try:
        processing_logger.info(f"Validate URL request data: {request.data}")

        # フロントエンドから送信される可能性のある両方のフィールド名を確認
        meeting_url = request.data.get('meeting_url') or request.data.get('meetingUrl')
        processing_logger.info(f"Extracted meeting_url: {meeting_url}")

        if not meeting_url:
            return Response({
                'error': 'meeting_urlが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)

        zoom_service = ZoomBotService()
        result = zoom_service.validate_meeting_url(meeting_url)

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"URL validation error: {e}")
        return Response({
            'error': 'URL validation failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_zoom_recording(request):
    """Zoom会議録画開始"""
    try:
        meeting_url = request.data.get('meeting_url') or request.data.get('meetingUrl')
        user_name = request.data.get('user_name')

        if not meeting_url:
            return Response({
                'error': 'meeting_urlが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        organization_id = user.organization.id

        zoom_service = ZoomBotService()
        result = zoom_service.start_meeting_recording(
            meeting_url,
            organization_id,
            user_name
        )

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Recording start error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_zoom_recording(request):
    """Zoom会議録画停止"""
    try:
        uploaded_file_id = request.data.get('uploaded_file_id')

        if not uploaded_file_id:
            return Response({
                'error': 'uploaded_file_idが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        organization = user.organization

        # 権限チェック
        try:
            uploaded_file = UploadedFile.objects.get(
                id=uploaded_file_id,
                organization=organization
            )
        except UploadedFile.DoesNotExist:
            return Response({
                'error': 'ファイルが見つかりません'
            }, status=status.HTTP_404_NOT_FOUND)

        zoom_service = ZoomBotService()
        result = zoom_service.stop_meeting_recording(uploaded_file_id)

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Recording stop error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_zoom_recording_status(request, uploaded_file_id):
    """Zoom会議録画状態取得"""
    try:
        user = request.user
        organization = user.organization

        # 権限チェック
        try:
            uploaded_file = UploadedFile.objects.get(
                id=uploaded_file_id,
                organization=organization
            )
        except UploadedFile.DoesNotExist:
            return Response({
                'error': 'ファイルが見つかりません'
            }, status=status.HTTP_404_NOT_FOUND)

        zoom_service = ZoomBotService()
        result = zoom_service.get_recording_status(uploaded_file_id)

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Status check error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_zoom_recordings(request):
    """アクティブなZoom会議録画一覧取得"""
    try:
        zoom_service = ZoomBotService()
        recordings = zoom_service.get_all_active_recordings()

        return Response({
            'success': True,
            'recordings': recordings,
            'count': len(recordings)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Active recordings check error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 予約録画用APIエンドポイント

@api_view(['POST'])
def get_meeting_details(request):
    """会議URLから詳細情報を取得"""
    try:
        meeting_url = request.data.get('meetingUrl')
        if not meeting_url:
            return Response({
                'error': 'meetingUrl is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        zoom_api = ZoomAPIService()
        meeting_details = zoom_api.parse_meeting_url_advanced(meeting_url)

        return Response({
            'success': True,
            'meeting_details': meeting_details
        }, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Meeting details fetch error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def schedule_zoom_recording(request):
    """Zoom会議録画を予約"""
    try:
        meeting_url = request.data.get('meetingUrl')
        scheduled_start_time = request.data.get('scheduledStartTime')

        if not meeting_url or not scheduled_start_time:
            return Response({
                'error': 'meetingUrl and scheduledStartTime are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 日時をパース
        from datetime import datetime
        try:
            scheduled_time = datetime.fromisoformat(scheduled_start_time.replace('Z', '+00:00'))
        except ValueError:
            return Response({
                'error': 'Invalid scheduledStartTime format'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 過去の時刻チェック
        from django.utils import timezone
        if scheduled_time <= timezone.now():
            return Response({
                'error': 'Scheduled time must be in the future'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ユーザーオプション
        user_options = {
            'pre_recording_minutes': request.data.get('preRecordingMinutes', 5),
            'post_recording_minutes': request.data.get('postRecordingMinutes', 10),
            'auto_start': request.data.get('autoStart', True),
            'auto_stop': request.data.get('autoStop', True)
        }

        # 予約録画作成
        result = create_scheduled_recording.delay(
            meeting_url=meeting_url,
            organization_id=request.user.organization.id,
            scheduled_start_time=scheduled_time,
            user_options=user_options
        ).get()

        if result['success']:
            return Response({
                'success': True,
                'scheduled_recording_id': result['scheduled_recording_id'],
                'uploaded_file_id': result['uploaded_file_id'],
                'meeting_details': result['meeting_details']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': result['error']
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        processing_logger.error(f"Schedule recording error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scheduled_recordings(request):
    """予約録画一覧を取得"""
    try:
        user = request.user
        organization = user.organization

        # 組織のすべての予約録画を取得
        scheduled_recordings = ScheduledRecording.objects.filter(
            uploaded_file__organization=organization
        ).select_related('uploaded_file').order_by('-created_at')

        recordings_data = []
        for recording in scheduled_recordings:
            recordings_data.append({
                'id': str(recording.id),
                'uploaded_file_id': str(recording.uploaded_file.id),
                'meeting_topic': recording.meeting_topic,
                'meeting_id': recording.meeting_id,
                'meeting_url': recording.meeting_url,
                'scheduled_start_time': recording.scheduled_start_time,
                'scheduled_end_time': recording.scheduled_end_time,
                'status': recording.status,
                'recording_type': recording.recording_type,
                'estimated_duration': recording.estimated_duration,
                'actual_start_time': recording.actual_start_time,
                'actual_end_time': recording.actual_end_time,
                'error_message': recording.error_message,
                'created_at': recording.created_at,
                'can_cancel': recording.can_cancel,
                'time_until_start': recording.get_time_until_start(),
                'formatted_schedule': recording.get_formatted_schedule()
            })

        return Response({
            'success': True,
            'recordings': recordings_data,
            'count': len(recordings_data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Get scheduled recordings error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json

@csrf_exempt
def recording_completed(request):
    """Zoom録画完了通知を受け取る"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # トークン検証（シンプルな共有トークン方式）
    auth_header = request.headers.get('Authorization', '')
    expected_token = f'Bearer {os.environ.get("DJANGO_API_TOKEN", "zoom-bot-secret-token")}'
    if auth_header != expected_token:
        processing_logger.warning(f"Invalid authorization token: {auth_header}, expected: {expected_token}")
        return JsonResponse({'error': 'Invalid authorization'}, status=401)

    try:
        data = json.loads(request.body)
        session_id = data.get('sessionId')
        uploaded_file_id = data.get('uploadedFileId')
        audio_file_path = data.get('audioFile')
        meeting_number = data.get('meetingNumber')
        duration = data.get('duration', 0)

        # UploadedFileを取得
        uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)

        # 既に処理済みの場合はスキップ（冪等性の確保）
        if uploaded_file.file and uploaded_file.status == UploadedFile.Status.COMPLETED:
            processing_logger.info(f"Recording {uploaded_file_id} already processed, skipping")
            return JsonResponse({
                'success': True,
                'message': 'Recording already processed',
                'already_processed': True
            })

        # 音声ファイルをコピー
        container_path = audio_file_path
        host_path = os.path.join(settings.MEDIA_ROOT, 'zoom_recordings', f'{session_id}_audio.wav')

        # ディレクトリを作成
        os.makedirs(os.path.dirname(host_path), exist_ok=True)

        # ボリュームマッピングを使用して直接アクセス
        # container_pathをホストパスに変換
        container_file_name = os.path.basename(container_path)
        container_dir_name = os.path.basename(os.path.dirname(container_path))
        source_path = os.path.join(settings.MEDIA_ROOT, 'zoom_recordings', container_dir_name, container_file_name)

        # ファイルをコピー
        import shutil
        if os.path.exists(source_path):
            shutil.copy2(source_path, host_path)
            processing_logger.info(f"Audio file copied from {source_path} to {host_path}")
        else:
            processing_logger.warning(f"Source audio file not found: {source_path}")

        # UploadedFileを更新
        uploaded_file.file = f'zoom_recordings/{session_id}_audio.wav'
        uploaded_file.duration = duration
        uploaded_file.is_processing = False
        uploaded_file.status = UploadedFile.Status.COMPLETED
        uploaded_file.save()

        # 文字起こしタスクを開始
        from .tasks.tasks import transcribe_and_save_async, generate_hls_async
        import os

        # 正しいファイルパスを構築
        file_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.file.name)

        processing_logger.info(f"Starting transcription for: {uploaded_file.id}")
        transcribe_and_save_async.delay(file_path, str(uploaded_file.id))

        # HLS変換タスクを開始
        processing_logger.info(f"Starting HLS generation for: {uploaded_file.id}")
        generate_hls_async.delay(str(uploaded_file.id))

        return JsonResponse({
            'success': True,
            'message': 'Recording completed and processing started'
        })

    except UploadedFile.DoesNotExist:
        return JsonResponse({'error': 'UploadedFile not found'}, status=404)
    except Exception as e:
        processing_logger.error(f"Recording completion error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def create_uploaded_file_record(request):
    """Node.js側からUploadedFileレコードを作成"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # トークン検証
    auth_header = request.headers.get('Authorization', '')
    expected_token = f'Bearer {os.environ.get("DJANGO_API_TOKEN", "zoom-bot-secret-token")}'
    if auth_header != expected_token:
        return JsonResponse({'error': 'Invalid authorization'}, status=401)

    try:
        data = json.loads(request.body)
        meeting_url = data.get('meetingUrl')
        meeting_number = data.get('meetingNumber')
        session_id = data.get('sessionId')

        if not meeting_url or not meeting_number or not session_id:
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        # デフォルトのorganization_idを使用（実際のプロジェクトでは適切に設定する必要があります）
        from django.contrib.auth import get_user_model
        User = get_user_model()
        default_user = User.objects.first()
        if not default_user:
            return JsonResponse({'error': 'No users found'}, status=500)

        # UploadedFileレコードを作成
        uploaded_file = UploadedFile.objects.create(
            organization_id=default_user.organization.id,
            file='',  # 後で更新
            status=UploadedFile.Status.PROCESSING,
            source_type='zoom_meeting',
            meeting_url=meeting_url,
            meeting_number=meeting_number,
            zoom_session_id=session_id,
            recording_start_time=timezone.now()
        )

        return JsonResponse({
            'id': str(uploaded_file.id),
            'success': True,
            'message': 'UploadedFile record created successfully'
        })

    except Exception as e:
        processing_logger.error(f"UploadedFile creation error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
def cancel_scheduled_recording(request):
    """予約録画をキャンセル"""
    try:
        recording_id = request.data.get('recordingId')
        cancel_reason = request.data.get('reason', 'ユーザーによるキャンセル')

        if not recording_id:
            return Response({
                'error': 'recordingId is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        organization = user.organization

        try:
            recording = ScheduledRecording.objects.get(
                id=recording_id,
                uploaded_file__organization=organization
            )
        except ScheduledRecording.DoesNotExist:
            return Response({
                'error': 'Scheduled recording not found'
            }, status=status.HTTP_404_NOT_FOUND)

        if not recording.can_cancel:
            return Response({
                'error': 'Cannot cancel this recording'
            }, status=status.HTTP_400_BAD_REQUEST)

        recording.cancel(cancel_reason)

        return Response({
            'success': True,
            'message': 'Recording cancelled successfully'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Cancel scheduled recording error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_scheduled_recording_status(request, recording_id):
    """予約録画の状態を取得"""
    try:
        user = request.user
        organization = user.organization

        try:
            recording = ScheduledRecording.objects.get(
                id=recording_id,
                uploaded_file__organization=organization
            )
        except ScheduledRecording.DoesNotExist:
            return Response({
                'error': 'Scheduled recording not found'
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'recording': {
                'id': str(recording.id),
                'status': recording.status,
                'meeting_topic': recording.meeting_topic,
                'scheduled_start_time': recording.scheduled_start_time,
                'actual_start_time': recording.actual_start_time,
                'actual_end_time': recording.actual_end_time,
                'error_message': recording.error_message,
                'can_cancel': recording.can_cancel,
                'time_until_start': recording.get_time_until_start(),
                'recording_window': recording.recording_window
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        processing_logger.error(f"Get scheduled recording status error: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
