import os
import tempfile
import logging
import time
import random
from typing import Optional
from functools import lru_cache
from django.conf import settings
from ..models import UploadedFile, Transcription
from dotenv import load_dotenv
from pydub import AudioSegment
import torch
import whisper
from pyannote.audio import Pipeline
import torchaudio

# 環境変数をロードする
load_dotenv()

# ダイアライゼーションのためのモデルをロード
pyannote_auth_token = os.getenv('PYANNOTE_AUTH_TOKEN')

# ロガーを取得
processing_logger = logging.getLogger('processing')

@lru_cache(maxsize=1)
def get_whisper_model():
    # オープンソースWhisperモデルのロード
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
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    for attempt in range(max_retries):
        try:
            # Exponential backoff with jitter
            if attempt > 0:
                base_delay = min(60, 2 ** attempt)  # 最大60秒
                jitter = random.uniform(0.1, 0.5)
                delay = base_delay + jitter
                processing_logger.info(f"リトライ {attempt}/{max_retries}: {delay:.1f}秒待機中...")
                time.sleep(delay)

            with open(file_path, 'rb') as audio_file:
                transcription_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            
            processing_logger.info(f"OpenAI APIによる文字起こし成功 (試行 {attempt + 1}/{max_retries})")
            return transcription_response
            
        except Exception as e:
            error_msg = str(e)
            processing_logger.warning(f"OpenAI API呼び出し失敗 (試行 {attempt + 1}/{max_retries}): {error_msg}")
            
            # 最後の試行でも失敗した場合
            if attempt == max_retries - 1:
                processing_logger.error(f"OpenAI API呼び出し最終失敗: {error_msg}")
                return None
                
            # レート制限の場合は長めに待機
            if "rate limit" in error_msg.lower():
                processing_logger.info("レート制限検出: 60秒待機...")
                time.sleep(60)
    
    return None

def transcribe_and_save(file_path: str, uploaded_file_id, use_openai: bool = True) -> bool:
    """
    音声ファイルの文字起こしを実行し、データベースに保存する関数
    """
    processing_logger.info(f"文字起こし開始: {file_path}")
    
    try:
        # UploadedFileインスタンスを取得
        uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
        
        # ファイルパスをチェック
        if not os.path.exists(file_path):
            processing_logger.error(f"ファイルが見つかりません: {file_path}")
            return False
            
        # ファイルサイズをチェック
        file_size = os.path.getsize(file_path)
        processing_logger.info(f"ファイルサイズ: {file_size} bytes")
        
        if file_size == 0:
            processing_logger.error("ファイルサイズが0です")
            return False
            
        # 音声ファイルの再生時間を取得
        try:
            audio_segment = AudioSegment.from_file(file_path)
            duration_seconds = len(audio_segment) / 1000.0  # millisecondsからsecondsへ
            processing_logger.info(f"音声ファイルの再生時間: {duration_seconds}秒")
        except Exception as e:
            processing_logger.error(f"音声ファイルの読み込みエラー: {e}")
            return False
            
        # 既存のTranscriptionデータを削除
        Transcription.objects.filter(uploaded_file=uploaded_file).delete()
        processing_logger.info("既存の文字起こしデータを削除しました")
        
        # 音声ファイルを分割してダイアライゼーション
        processing_logger.info("音声ファイルの分割処理を開始...")
        
        # 話者分離を実行
        segments = perform_speaker_diarization(file_path)
        processing_logger.info(f"話者分離完了: {len(segments)}個のセグメント")
        
        # 各セグメントの文字起こし
        for i, segment in enumerate(segments):
            processing_logger.info(f"セグメント {i+1}/{len(segments)} の文字起こし開始")
            
            # セグメントの音声を抽出
            segment_audio = audio_segment[segment['start']*1000:segment['end']*1000]
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                segment_audio.export(tmp_file.name, format='wav')
                tmp_file_path = tmp_file.name
            
            try:
                # 文字起こし実行
                if use_openai:
                    transcription_result = openai_transcribe_with_retry(tmp_file_path)
                    if transcription_result:
                        text = transcription_result.text
                    else:
                        # OpenAI APIが失敗した場合はWhisperを使用
                        text = transcribe_with_whisper(tmp_file_path)
                else:
                    text = transcribe_with_whisper(tmp_file_path)
                
                # Transcriptionオブジェクトを作成
                Transcription.objects.create(
                    uploaded_file=uploaded_file,
                    text=text,
                    speaker_label=segment['speaker'],
                    start_time=segment['start'],
                    end_time=segment['end']
                )
                
                processing_logger.info(f"セグメント {i+1} の文字起こし完了: {text[:50]}...")
                
            finally:
                # 一時ファイルを削除
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
        
        processing_logger.info("文字起こし処理が完了しました")
        return True
        
    except Exception as e:
        processing_logger.error(f"文字起こし処理でエラーが発生しました: {e}")
        return False

def perform_speaker_diarization(file_path):
    """
    話者分離を実行する関数
    """
    try:
        # ダイアライゼーションモデルを取得
        diarization_model = get_diarization_model()
        
        # 音声ファイルを読み込み
        waveform, sample_rate = torchaudio.load(file_path)
        
        # ダイアライゼーション実行
        diarization_result = diarization_model({"waveform": waveform, "sample_rate": sample_rate})
        
        # 結果を処理
        segments = []
        for turn, _, speaker in diarization_result.itertracks(yield_label=True):
            segments.append({
                'start': turn.start,
                'end': turn.end,
                'speaker': speaker
            })
        
        return segments
        
    except Exception as e:
        processing_logger.warning(f"話者分離に失敗しました: {e}")
        # 話者分離が失敗した場合は全体を1つのセグメントとして扱う
        audio_segment = AudioSegment.from_file(file_path)
        duration_seconds = len(audio_segment) / 1000.0
        
        return [{
            'start': 0.0,
            'end': duration_seconds,
            'speaker': 'SPEAKER_00'
        }]

def transcribe_with_whisper(file_path):
    """
    Whisperモデルを使用した文字起こし
    """
    try:
        whisper_model = get_whisper_model()
        result = whisper_model.transcribe(file_path)
        return result['text']
    except Exception as e:
        processing_logger.error(f"Whisper文字起こしエラー: {e}")
        return "文字起こしに失敗しました"