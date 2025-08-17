import os
import tempfile
import logging
import time
import random
import requests
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

def lemonfox_transcribe_with_retry(file_path: str, max_retries: int = 3) -> Optional[dict]:
    """
    LemonFox.ai APIでの文字起こし処理
    """
    api_key = os.getenv('LEMONFOX_API_KEY')
    if not api_key:
        processing_logger.error("LEMONFOX_API_KEY環境変数が設定されていません")
        return None

    url = "https://api.lemonfox.ai/v1/audio/transcriptions"

    for attempt in range(max_retries):
        try:
            # Exponential backoff with jitter
            if attempt > 0:
                base_delay = min(30, 2 ** attempt)  # 最大30秒
                jitter = random.uniform(0.1, 0.5)
                delay = base_delay + jitter
                processing_logger.info(f"LemonFox APIリトライ {attempt}/{max_retries}: {delay:.1f}秒待機中...")
                time.sleep(delay)

            with open(file_path, 'rb') as audio_file:
                files = {
                    'file': audio_file
                }
                data = {
                    'response_format': 'verbose_json',
                    'speaker_labels': 'true',
                    'language': 'ja'  # 日本語を指定
                }
                headers = {
                    'Authorization': f'Bearer {api_key}'
                }

                response = requests.post(url, files=files, data=data, headers=headers)
                response.raise_for_status()

                result = response.json()
                processing_logger.info(f"LemonFox APIによる文字起こし成功 (試行 {attempt + 1}/{max_retries})")
                return result

        except Exception as e:
            error_msg = str(e)
            processing_logger.warning(f"LemonFox API呼び出し失敗 (試行 {attempt + 1}/{max_retries}): {error_msg}")

            # 最後の試行でも失敗した場合
            if attempt == max_retries - 1:
                processing_logger.error(f"LemonFox API呼び出し最終失敗: {error_msg}")
                return None

            # レート制限の場合は長めに待機
            if response.status_code == 429:
                processing_logger.info("レート制限検出: 30秒待機...")
                time.sleep(30)

    return None

