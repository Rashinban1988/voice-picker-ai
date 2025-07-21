#!/usr/bin/env python3
"""
メモリ使用量監視スクリプト
"""
import os
import psutil
import logging
import time
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Monitor memory usage and send alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=int,
            default=80,
            help='Memory usage threshold percentage (default: 80)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Check interval in seconds (default: 60)'
        )
    
    def handle(self, *args, **options):
        threshold = options['threshold']
        interval = options['interval']
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        logger.info(f"Starting memory monitor - Threshold: {threshold}%, Interval: {interval}s")
        
        consecutive_alerts = 0
        max_consecutive = 3
        
        while True:
            try:
                # システム全体のメモリ使用量
                memory = psutil.virtual_memory()
                usage_percent = memory.percent
                
                # プロセス別メモリ使用量
                current_process = psutil.Process()
                process_memory = current_process.memory_info().rss / 1024 / 1024  # MB
                
                # Djangoプロセスのメモリ使用量
                django_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
                    try:
                        if proc.info['cmdline'] and any('manage.py' in cmd for cmd in proc.info['cmdline']):
                            django_processes.append({
                                'pid': proc.info['pid'],
                                'memory_mb': proc.info['memory_info'].rss / 1024 / 1024
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # ログ出力
                logger.info(f"System Memory: {usage_percent:.1f}% ({memory.used/1024/1024/1024:.1f}GB/{memory.total/1024/1024/1024:.1f}GB)")
                logger.info(f"Current Process: {process_memory:.1f}MB")
                
                for django_proc in django_processes:
                    logger.info(f"Django Process {django_proc['pid']}: {django_proc['memory_mb']:.1f}MB")
                
                # アラート判定
                if usage_percent > threshold:
                    consecutive_alerts += 1
                    logger.warning(f"HIGH MEMORY USAGE ALERT! {usage_percent:.1f}% (consecutive: {consecutive_alerts})")
                    
                    if consecutive_alerts >= max_consecutive:
                        logger.critical(f"CRITICAL: Memory usage above {threshold}% for {consecutive_alerts} consecutive checks!")
                        
                        # 緊急時の対策を実行
                        self.emergency_cleanup(logger)
                        consecutive_alerts = 0
                else:
                    consecutive_alerts = 0
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Memory monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(interval)
    
    def emergency_cleanup(self, logger):
        """緊急時のクリーンアップ処理"""
        try:
            import gc
            import django
            from django.core.cache import cache
            
            logger.info("Executing emergency cleanup...")
            
            # ガベージコレクション強制実行
            collected = gc.collect()
            logger.info(f"Garbage collection freed {collected} objects")
            
            # Djangoキャッシュクリア
            try:
                cache.clear()
                logger.info("Django cache cleared")
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")
            
            # メモリ使用量再確認
            memory = psutil.virtual_memory()
            logger.info(f"Memory after cleanup: {memory.percent:.1f}%")
            
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")