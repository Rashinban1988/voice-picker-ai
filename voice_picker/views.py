import json
import logging
from openai import OpenAI
import os
import time
import warnings
import re
import webvtt
# import wave

import numpy as np
import noisereduce as nr
from functools import lru_cache
# from celery import shared_task
from django.db import transaction
from django.http import JsonResponse
from django.views import View
from dotenv import load_dotenv
from pydub import AudioSegment
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from typing import Union
from urllib.parse import unquote
from vosk import KaldiRecognizer, Model
import torch
import whisper
from .models import Transcription, UploadedFile
from .serializers import TranscriptionSerializer, UploadedFileSerializer
from pyannote.audio import Pipeline

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
            except Exception as e:
                django_logger.error(f"ファイル保存中にエラーが発生しました: {e}")
                return Response({"error": "ファイルの保存に失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # 文字起こし処理を非同期で実行 Celeryを使う場合
            # transcribe_and_save_async.delay(temp_file_path, uploaded_file.id)

            return Response(file_serializer.data, status=status.HTTP_202_ACCEPTED)
        else:
            django_logger.info(f"ファイルアップロードに失敗しました: {file_serializer.errors}")
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

    # ノイズ除去
    samples = np.array(audio.get_array_of_samples())
    reduced_noise = nr.reduce_noise(
        y=samples, # 音声データ
        sr=audio.frame_rate, # サンプリングレート
        prop_decrease=0.5, # ノイズを減少させる割合、1だと音声も減少する可能性がある
        time_constant_s=2, # 室内など一定のノイズの場合は大きいほどノイズが減少する、屋外などノイズが変動する場合は小さいほどノイズが減少する
        freq_mask_smooth_hz=400, # 音声に影響が出ないのは500Hz以下
        time_mask_smooth_ms=50, # 短い音声では50ms以下、長い音声では100ms以上
        thresh_n_mult_nonstationary=1.5, # 屋外などノイズが変動する場合は大きいほどノイズが減少する、室内のおすすめは1.5
        sigmoid_slope_nonstationary=10, # 非定常ノイズのシグモイドの傾き、音声の場合は10以上
        n_std_thresh_stationary=1.5, # 定常ノイズの標準偏差の閾値、大きいほどノイズが減少する、音声の場合は1.5
        clip_noise_stationary=False, # 定常ノイズをクリップするかどうか、Trueだと音声も減少する可能性がある
        use_tqdm=False, # 進捗バーを表示するかどうか、処理速度に影響する
        n_jobs=2, # 並列処理の数、1だとシリアル処理
        use_torch=False, # テンソルを使用するかどうか、Trueだと処理速度が速い（GPUを使用する場合はTrue）
        device="cpu" # デバイスを指定、GPUを使用する場合は"cuda"、CPUを使用する場合は"cpu"
    )
    audio = AudioSegment(
        reduced_noise.tobytes(),
        frame_rate=audio.frame_rate,
        sample_width=audio.sample_width,
        channels=audio.channels
    )

    # 音声の正規化
    audio = audio.normalize()

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

def preprocess_audio(audio, t1, t2, file_path):
    """
    音声を調整する。
    """
    audio = audio.set_frame_rate(16000)  # サンプリングレートを16000Hzに変換
    audio = audio.set_sample_width(2)     # 16bitに変換
    audio = audio.set_channels(1)         # モノラルに変換
    audio = audio[t1:t2]
    audio.export(file_path, format="wav")

    # 0.5秒のスペーサーを追加
    spacer_milli = 500
    spacer = AudioSegment.silent(duration=spacer_milli)
    audio = spacer.append(audio, crossfade=0)
    audio.export(file_path, format="wav")

    return audio

def perform_diarization(file_path):
    """
    音声ファイルをダイアライゼーション（話者分離）する。
    """
    pipeline = Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=pyannote_auth_token)
    return pipeline(file_path)

def save_diarization_output(dz):
    """
    ダイアライゼーション（話者分離）の結果を保存する。
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
    speakers = set()
    dzList = []
    for line in dz:
        start, end = tuple(re.findall('[0-9]+:[0-9]+:[0-9]+\.[0-9]+', string=line))
        start = millisec(start) - spacer_milli
        end = millisec(end) - spacer_milli
        speaker_match = re.findall(r'SPEAKER_\d+', line)
        speaker = speaker_match[0] if speaker_match else None
        speakers.add(speaker)
        dzList.append([start, end, speaker])
    return dzList

def create_audio_segments(audio, dzList, file_path):
    """
    音声ファイルをセグメントに分割する。
    同じ話者の音声は30秒まで同じセグメントにまとめる。
    """
    spacer_milli = 500
    spacer = AudioSegment.silent(duration=spacer_milli)
    sounds = spacer
    segments = []

    current_speaker = None
    current_segment = AudioSegment.silent(duration=0)
    max_segment_duration = 30 * 1000  # セグメントの最大長
    segment_start_time = None # セグメントの開始時間を初期化

    for l in dzList:
        if isinstance(l, list) and len(l) == 3:
            start, end, speaker = l  # リストからstart, end, speakerを取得
        else:
            processing_logger.error(f"Invalid type for line: {type(l)}. Expected list with 3 elements.")
            continue  # 次のループに進む

        # 現在のセグメントに音声を追加
        current_segment = current_segment.append(audio[start:end], crossfade=0)

        # セグメントの長さをチェック
        if len(current_segment) >= max_segment_duration or speaker != current_speaker:
            # セグメントをsoundsに追加
            sounds = sounds.append(current_segment, crossfade=0)
            segments.append(len(sounds))  # 現在のsoundsの長さを記録

            # セグメントの開始時間を記録
            if segment_start_time is None:
                segment_start_time = start  # 最初のセグメントの開始時間を設定
            else:
                segment_start_time = min(segment_start_time, start)  # 最小のstart時間を保持

            sounds = sounds.append(spacer, crossfade=0)  # スペーサーを追加
            current_segment = AudioSegment.silent(duration=0)  # 現在のセグメントをリセット

        current_speaker = speaker

    # 最後のセグメントが残っている場合は追加
    if len(current_segment) > 0:
        sounds = sounds.append(current_segment, crossfade=0)
        segments.append(len(sounds))

        # 最後のセグメントの開始時間を記録
        if segment_start_time is None:
            segment_start_time = start  # 最初のセグメントの開始時間を設定
        else:
            segment_start_time = min(segment_start_time, start)  # 最小のstart時間を保持

        sounds = sounds.append(spacer, crossfade=0)

    sounds.export(file_path, format="wav")
    return sounds, segments, segment_start_time

def export_segment(sounds, segments, i, segment_start_time):
    """
    セグメントをエクスポートする。
    """
    segment_audio = sounds[segments[i]:segments[i + 1]]
    temp_file_path = f"temp_segment_{i}.wav"
    segment_audio.export(temp_file_path, format="wav")
    return temp_file_path, segment_start_time

def transcribe_segment(whisper_model, temp_file_path, segment_start_time):
    """
    セグメントを文字起こしする。
    """
    with torch.no_grad():
        result = whisper_model.transcribe(temp_file_path, fp16=False, language="ja")
        transcription_text = result.get("text", "")
        processing_logger.info(f"transcription_text: {transcription_text}")
    return transcription_text, segment_start_time

def save_transcription(transcription_text, start, uploaded_file_id, speaker, segment_start_time):
    """
    文字起こし結果を保存する。
    """
    processing_logger.info(f"Saving transcription: start_time={segment_start_time}, text={transcription_text}, speaker={speaker}")

    serializer_class = TranscriptionSerializer(data={
        "start_time": segment_start_time,
        "text": transcription_text,
        "uploaded_file": uploaded_file_id,
        "speaker": speaker,
    })
    if serializer_class.is_valid():
        serializer_class.save()
    else:
        processing_logger.error(f"transcription_textが空です: {transcription_text}")

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
        t1 = 0 * 1000  # Works in milliseconds
        t2 = 20 * 60 * 1000

        # ファイルのパスを取得
        file_path = UploadedFile.objects.get(id=uploaded_file_id).file.path
        file_extension = os.path.splitext(file_path)[1]

        if file_extension != ".wav":
            file_path, file_extension = process_audio(file_path, file_extension)

        audio = AudioSegment.from_wav(file_path)
        audio = preprocess_audio(audio, t1, t2, file_path)  # 音声の前処理を関数化

        # ダイアライゼーション
        dz = perform_diarization(file_path) # ダイアライゼーションを行う
        save_diarization_output(dz) # 出力を保存する

        dzList = extract_speakers(dz) # 話者を抽出する

        sounds, segments, segment_start_timeq = create_audio_segments(audio, dzList, file_path) # 音声セグメントを作成する

        whisper_model = get_whisper_model()

        # 各話者のセグメントに対して文字起こしを行う
        for i, (start, end, speaker) in enumerate(dzList):
            temp_file_path, segment_start_time = export_segment(sounds, segments, i, segment_start_time) # セグメントをエクスポートする
            transcription_text, segment_start_time = transcribe_segment(whisper_model, temp_file_path, segment_start_time) # セグメントを文字起こしする
            save_transcription(transcription_text, start, uploaded_file_id, speaker) # 結果を保存する
            os.remove(temp_file_path)  # 一時ファイルを削除

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

def summarize_text(text: str) -> str:
    """
    テキストを要約する。

    Args:
        text (str): 要約するテキスト
    Returns:
        str: 要約されたテキスト
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、主要な課題点を特定する専門家です。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、要約を作成してください：\n\n{text}"}
            ],
            max_tokens=500  # 応答の最大長を制限
        )
        return response.choices[0].message.content
    except Exception as e:
        processing_logger.error(f"テキスト要約中にエラーが発生しました: {e}")
        return "要約に失敗しました。"

def definition_issue(text: str) -> str:
    """
    テキストを分析し、主要な課題点を特定する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: 主要な課題点
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、主要な課題点を特定する専門家です。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、主要な課題点を挙げられるだけ、箇条書きで簡潔に列挙してください：\n\n{text}"}
            ],
            max_tokens=500  # 応答の最大長を制限
        )
        return response.choices[0].message.content
    except Exception as e:
        processing_logger.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"

def definition_solution(text: str) -> str:
    """
    テキストを分析し、取り組み案を特定する。

    Args:
        text (str): 分析するテキスト
    Returns:
        str: 取り組み案
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは文章を分析し、主要な課題点を特定する専門家です。"},
                {"role": "user", "content": f"以下の文章の内容を読み取り、取り組み案を挙げられるだけ、箇条書きで簡潔に列挙してください：\n\n{text}"}
            ],
            max_tokens=500  # 応答の最大長を制限
        )
        return response.choices[0].message.content
    except Exception as e:
        processing_logger.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"