def transcribe_and_save(file_path: str, uploaded_file_id, transcription_provider: str = 'openai') -> bool:
    """
    音声ファイルの文字起こしを実行し、データベースに保存する関数
    transcription_provider: 'openai', 'lemonfox', 'whisper'
    """
    processing_logger.info(f"文字起こし開始: {file_path} (プロバイダー: {transcription_provider})")

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

        # 音声ファイルの再生時間を取得（メモリ効率的にffprobeを使用）
        try:
            import subprocess
            cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            duration_seconds = float(result.stdout.strip())
            processing_logger.info(f"音声ファイルの再生時間: {duration_seconds}秒")
        except Exception as e:
            processing_logger.error(f"音声ファイルの再生時間取得エラー: {e}")
            # フォールバック: AudioSegmentを使用（メモリ使用量注意）
            try:
                audio_segment = AudioSegment.from_file(file_path)
                duration_seconds = len(audio_segment) / 1000.0
                processing_logger.warning(f"ffprobe失敗、AudioSegmentで取得: {duration_seconds}秒")
                del audio_segment  # 明示的にメモリ解放
            except Exception as e2:
                processing_logger.error(f"音声ファイルの読み込みエラー: {e2}")
                return False

        # 既存のTranscriptionデータを論理削除
        transcriptions = Transcription.objects.filter(uploaded_file=uploaded_file, exist=True)
        for transcription in transcriptions:
            transcription.delete()  # モデルのdeleteメソッドを使用して論理削除
        processing_logger.info("既存の文字起こしデータを論理削除しました")

        # LemonFoxの場合は話者分離機能付きなので、ファイル全体を処理
        if transcription_provider == 'lemonfox':
            return transcribe_with_lemonfox_full_file(file_path, uploaded_file)

        # OpenAIとWhisperの場合は従来の話者分離処理
        # 音声ファイルを分割してダイアライゼーション
        processing_logger.info("音声ファイルの分割処理を開始...")

        # 話者分離を実行
        segments = perform_speaker_diarization(file_path)
        processing_logger.info(f"話者分離完了: {len(segments)}個のセグメント")

        # 各セグメントの文字起こし（メモリ効率的にffmpegで分割）
        for i, segment in enumerate(segments):
            processing_logger.info(f"セグメント {i+1}/{len(segments)} の文字起こし開始")

            # ffmpegで該当セグメントを切り出し（メモリ効率的）
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file_path = tmp_file.name

            try:
                # ffmpegでセグメント切り出し
                import subprocess
                cmd = [
                    'ffmpeg', '-y', '-i', file_path,
                    '-ss', str(segment['start']),
                    '-t', str(segment['end'] - segment['start']),
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',
                    tmp_file_path
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    processing_logger.error(f"ffmpegでのセグメント切り出し失敗: {result.stderr}")
                    continue

                # 文字起こし実行
                if transcription_provider == 'openai':
                    transcription_result = openai_transcribe_with_retry(tmp_file_path)
                    if transcription_result:
                        text = transcription_result.text
                    else:
                        # OpenAI APIが失敗した場合はWhisperを使用
                        text = transcribe_with_whisper(tmp_file_path)
                else:  # transcription_provider == 'whisper'
                    text = transcribe_with_whisper(tmp_file_path)

                # Transcriptionオブジェクトを作成
                Transcription.objects.create(
                    uploaded_file=uploaded_file,
                    text=text,
                    speaker=segment['speaker'],
                    start_time=int(segment['start'])
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

def transcribe_with_lemonfox_full_file(file_path: str, uploaded_file) -> bool:
    """
    LemonFox.ai APIを使用してファイル全体を文字起こし（話者分離付き）
    25MB以上のファイルは分割して処理（LemonFox API制限）
    """
    try:
        # ファイルサイズチェック（25MB = 25 * 1024 * 1024 bytes）
        file_size = os.path.getsize(file_path)
        max_size = 25 * 1024 * 1024  # 25MB (LemonFox API制限)

        if file_size > max_size:
            processing_logger.info(f"ファイルサイズが25MBを超過（{file_size} bytes, {file_size/1024/1024:.1f}MB）: 分割処理を実行")
            return transcribe_with_lemonfox_chunked(file_path, uploaded_file)
        else:
            processing_logger.info(f"ファイルサイズ {file_size} bytes ({file_size/1024/1024:.1f}MB): 通常処理")
            return transcribe_with_lemonfox_single_file(file_path, uploaded_file)

    except Exception as e:
        processing_logger.error(f"LemonFox文字起こし処理でエラーが発生しました: {e}")
        return False

def transcribe_with_lemonfox_chunked(file_path: str, uploaded_file) -> bool:
    """
    100MB以上のファイルをffmpegで分割してLemonFox.ai APIで文字起こし
    """
    import subprocess
    try:
        processing_logger.info(f"大容量ファイルの分割処理を開始: {file_path}")

        # ffmpegで音声の総時間を取得（メモリ効率的）
        cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        total_duration = float(result.stdout.strip())
        processing_logger.info(f"総時間: {total_duration:.1f}秒")

        # 5分（300秒）ごとに分割
        chunk_duration = 300  # 5分
        estimated_chunks = int((total_duration + chunk_duration - 1) // chunk_duration)
        processing_logger.info(f"推定分割数: {estimated_chunks}, チャンク時間: {chunk_duration}秒")

        all_transcriptions = []

        # 一時ディレクトリ作成
        with tempfile.TemporaryDirectory() as temp_dir:
            # ffmpegで分割（メモリ使用量最小）
            for i in range(estimated_chunks):
                chunk_start = i * chunk_duration
                chunk_end = min((i + 1) * chunk_duration, total_duration)

                chunk_file = os.path.join(temp_dir, f"chunk_{i:03d}.wav")

                # ffmpegで該当部分を切り出し
                cmd = [
                    'ffmpeg', '-y', '-i', file_path,
                    '-ss', str(chunk_start),
                    '-t', str(chunk_end - chunk_start),
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',
                    chunk_file
                ]

                subprocess.run(cmd, capture_output=True, check=True)
                processing_logger.info(f"チャンク {i+1}/{estimated_chunks} 作成完了: {chunk_start:.1f}s - {chunk_end:.1f}s")

                # 即座に文字起こし処理
                processing_logger.info(f"チャンク {i+1} の文字起こしを開始")
                result = lemonfox_transcribe_with_retry(chunk_file)

                if result and 'segments' in result:
                    # タイムスタンプを調整してall_transcriptionsに追加（DB保存は後で行う）
                    for segment in result['segments']:
                        adjusted_start_time = segment.get('start', 0.0) + chunk_start
                        adjusted_end_time = segment.get('end', 0.0) + chunk_start
                        speaker_label = segment.get('speaker', 'SPEAKER_00')
                        text = segment.get('text', '')

                        if text.strip():  # 空でないテキストのみ追加
                            all_transcriptions.append({
                                'start': adjusted_start_time,
                                'end': adjusted_end_time,
                                'text': text,
                                'speaker': speaker_label
                            })
                else:
                    processing_logger.warning(f"チャンク {i+1} の文字起こしに失敗")

        # すべてのチャンクを処理した後にマージ処理を実行
        if all_transcriptions:
            # 時系列順にソート
            all_transcriptions.sort(key=lambda x: x['start'])

            # 同一話者の連続セグメントをマージ
            merged_transcriptions = merge_continuous_speaker_segments(all_transcriptions)

            processing_logger.info(f"分割文字起こし完了: 総セグメント数 {len(all_transcriptions)} -> マージ後: {len(merged_transcriptions)}")

            # マージ後のデータをDBに保存
            for segment in merged_transcriptions:
                Transcription.objects.create(
                    uploaded_file=uploaded_file,
                    text=segment['text'],
                    speaker=segment['speaker'],
                    start_time=int(segment['start'])
                )

        return True

    except Exception as e:
        processing_logger.error(f"分割文字起こし処理でエラーが発生しました: {e}")
        return False

def merge_continuous_speaker_segments(segments, max_gap_seconds=30, max_segment_duration=30):
    """
    同一話者の連続セグメントを30秒以内でマージし、30秒を超えたら分割する
    """
    if not segments:
        return segments


    merged = []
    current_segment = segments[0].copy()

    for next_segment in segments[1:]:
        time_gap = next_segment.get('start', 0) - current_segment.get('end', 0)
        # マージ後の総時間を計算
        potential_duration = next_segment.get('end', 0) - current_segment.get('start', 0)

        # 同一話者で時間間隔が指定秒数以内、かつマージ後の総時間が30秒以
        # 内の場合
        if (current_segment.get('speaker') == next_segment.get('speaker') and
            time_gap <= max_gap_seconds and
            potential_duration <= max_segment_duration):
            # セグメントをマージ
            current_segment['text'] += ' ' + next_segment.get('text', '')
            current_segment['end'] = next_segment.get('end', current_segment.get('end', 0))
        else:
            # 新しいセグメントとして追加
            merged.append(current_segment)
            current_segment = next_segment.copy()

    merged.append(current_segment)
    return merged

def transcribe_with_lemonfox_single_file(file_path: str, uploaded_file) -> bool:
    """
    LemonFox.ai APIを使用して単一ファイルを文字起こし
    """
    try:
        transcription_result = lemonfox_transcribe_with_retry(file_path)
        if not transcription_result:
            processing_logger.error("LemonFox APIによる文字起こしに失敗しました")
            return False

        # LemonFoxのレスポンス形式を処理
        if 'segments' in transcription_result:
            # セグメント情報がある場合、まずマージ処理を実行
            segments = transcription_result['segments']
            merged_segments = merge_continuous_speaker_segments(segments)

            processing_logger.info(f"セグメント数: {len(segments)} -> マージ後: {len(merged_segments)}")

            for segment in merged_segments:
                speaker_label = segment.get('speaker', 'SPEAKER_00')
                text = segment.get('text', '')
                start_time = segment.get('start', 0.0)
                end_time = segment.get('end', 0.0)

                if text.strip():  # 空でないテキストのみ保存
                    Transcription.objects.create(
                        uploaded_file=uploaded_file,
                        text=text,
                        speaker=speaker_label,
                        start_time=int(start_time)
                    )

        elif 'text' in transcription_result:
            # セグメント情報がない場合は全体テキストとして保存
            text = transcription_result['text']

            Transcription.objects.create(
                uploaded_file=uploaded_file,
                text=text,
                speaker='SPEAKER_00',
                start_time=0
            )

        processing_logger.info("LemonFox APIによる文字起こし処理が完了しました")
        return True

    except Exception as e:
        processing_logger.error(f"LemonFox文字起こし処理でエラーが発生しました: {e}")
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
        try:
            # ffprobeで再生時間を取得（メモリ効率的）
            import subprocess
            cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            duration_seconds = float(result.stdout.strip())
        except Exception:
            # フォールバック: AudioSegmentを使用
            try:
                audio_segment = AudioSegment.from_file(file_path)
                duration_seconds = len(audio_segment) / 1000.0
                del audio_segment  # 明示的にメモリ解放
            except Exception:
                # デフォルト値
                duration_seconds = 3600.0  # 1時間とする

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