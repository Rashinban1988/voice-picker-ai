#!/bin/bash

# ログバックアップスクリプト
# 1週間以上経過したログファイルをlogs/backup/年/月/ディレクトリに移動する

set -e

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_ROOT/logs"
BACKUP_DIR="$LOGS_DIR/backup"

# ログ出力関数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# バックアップディレクトリが存在しない場合は作成
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    log "Created backup directory: $BACKUP_DIR"
fi

# 現在の日付から1週間前の日付を計算
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CUTOFF_DATE=$(date -v-7d '+%Y-%m-%d')
else
    # Linux
    CUTOFF_DATE=$(date -d '7 days ago' '+%Y-%m-%d')
fi

log "Starting log backup process. Cutoff date: $CUTOFF_DATE"

# ログディレクトリ内のファイルを処理
moved_count=0
total_size=0

for log_file in "$LOGS_DIR"/*.log; do
    # ファイルが存在しない場合はスキップ
    [ ! -f "$log_file" ] && continue

    filename=$(basename "$log_file")

    # ファイル名から日付を抽出（例: api2025-06-08.log -> 2025-06-08）
    if [[ $filename =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
        file_date="${BASH_REMATCH[1]}"

        # 日付比較（文字列比較で十分）
        if [[ "$file_date" < "$CUTOFF_DATE" ]]; then
            # 年月を抽出
            year=$(echo "$file_date" | cut -d'-' -f1)
            month=$(echo "$file_date" | cut -d'-' -f2)

            # バックアップディレクトリ作成
            backup_subdir="$BACKUP_DIR/$year/$month"
            mkdir -p "$backup_subdir"

            # ファイルサイズを取得
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                file_size=$(stat -f%z "$log_file")
            else
                # Linux
                file_size=$(stat -f%s "$log_file" 2>/dev/null || stat -c%s "$log_file")
            fi

            # ファイルを移動
            mv "$log_file" "$backup_subdir/"

            if [ $? -eq 0 ]; then
                log "Moved: $filename -> $backup_subdir/"
                ((moved_count++))
                ((total_size+=file_size))
            else
                log "ERROR: Failed to move $filename"
            fi
        fi
    else
        log "WARNING: Could not extract date from filename: $filename"
    fi
done

# 結果を人間が読める形式で表示
if [ $moved_count -gt 0 ]; then
    # ファイルサイズを人間が読める形式に変換
    if command -v numfmt >/dev/null 2>&1; then
        # GNU coreutilsのnumfmtが利用可能な場合
        readable_size=$(numfmt --to=iec-i --suffix=B $total_size)
    else
        # numfmtが利用できない場合の簡易変換
        if [ $total_size -gt 1073741824 ]; then
            readable_size="$(($total_size / 1073741824))GB"
        elif [ $total_size -gt 1048576 ]; then
            readable_size="$(($total_size / 1048576))MB"
        elif [ $total_size -gt 1024 ]; then
            readable_size="$(($total_size / 1024))KB"
        else
            readable_size="${total_size}B"
        fi
    fi

    log "Backup completed successfully. Moved $moved_count files ($readable_size total)"
else
    log "No files to backup (all files are newer than $CUTOFF_DATE)"
fi

# バックアップディレクトリの構造を表示（デバッグ用）
if [ $moved_count -gt 0 ]; then
    log "Current backup directory structure:"
    if command -v tree >/dev/null 2>&1; then
        tree "$BACKUP_DIR" -I '__pycache__|*.pyc'
    else
        find "$BACKUP_DIR" -type f -name "*.log" | head -10 | while read -r file; do
            log "  $(echo "$file" | sed "s|$BACKUP_DIR/||")"
        done
        if [ $(find "$BACKUP_DIR" -type f -name "*.log" | wc -l) -gt 10 ]; then
            log "  ... and more files"
        fi
    fi
fi

log "Log backup process completed"
