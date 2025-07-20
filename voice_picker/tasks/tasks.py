import os
import tempfile
import logging
import subprocess
import json
from pathlib import Path
from celery import shared_task
from django.conf import settings
from ..models import UploadedFile, Transcription
from ..services.transcription_service import transcribe_and_save
import concurrent.futures
import multiprocessing
from dotenv import load_dotenv

# 環境変数をロード
load_dotenv()

processing_logger = logging.getLogger('processing')

# Status constants from UploadedFile.Status
STATUS_UNPROCESSED = 0
STATUS_PROCESSING = 1
STATUS_COMPLETED = 2
STATUS_ERROR = 3

@shared_task(bind=True)
def transcribe_and_save_async(self, file_path, uploaded_file_id):
    """
    音声ファイルの文字起こしを非同期で実行するCeleryタスク

    Args:
        file_path (str): 音声ファイルのパス
        uploaded_file_id (int): UploadedFileのID

    Returns:
        dict: 実行結果
    """
    try:
        processing_logger.info(f"Starting async transcription for file {file_path}, uploaded_file_id: {uploaded_file_id}")

        # UploadedFileの状態を処理中に更新
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            uploaded_file.status = STATUS_PROCESSING
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            processing_logger.error(f"UploadedFile with id {uploaded_file_id} not found")
            return {"success": False, "error": "UploadedFile not found"}

        # 環境変数から文字起こしプロバイダーを取得
        transcription_provider = os.getenv('TRANSCRIPTION_PROVIDER', 'openai')
        processing_logger.info(f"Using transcription provider: {transcription_provider}")

        # 文字起こし実行
        success = transcribe_and_save(file_path, uploaded_file_id, transcription_provider)

        if success:
            # 成功時はステータスを完了に更新
            uploaded_file.status = STATUS_COMPLETED
            uploaded_file.save()
            processing_logger.info(f"Transcription completed successfully for uploaded_file_id: {uploaded_file_id}")
            return {"success": True, "uploaded_file_id": uploaded_file_id}
        else:
            # 失敗時はステータスをエラーに更新
            uploaded_file.status = STATUS_ERROR
            uploaded_file.save()
            processing_logger.error(f"Transcription failed for uploaded_file_id: {uploaded_file_id}")
            return {"success": False, "error": "Transcription failed"}

    except Exception as e:
        processing_logger.error(f"Error in async transcription task: {e}")

        # エラー時もステータスを更新
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            uploaded_file.status = STATUS_ERROR
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            pass

        # Celeryの自動リトライ機能を使用
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, max_retries=3)
def generate_hls_async(self, uploaded_file_id):
    """
    動画ファイルをHLS形式に変換する非同期タスク

    Args:
        uploaded_file_id (str): UploadedFileのUUID

    Returns:
        dict: 実行結果
    """
    try:
        processing_logger.info(f"Starting HLS generation for uploaded_file_id: {uploaded_file_id}")

        # UploadedFile取得
        uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)

        # デバッグ情報
        processing_logger.info(f"File name: {uploaded_file.file.name}")
        processing_logger.info(f"File path: {uploaded_file.file.path}")
        processing_logger.info(f"Organization ID: {uploaded_file.organization.id}")

        # 正しいファイルパスを構築
        file_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.file.name)
        processing_logger.info(f"Constructed file path: {file_path}")

        # ファイルの存在確認
        if not os.path.exists(file_path):
            processing_logger.error(f"File does not exist at path: {file_path}")
            raise Exception(f"File not found: {file_path}")

        # 動画ファイルチェック
        if not file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            processing_logger.info(f"File is not a video, skipping HLS generation: {file_path}")
            return {"success": False, "reason": "Not a video file"}

        # HLS出力ディレクトリ作成
        hls_base_dir = os.path.join(settings.MEDIA_ROOT, 'hls')
        os.makedirs(hls_base_dir, exist_ok=True)

        output_dir = os.path.join(hls_base_dir, str(uploaded_file_id))
        os.makedirs(output_dir, exist_ok=True)

        # HLSパスを先に保存（フロントエンドの即座取得のため）
        uploaded_file.hls_playlist_path = f"hls/{uploaded_file_id}/master.m3u8"
        uploaded_file.save()
        processing_logger.info(f"HLS path saved before generation: {uploaded_file.hls_playlist_path}")

        # ffmpegコマンド（メモリ効率重視）
        playlist_path = os.path.join(output_dir, 'playlist.m3u8')

        # マルチバリアント（複数画質）対応
        variants = [
            # 低画質（モバイル向け）
            {
                'name': '360p',
                'video_bitrate': '500k',
                'audio_bitrate': '64k',
                'resolution': '640x360',
                'maxrate': '550k',
                'bufsize': '1000k'
            },
            # 中画質（デフォルト）
            {
                'name': '720p',
                'video_bitrate': '1500k',
                'audio_bitrate': '128k',
                'resolution': '1280x720',
                'maxrate': '1650k',
                'bufsize': '3000k'
            }
        ]

        # マスタープレイリスト作成
        master_playlist_path = os.path.join(output_dir, 'master.m3u8')
        master_content = "#EXTM3U\n#EXT-X-VERSION:3\n"

        # ハードウェアアクセラレーション検出
        def detect_hardware_acceleration():
            """利用可能なハードウェアアクセラレーションを検出"""
            try:
                # NVIDIA GPU (NVENC)
                result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                                      capture_output=True, text=True)
                if 'h264_nvenc' in result.stdout:
                    return 'nvenc'

                # Intel Quick Sync (QSV)
                if 'h264_qsv' in result.stdout:
                    return 'qsv'

                # AMD VCE
                if 'h264_amf' in result.stdout:
                    return 'amf'

                # Apple VideoToolbox (macOS)
                if 'h264_videotoolbox' in result.stdout:
                    return 'videotoolbox'

            except Exception as e:
                processing_logger.warning(f"Hardware acceleration detection failed: {e}")

            return None

        # 並列処理用の関数
        def process_variant(variant):
            variant_dir = os.path.join(output_dir, variant['name'])
            os.makedirs(variant_dir, exist_ok=True)

            variant_playlist = os.path.join(variant_dir, 'playlist.m3u8')

            # ハードウェアアクセラレーション設定
            hw_accel = detect_hardware_acceleration()
            processing_logger.info(f"Detected hardware acceleration: {hw_accel}")

            # ffmpegコマンド構築（最適化版）
            cmd = ['ffmpeg', '-i', file_path]

            # ハードウェアアクセラレーション適用
            if hw_accel == 'nvenc':
                cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'p4'])  # NVENC preset
            elif hw_accel == 'qsv':
                cmd.extend(['-c:v', 'h264_qsv', '-preset', 'fast'])
            elif hw_accel == 'amf':
                cmd.extend(['-c:v', 'h264_amf', '-quality', 'speed'])
            elif hw_accel == 'videotoolbox':
                cmd.extend(['-c:v', 'h264_videotoolbox', '-allow_sw', '1'])
            else:
                # ソフトウェアエンコーディング（デフォルト）
                cmd.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'zerolatency'])

            # 共通設定
            cmd.extend([
                '-b:v', variant['video_bitrate'],
                '-maxrate', variant['maxrate'],
                '-bufsize', variant['bufsize'],
                '-vf', f"scale={variant['resolution']}",
                '-g', '60',  # GOP size (2秒間隔でキーフレーム at 30fps)
                '-sc_threshold', '0',  # シーンチェンジ検出無効化
                '-c:a', 'aac',
                '-b:a', variant['audio_bitrate'],
                '-ac', '2',
                '-f', 'hls',
                '-hls_time', '6',  # 6秒セグメント（高速化）
                '-hls_playlist_type', 'vod',
                '-hls_segment_filename', os.path.join(variant_dir, 'segment_%03d.ts'),
                '-hls_flags', 'delete_segments',
                '-y',
                variant_playlist
            ])

            # 実行
            processing_logger.info(f"Executing ffmpeg for {variant['name']}: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                processing_logger.error(f"ffmpeg error for {variant['name']}: {result.stderr}")
                return None, f"ffmpeg failed for {variant['name']}: {result.stderr}"

            # 成功時の戻り値
            bandwidth = int(variant['video_bitrate'].rstrip('k')) * 1000 + int(variant['audio_bitrate'].rstrip('k')) * 1000
            return {
                'name': variant['name'],
                'bandwidth': bandwidth,
                'resolution': variant['resolution']
            }, None

        # 並列実行（最大2並列：360pと720pを同時実行）
        processing_logger.info("Starting parallel HLS generation")
        successful_variants = []

        # CPU コア数に応じたワーカー数調整（最小2、最大4）
        max_workers = min(2, max(1, multiprocessing.cpu_count() // 2))
        processing_logger.info(f"Using {max_workers} workers for parallel processing")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_variant = {executor.submit(process_variant, variant): variant for variant in variants}

            for future in concurrent.futures.as_completed(future_to_variant):
                variant = future_to_variant[future]
                try:
                    result, error = future.result(timeout=1800)  # 30分タイムアウト
                    if result:
                        successful_variants.append(result)
                        processing_logger.info(f"Successfully processed variant: {result['name']}")
                    else:
                        processing_logger.error(f"Failed to process variant {variant['name']}: {error}")
                        # 360p失敗は致命的エラー
                        if variant['name'] == '360p':
                            raise Exception(error)
                except concurrent.futures.TimeoutError:
                    processing_logger.error(f"Variant {variant['name']} timed out after 30 minutes")
                    if variant['name'] == '360p':
                        raise Exception(f"Critical timeout in 360p variant")
                except Exception as exc:
                    processing_logger.error(f"Variant {variant['name']} generated an exception: {exc}")
                    if variant['name'] == '360p':
                        raise Exception(f"Critical failure in 360p variant: {exc}")

        # 成功したバリアントでマスタープレイリスト作成
        if not successful_variants:
            raise Exception("No variants were successfully processed")

        for variant_info in successful_variants:
            master_content += f"#EXT-X-STREAM-INF:BANDWIDTH={variant_info['bandwidth']},RESOLUTION={variant_info['resolution']}\n"
            master_content += f"{variant_info['name']}/playlist.m3u8\n"

        # マスタープレイリスト保存
        with open(master_playlist_path, 'w') as f:
            f.write(master_content)

        processing_logger.info(f"HLS generation completed for uploaded_file_id: {uploaded_file_id}")
        return {
            "success": True,
            "uploaded_file_id": str(uploaded_file_id),
            "hls_url": f"/media/hls/{uploaded_file_id}/master.m3u8"
        }

    except Exception as e:
        processing_logger.error(f"Error in HLS generation: {e}")

        # メモリ不足やタイムアウトの場合は再試行しない
        if 'memory' in str(e).lower() or 'timeout' in str(e).lower():
            try:
                uploaded_file.status = STATUS_ERROR
                uploaded_file.save()
            except:
                pass
            processing_logger.error(f"Non-retryable error in HLS generation: {e}")
            return {"success": False, "error": str(e)}

        raise self.retry(exc=e, countdown=300)  # 5分後にリトライ
