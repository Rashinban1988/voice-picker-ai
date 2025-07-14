import os
import tempfile
import logging
import subprocess
import json
from pathlib import Path
from celery import shared_task
from django.conf import settings
from .models import UploadedFile, Transcription
from .views import transcribe_and_save

processing_logger = logging.getLogger('processing')

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
            uploaded_file.status = UploadedFile.Status.PROCESSING
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            processing_logger.error(f"UploadedFile with id {uploaded_file_id} not found")
            return {"success": False, "error": "UploadedFile not found"}

        # 文字起こし実行
        success = transcribe_and_save(file_path, uploaded_file_id)

        if success:
            # 成功時はステータスを完了に更新
            uploaded_file.status = UploadedFile.Status.COMPLETED
            uploaded_file.save()
            processing_logger.info(f"Transcription completed successfully for uploaded_file_id: {uploaded_file_id}")
            return {"success": True, "uploaded_file_id": uploaded_file_id}
        else:
            # 失敗時はステータスをエラーに更新
            uploaded_file.status = UploadedFile.Status.ERROR
            uploaded_file.save()
            processing_logger.error(f"Transcription failed for uploaded_file_id: {uploaded_file_id}")
            return {"success": False, "error": "Transcription failed"}

    except Exception as e:
        processing_logger.error(f"Error in async transcription task: {e}")

        # エラー時もステータスを更新
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            uploaded_file.status = UploadedFile.Status.ERROR
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
        file_path = uploaded_file.file.path

        # 動画ファイルチェック
        if not file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            processing_logger.info(f"File is not a video, skipping HLS generation: {file_path}")
            return {"success": False, "reason": "Not a video file"}

        # HLS出力ディレクトリ作成
        hls_base_dir = os.path.join(settings.MEDIA_ROOT, 'hls')
        os.makedirs(hls_base_dir, exist_ok=True)

        output_dir = os.path.join(hls_base_dir, str(uploaded_file_id))
        os.makedirs(output_dir, exist_ok=True)

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

        for variant in variants:
            variant_dir = os.path.join(output_dir, variant['name'])
            os.makedirs(variant_dir, exist_ok=True)

            variant_playlist = os.path.join(variant_dir, 'playlist.m3u8')

            # ffmpegコマンド構築（低メモリ使用）
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-preset', 'ultrafast',  # 高速・低CPU使用
                '-threads', '2',  # CPU使用を制限
                '-c:v', 'h264',
                '-b:v', variant['video_bitrate'],
                '-maxrate', variant['maxrate'],
                '-bufsize', variant['bufsize'],
                '-vf', f"scale={variant['resolution']}",
                '-c:a', 'aac',
                '-b:a', variant['audio_bitrate'],
                '-ac', '2',
                '-f', 'hls',
                '-hls_time', '10',  # 10秒セグメント
                '-hls_playlist_type', 'vod',  # VOD用
                '-hls_segment_filename', os.path.join(variant_dir, 'segment_%03d.ts'),
                '-hls_flags', 'delete_segments',  # 一時ファイル削除
                variant_playlist
            ]

            # 実行
            processing_logger.info(f"Executing ffmpeg for {variant['name']}: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                processing_logger.error(f"ffmpeg error for {variant['name']}: {result.stderr}")
                # 低画質の変換に失敗した場合のみリトライ
                if variant['name'] == '360p':
                    raise Exception(f"ffmpeg failed: {result.stderr}")
                else:
                    # 高画質変換失敗は警告のみ
                    processing_logger.warning(f"Skipping {variant['name']} variant due to error")
                    continue

            # マスタープレイリストに追加
            bandwidth = int(variant['video_bitrate'].rstrip('k')) * 1000 + int(variant['audio_bitrate'].rstrip('k')) * 1000
            master_content += f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={variant['resolution']}\n"
            master_content += f"{variant['name']}/playlist.m3u8\n"

        # マスタープレイリスト保存
        with open(master_playlist_path, 'w') as f:
            f.write(master_content)

        # UploadedFileにHLS情報を保存
        uploaded_file.hls_playlist_path = f"hls/{uploaded_file_id}/master.m3u8"
        uploaded_file.save()

        processing_logger.info(f"HLS generation completed for uploaded_file_id: {uploaded_file_id}")
        return {
            "success": True,
            "uploaded_file_id": str(uploaded_file_id),
            "hls_url": f"/media/hls/{uploaded_file_id}/master.m3u8"
        }

    except Exception as e:
        processing_logger.error(f"Error in HLS generation: {e}")
        raise self.retry(exc=e, countdown=300)  # 5分後にリトライ
