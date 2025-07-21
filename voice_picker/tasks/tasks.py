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

            # 文字起こし完了後に要約・課題・取り組み案を生成
            try:
                processing_logger.info(f"Starting AI analysis for uploaded_file_id: {uploaded_file_id}")
                generate_ai_analysis_async.delay(uploaded_file_id)
                processing_logger.info(f"AI analysis task queued for uploaded_file_id: {uploaded_file_id}")
            except Exception as analysis_error:
                processing_logger.error(f"Failed to queue AI analysis: {analysis_error}")

            # 動画ファイルの場合、文字起こし完了後にHLS変換を開始
            try:
                if uploaded_file.file.name.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm')):
                    processing_logger.info(f"Queuing HLS task for video file {uploaded_file_id} after transcription")
                    generate_hls_async.delay(uploaded_file_id)
                    processing_logger.info(f"HLS task queued for uploaded_file_id: {uploaded_file_id}")
            except Exception as hls_error:
                processing_logger.error(f"Failed to queue HLS task: {hls_error}")

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
def generate_ai_analysis_async(self, uploaded_file_id):
    """
    文字起こし完了後にAI分析（要約・課題・取り組み案）を生成する非同期タスク

    Args:
        uploaded_file_id (str): UploadedFileのUUID

    Returns:
        dict: 実行結果
    """
    try:
        processing_logger.info(f"Starting AI analysis for uploaded_file_id: {uploaded_file_id}")

        # UploadedFile取得
        uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)

        # 文字起こしデータを取得
        transcriptions = Transcription.objects.filter(uploaded_file=uploaded_file).order_by('start_time')

        if not transcriptions.exists():
            processing_logger.error(f"No transcriptions found for uploaded_file_id: {uploaded_file_id}")
            return {"success": False, "error": "No transcriptions found"}

        # 文字起こしテキストを結合
        full_text = " ".join([t.text for t in transcriptions])
        processing_logger.info(f"Combined transcription text length: {len(full_text)} characters")

        # 既存のAI分析関数を使用
        from ..views import summarize_text, definition_issue, definition_solution

        try:
            # 要約を生成
            processing_logger.info("Generating summary...")
            summary = summarize_text(full_text)

            # 課題を特定
            processing_logger.info("Identifying issues...")
            issues = definition_issue(full_text)

            # 取り組み案を生成
            processing_logger.info("Generating solutions...")
            solutions = definition_solution(full_text)

            # 結果をデータベースに保存
            uploaded_file.summarization = summary
            uploaded_file.issue = issues
            uploaded_file.solution = solutions
            uploaded_file.save()

            processing_logger.info(f"AI analysis completed successfully for uploaded_file_id: {uploaded_file_id}")
            return {
                "success": True,
                "uploaded_file_id": uploaded_file_id,
                "analysis": {
                    "summary": summary,
                    "issues": issues,
                    "solutions": solutions
                }
            }

        except Exception as analysis_error:
            processing_logger.error(f"AI analysis failed: {analysis_error}")
            return {"success": False, "error": f"AI analysis failed: {analysis_error}"}

    except UploadedFile.DoesNotExist:
        processing_logger.error(f"UploadedFile with id {uploaded_file_id} not found")
        return {"success": False, "error": "UploadedFile not found"}

    except Exception as e:
        processing_logger.error(f"Error in AI analysis task: {e}")

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

        # HLS生成開始（パスは完了時に保存）
        processing_logger.info(f"HLS generation starting for: {uploaded_file_id}")

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
                # NVIDIA GPU (NVENC) - 実際に使用可能か検証
                result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                                      capture_output=True, text=True)
                if 'h264_nvenc' in result.stdout:
                    # NVENCが実際に使用可能かテスト
                    test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                               '-c:v', 'h264_nvenc', '-f', 'null', '-']
                    test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                    if test_result.returncode == 0:
                        processing_logger.info("NVENC hardware acceleration available and working")
                        return 'nvenc'
                    else:
                        processing_logger.warning("NVENC listed but not functional, falling back to software")

                # Intel Quick Sync (QSV)
                if 'h264_qsv' in result.stdout:
                    test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                               '-c:v', 'h264_qsv', '-f', 'null', '-']
                    test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                    if test_result.returncode == 0:
                        processing_logger.info("QSV hardware acceleration available and working")
                        return 'qsv'

                # AMD VCE
                if 'h264_amf' in result.stdout:
                    test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                               '-c:v', 'h264_amf', '-f', 'null', '-']
                    test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                    if test_result.returncode == 0:
                        processing_logger.info("AMF hardware acceleration available and working")
                        return 'amf'

                # Apple VideoToolbox (macOS)
                if 'h264_videotoolbox' in result.stdout:
                    test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                               '-c:v', 'h264_videotoolbox', '-f', 'null', '-']
                    test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                    if test_result.returncode == 0:
                        processing_logger.info("VideoToolbox hardware acceleration available and working")
                        return 'videotoolbox'

            except subprocess.TimeoutExpired:
                processing_logger.warning("Hardware acceleration test timed out")
            except Exception as e:
                processing_logger.warning(f"Hardware acceleration detection failed: {e}")

            processing_logger.info("No working hardware acceleration found, using software encoding")
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

        # CPU コア数とファイルサイズに応じたワーカー数調整
        cpu_count = multiprocessing.cpu_count()
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024
        
        # 大容量ファイル（300MB以上）または低メモリ環境では並列処理無効
        if settings.SYSTEM_MEMORY_GB <= 8 or file_size_mb > 300:
            max_workers = 1  # 順次処理でメモリ安全
            processing_logger.info(f"Large file ({file_size_mb:.1f}MB) or low memory environment: using sequential processing")
        else:
            # 小容量ファイルでメモリ十分な場合のみ並列処理
            max_workers = min(2, max(1, cpu_count // 2))  # 最大2並列に制限
            processing_logger.info(f"Small file ({file_size_mb:.1f}MB): using parallel processing")
        
        processing_logger.info(f"Using {max_workers} workers for HLS generation")

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

        # HLSプレイリストパスをデータベースに保存
        try:
            uploaded_file.hls_playlist_path = f"hls/{uploaded_file_id}/master.m3u8"
            uploaded_file.status = STATUS_COMPLETED
            uploaded_file.save()
            processing_logger.info(f"HLS playlist path saved: {uploaded_file.hls_playlist_path}")
        except Exception as save_error:
            processing_logger.error(f"Failed to save HLS playlist path: {save_error}")

        processing_logger.info(f"HLS generation completed for uploaded_file_id: {uploaded_file_id}")
        return {
            "success": True,
            "uploaded_file_id": str(uploaded_file_id),
            "hls_url": f"/media/hls/{uploaded_file_id}/master.m3u8"
        }

    except Exception as e:
        processing_logger.error(f"Error in HLS generation: {e}")

        # ハードウェアエンコーダーエラー、メモリ不足、タイムアウトの場合は再試行しない
        error_str = str(e).lower()
        non_retryable_errors = [
            'memory', 'timeout', 'nvenc', 'qsv', 'amf', 'videotoolbox',
            'cannot load libcuda', 'encoder not found', 'codec not found',
            'hardware acceleration', 'libcuda.so', 'nvidia'
        ]

        if any(error in error_str for error in non_retryable_errors):
            try:
                uploaded_file.status = STATUS_ERROR
                uploaded_file.save()
            except:
                pass
            processing_logger.error(f"Non-retryable error in HLS generation: {e}")
            return {"success": False, "error": str(e)}

        # その他のエラーのみリトライ（最大3回、5分間隔）
        raise self.retry(exc=e, countdown=300)  # 5分後にリトライ
