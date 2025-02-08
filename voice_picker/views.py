import json
import logging
from openai import OpenAI
import os
import time
import warnings
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

# 環境変数をロードする
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@lru_cache(maxsize=1)
def get_whisper_model():
    # オープンソースWhisperモデルのロード
    # GPUを使用する場合
    # device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # whisper_model = whisper.load_model("tiny").to(device)

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
        user = request.user  # 現在のユーザーを取得
        organization = user.organization  # ユーザーの組織を取得

        if not organization:
            return Response({"detail": "不正なリクエストです"}, status=status.HTTP_400_BAD_REQUEST)  # organization_idがない場合のレスポンス

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
        return response

    def create(self, request, *args, **kwargs):
        # ロガーを取得
        logger = logging.getLogger('django')
        logger.debug("ファイルアップロードがリクエストされました。")

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
                logger.error(f"ファイル保存中にエラーが発生しました: {e}")
                return Response({"error": "ファイルの保存に失敗しました。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # 文字起こし処理を非同期で実行 Celeryを使う場合
            # transcribe_and_save_async.delay(temp_file_path, uploaded_file.id)

            return Response(file_serializer.data, status=status.HTTP_202_ACCEPTED)
        else:
            logger.info(f"ファイルアップロードに失敗しました: {file_serializer.errors}")
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

class TranscriptionViewSet(viewsets.ModelViewSet):
    queryset = Transcription.objects.all()
    serializer_class = TranscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        uploadedfileのIDに基づいてtranscriptionのクエリセットをフィルタリングする。
        """
        queryset = super().get_queryset().order_by('created_at')
        # URLからuploadedfileのIDを取得するためのキーを修正する
        uploadedfile_id = self.kwargs.get('uploadedfile_id')
        if uploadedfile_id is not None:
            queryset = queryset.filter(uploaded_file__id=uploadedfile_id)
        return queryset

class TranscribeView(View):
    def get(self, request, *args, **kwargs):
        command = TranscribeCommand()
        command.handle()
        return JsonResponse({'status': 'transcription started'})

# FP16に関するワーニングを無視
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

def file_upload_view(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # ファイルの処理
            handle_uploaded_file(request.FILES['file'])
            return render(request, 'transcription/success.html')  # 成功時のテンプレート
    else:
        form = FileUploadForm()
    return render(request, 'transcription/upload.html', {'form': form})

def handle_uploaded_file(f):
    # 一時ファイルとして保存
    with open('temp_file', 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

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
    logger = logging.getLogger(__name__)

    logger.debug("文字起こし処理がリクエストされました。")
    logger.debug(f"ファイルパス: {file_path}")

    # モデルのロード
    try:
        # Voskモデルのロード
        # base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # model_path = os.path.join(base_path, 'models/vosk-model-ja-0.22')
        # vosk_model = Model(model_path)

        whisper_model = get_whisper_model()
        print(whisper_model)
    except Exception as e:
        logger.error(f"モデルのロードに失敗しました: {e}")
        return

    # 音声ファイルの読み込みと調整
    try:
        file_path = os.path.join('/code', file_path)
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension in [".wav", ".mp3", ".m4a", ".mp4"]:
            # 音声の読み込み
            audio = AudioSegment.from_file(file_path, format=file_extension.replace(".", ""), frame_rate=16000, sample_width=2)

            # サンプリングレートの調整（必要に応じて）
            audio = audio.set_frame_rate(16000)

            # ノイズ除去（noisereduceライブラリを使用）
            audio_np = np.array(audio.get_array_of_samples())
            reduced_noise = nr.reduce_noise(y=audio_np, sr=16000)

            # 音声データを再構築
            audio = AudioSegment(
                reduced_noise.tobytes(),
                frame_rate=16000,
                sample_width=audio.sample_width,
                channels=audio.channels
            )

            # 音声の正規化
            audio = audio.normalize()  # 音声の正規化
        else:
            raise ValueError("サポートされていない音声形式です。")
    except Exception as e:
        logger.error(f"ファイルの読み込みに失敗しました: {e}")
        return

    # 音声ファイルを指定秒数ごとに分割して文字起こし
    try:
        split_interval = 15 * 1000  # ミリ秒単位
        all_transcription_text = ""
        for i, start_time in enumerate(range(0, len(audio), split_interval)):
            end_time = min(start_time + split_interval, len(audio))
            split_audio = audio[start_time:end_time]
            temp_file_path = f"temp_{i}.wav"
            try:
                split_audio.export(temp_file_path, format="wav")

                # ----------------------------------voskの音声分析 はじめ----------------------------------
                # with wave.open(temp_file_path, 'rb') as wf:
                    # 分析処理
                    # rec = KaldiRecognizer(vosk_model, wf.getframerate())
                    # while True:
                    #     data = wf.readframes(1000)
                    #     if len(data) == 0:
                    #         break
                    #     if rec.AcceptWaveform(data):
                    #         pass
                    # result = json.loads(rec.FinalResult())
                    # transcription_text = result['text'] if 'text' in result else ''
                # ----------------------------------voskの音声分析 おわり----------------------------------
                # ----------------------------------open ai whisper1 音声分析 はじめ-----------------------
                # transcription = client.audio.transcriptions.create(
                #     model = "whisper-1",
                #     file = open(temp_file_path, "rb"),
                #     language = "ja",
                #     prompt = "この音声は、日本語で話されています。",
                # )
                # transcription_text = transcription.text
                # all_transcription_text += transcription_text
                # # API呼び出し後に待機時間を追加
                # time.sleep(0.7)  # 1分間に100回の制限を考慮して0.7秒待機（85回）
                # ----------------------------------open ai whisper1 音声分析 おわり-----------------------
                # ----------------------------------オープンソースWhisper音声分析 はじめ-----------------------
                # GPUを使用する場合
                # result = whisper_model.transcribe(temp_file_path)
                # transcription_text = result["text"]
                # all_transcription_text += transcription_text

                # CPUを使用して転写
                with torch.no_grad():
                    result = whisper_model.transcribe(temp_file_path, fp16=False, language="ja")
                transcription_text = result["text"]
                print(transcription_text)
                all_transcription_text += transcription_text
                # ----------------------------------オープンソースWhisper音声分析 おわり-----------------------

                # 分析処理終了
                serializer_class = TranscriptionSerializer(data={
                    "start_time": start_time / 1000,
                    "text": transcription_text,
                    "uploaded_file": uploaded_file_id,
                })
                if serializer_class.is_valid():
                    serializer_class.save()
                else:
                    logger.error(f"文字起こし結果の保存に失敗しました: {serializer_class.errors}")
            finally:
                os.remove(temp_file_path)
        return True
    except Exception as e:
        logger.error(f"文字起こし処理中にエラーが発生しました: {e}")
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
    logger = logging.getLogger(__name__)
    logger.info(f"summarize_and_save が呼び出されました。uploaded_file_id: {uploaded_file.id}")

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
        logger.error(f"summarize_and_save でエラーが発生しました: {e}")
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
        logging.error(f"テキスト要約中にエラーが発生しました: {e}")
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
        logging.error(f"テキスト分析中にエラーが発生しました: {e}")
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
        logging.error(f"テキスト分析中にエラーが発生しました: {e}")
        return "分析に失敗しました。"