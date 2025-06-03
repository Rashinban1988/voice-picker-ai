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
from moviepy.editor import VideoFileClip
# import wave

import numpy as np
import noisereduce as nr
from functools import lru_cache
# from celery import shared_task
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views import View
from dotenv import load_dotenv
from pydub import AudioSegment
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.views.decorators.csrf import csrf_exempt
from typing import Union
from urllib.parse import unquote
from vosk import KaldiRecognizer, Model
import torch
import whisper
from .models import Transcription, UploadedFile, Environment
from .serializers import TranscriptionSerializer, UploadedFileSerializer, EnvironmentSerializer
from pyannote.audio import Pipeline
from pyannote.audio import Audio
import torchaudio
from pyannote.audio.pipelines.utils.hook import ProgressHook
from django.utils import timezone
from rest_framework.renderers import StaticHTMLRenderer

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

        # 今月作成分だけをフィルタリング
        now = timezone.now()
        uploaded_files = UploadedFile.objects.filter(
            organization=organization,
            exist=True,
            created_at__year=now.year,
            created_at__month=now.month
        )
        total_duration = sum(uploaded_file.duration for uploaded_file in uploaded_files)

        max_duration = organization.get_max_duration()

        return Response({
            "total_duration": total_duration,
            "max_duration": max_duration
        })

    @action(detail=False, methods=['get'])
    def audio(self, request, *args, **kwargs):
        """
        音声ファイルのデータを取得する。
        """
        api_logger.info(f"UploadedFile audio request: {request.GET}")
        user = request.user
        organization = user.organization

        if not organization:
            api_logger.error("organization_idがない")
            return Response({"detail": "不正なリクエストです"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = UploadedFile.objects.filter(organization=organization)
        queryset = queryset.filter(id=kwargs['pk'])

        if not queryset.exists():
            api_logger.error("UploadedFileが見つかりません")
            return Response({"detail": "UploadedFileが見つかりません"}, status=status.HTTP_404_NOT_FOUND)

        instance = queryset.first()
        file_path = instance.file.path

        if not os.path.exists(file_path):
            return Response({"detail": "ファイルが見つかりません"}, status=status.HTTP_404_NOT_FOUND)

        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in ['.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov', '.wmv']:
            return Response({"detail": "音声ファイルではありません"}, status=status.HTTP_400_BAD_REQUEST)

        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        response = HttpResponse(open(file_path, 'rb').read(), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'

        api_logger.info(f"UploadedFile audio response: file sent")
        return response

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
                uploaded_file = file_serializer.save(organization_id=organization_id) # UploadedFileモデルにファイル情報を保存

                # 動画ファイルの再生時間を取得して保存
                if uploaded_file.file.name.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov', '.wmv')):
                    duration = get_video_duration(uploaded_file.file.path)
                    if duration is not None:
                        uploaded_file.duration = duration
                        uploaded_file.save()
                        # シリアライザーを再取得
                        file_serializer = UploadedFileSerializer(uploaded_file)

            except Exception as e:
                django_logger.error(f"ファイル保存中にエラーが発生しました: {e}")
                return Response({"error": "ファイルの保存に失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # 文字起こし処理を非同期で実行 Celeryを使う場合
            # transcribe_and_save_async.delay(temp_file_path, uploaded_file.id)

            return Response(file_serializer.data, status=status.HTTP_202_ACCEPTED)
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
                    transcription_text=transcription.get('text'),
                    start=transcription.get('start'),
                    uploaded_file_id=uploaded_file_id,
                    speaker=transcription.get('speaker')
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

    # 音声ファイルを読み込む
    audio = AudioSegment.from_file(file_path, format=file_extension.replace(".", ""), frame_rate=16000, sample_width=2, channels=1)
    processing_logger.info(f"audio: {audio}")

    # 音声の正規化
    audio = audio.normalize()

    # ノイズ除去
    samples = np.array(audio.get_array_of_samples())
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
        use_torch=True,
        device="cuda"
    )

    # 音声データの再構築
    audio = AudioSegment(
        reduced_noise.tobytes(),
        frame_rate=audio.frame_rate,
        sample_width=audio.sample_width,
        channels=audio.channels
    )

    # 音声の正規化
    # audio = audio.normalize()

    # 新しいファイル名を作成
    new_file_path = file_path.rsplit(".", 1)[0] + ".wav"

    # WAV形式でエクスポート
    try:
        audio.export(new_file_path, format="wav")  # 新しいファイル名を指定
    except Exception as e:
        raise RuntimeError(f"ファイルのエクスポートに失敗しました: {e}")

    # 新しいファイルが作成されたか確認
    if not os.path.exists(new_file_path):
        raise FileNotFoundError(f"エクスポートされたファイルが見つかりません: {new_file_path}")

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
    ダイアライゼーション（話者分離）の結果から話者を抽出する。
    """
    spacer_milli = 500
    dz = open("diarization.txt").read().splitlines()
    processing_logger.info(f"dz: {dz}")
    speakers = set()
    dzList = []
    for line in dz:
        processing_logger.info(f"line: {line}")
        start, end = tuple(re.findall('[0-9]+:[0-9]+:[0-9]+\.[0-9]+', string=line))
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

# @shared_task # Celeryを使う場合コメントアウトを外す
# def transcribe_and_save_async(file_path, uploaded_file_id):
def transcribe_and_save(file_path: str, uploaded_file_id: int) -> bool:
    """
    音声、動画ファイルから文字起こしを行い、transcriptionテーブルに保存する。

    Args:
        file_path (str): 音声、動画ファイルのパス
        uploaded_file_id (int): UploadedFileのID

    Returns:
        bool: 成功した場合はTrue、失敗した場合はFalse
    """

    try:
        # pyannoteはwavファイルの方が精度が高いので、wavファイルに変換する
        is_wav_file = True
        temp_file_path = file_path
        file_extension = os.path.splitext(file_path)[1]
        if file_extension != ".wav":
            temp_file_path, file_extension = process_audio(file_path, file_extension)
            is_wav_file = False
        # pyannoteでダイアライゼーション（話者分離）を行う
        diarization = perform_diarization(temp_file_path)
        # save_diarization_output(diarization) # テスト用

        audio = Audio(sample_rate=16000, mono=True)

        # 話者分離したデータを分割で文字起こしするより、全体を文字起こしする方が精度が高い
        whisper_model = get_whisper_model()
        all_result = whisper_model.transcribe(temp_file_path, language="ja")

        # 文字起こししたデータに再生時間を基に話者データを組み合わせる、話者が変わらなければ３０秒まで同じセグメントにまとめる
        segment_limit_time = 30
        temp_threshold_time = segment_limit_time
        temp_segment_transcription_text = ""
        temp_segment_start_time = 0
        temp_segment_speaker = ""
        # for segment, _, speaker in diarization.itertracks(yield_label=True):
        #     # セグメントの開始時間と終了時間を取得
        #     segment_start_time = segment.start
        #     segment_end_time = segment.end

        #     waveform, sample_rate = audio.crop(temp_file_path, segment)
        #     # waveformが正しい形式であることを確認
        #     if isinstance(waveform, list):
        #         waveform = torch.tensor(waveform)  # リストをテンソルに変換
        #     # waveformが2次元テンソルの場合、1次元に変換
        #     if waveform.ndim == 2:
        #         waveform = waveform.mean(dim=0)  # チャンネルを平均化

        #     dz_result = whisper_model.transcribe(waveform.numpy(), language="ja")

        #     # 話者情報を付加するための文字起こし結果を見つける
        #     for result in all_result['segments']:
        #         # 文字起こしの開始時間と終了時間を取得
        #         result_start = result['start']
        #         result_end = result['end']

        #         # セグメントの時間と文字起こしの時間が重なっているか確認
        #         if segment_start_time <= result_start <= segment_end_time or segment_start_time <= result_end <= segment_end_time:
        #             sec_start = int(result_start)
        #             sec_end = int(result_end)

        #             # 話者が変わらず、temp_threshold_timeを超えていない場合、temp_segment_transcription_textに追加
        #             if speaker == temp_segment_speaker:
        #                 if sec_end < temp_threshold_time:
        #                     temp_segment_transcription_text += result['text']
        #                 else:
        #                     save_transcription(temp_segment_transcription_text, temp_segment_start_time, uploaded_file_id, temp_segment_speaker)
        #                     temp_segment_transcription_text = result['text']
        #                     temp_threshold_time = sec_start + segment_limit_time
        #                     temp_segment_start_time = sec_start
        #                     temp_segment_speaker = speaker
        #             else:
        #                 save_transcription(temp_segment_transcription_text, temp_segment_start_time, uploaded_file_id, temp_segment_speaker)
        #                 temp_segment_transcription_text = result['text']
        #                 temp_threshold_time = sec_start + segment_limit_time
        #                 temp_segment_start_time = sec_start
        #                 temp_segment_speaker = speaker

        #             print(f"[{sec_start}s - {sec_end}s] {speaker}: {result['text']}")
        #             print("------------------------------------------------------------------------------------------------")
        #             break

        # 文字起こしからループを回すバージョン
        for result in all_result['segments']:
            result_start = result['start']
            result_end = result['end']
            result_text = result['text']

            for segment, _, speaker in diarization.itertracks(yield_label=True):
                segment_start_time = segment.start
                segment_end_time = segment.end

                # セグメントの時間と文字起こしの時間が重なっているか確認
                if result_start <= segment_start_time <= result_end or result_start <= segment_end_time <= result_end:
                    sec_start = int(result_start)
                    sec_end = int(result_end)

                    # 話者が変わるか、話者が変わらなくてもtemp_threshold_timeを超えている場合、保存する
                    if speaker == temp_segment_speaker:
                        if sec_end < temp_threshold_time:
                            temp_segment_transcription_text += result_text
                        else:
                            save_transcription(temp_segment_transcription_text, temp_segment_start_time, uploaded_file_id, temp_segment_speaker)
                            temp_segment_transcription_text = result_text
                            temp_threshold_time = sec_start + segment_limit_time
                            temp_segment_start_time = sec_start
                            temp_segment_speaker = speaker
                    else:
                        save_transcription(temp_segment_transcription_text, temp_segment_start_time, uploaded_file_id, temp_segment_speaker)
                        temp_segment_transcription_text = result_text
                        temp_threshold_time = sec_start + segment_limit_time
                        temp_segment_start_time = sec_start
                        temp_segment_speaker = speaker

                    print(f"[{sec_start}s - {sec_end}s] {speaker}: {result_text}")
                    print("------------------------------------------------------------------------------------------------")
                    break

        # 最後のセグメントが残っている場合は保存
        if temp_segment_transcription_text != "":
            save_transcription(temp_segment_transcription_text, temp_segment_start_time, uploaded_file_id, temp_segment_speaker)
        # ファイルを削除
        if not is_wav_file:
            os.remove(temp_file_path)
        return True
    except Exception as e:
        processing_logger.error(f"エラーが発生しました: {e}")
        return False

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
            logger.warning(f"文字起こしデータがありません。uploaded_file_id: {uploaded_file.id}")
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
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、要約を作成する専門家です。応答は必ずマークダウン形式で出力してください。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、マークダウン形式で要約を作成してください：\\n\\n{text}"}
            ],
            max_tokens=500  # 応答の最大長を制限
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"テキスト要約中にエラーが発生しました: {e}")
        return "要約に失敗しました。"

def definition_issue(text: str) -> str:
    """
    テキストを分析し、主要な課題点を特定する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: マークダウン形式で主要な課題点
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、主要な課題点を特定する専門家です。応答は必ずマークダウン形式で出力してください。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、マークダウン形式で主要な課題点を挙げられるだけ、箇条書きで簡潔に列挙してください：\\n\\n{text}"}
            ],
            max_tokens=500  # 応答の最大長を制限
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"

def definition_solution(text: str) -> str:
    """
    テキストを分析し、取り組み案を特定する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: マークダウン形式で取り組み案
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、取り組み案を特定する専門家です。応答は必ずマークダウン形式で出力してください。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、マークダウン形式で取り組み案を挙げられるだけ、箇条書きで簡潔に列挙してください：\\n\\n{text}"}
            ],
            max_tokens=500  # 応答の最大長を制限
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"

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
            max_tokens=500  # 応答の最大長を制限
        )
        return remove_markdown_blocks(response.choices[0].message.content)
    except Exception as e:
        processing_logger.error(f"議事録作成中にエラーが発生しました: {e}")
        return "議事録作成に失敗しました。"

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
