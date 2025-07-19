# プロジェクトガイドライン for Claude

## コーディング規約

### 1. 改行とインデント
- 空白行にはスペースを入れない
- インデントはスペース4つを使用
- ファイルの最後には改行を入れる

### 2. インポート
- `Status`などのEnumクラスはモデルクラス経由でアクセスする
  ```python
  # 良い例
  UploadedFile.Status.PROCESSING
  
  # 避ける例
  from voice_picker.models.uploaded_file import Status
  Status.PROCESSING
  ```

### 3. エラーハンドリング
- 適切なログを記録する
- エラー時は状態を適切に更新する

## 文字起こしAPI設定

### 利用可能なプロバイダー
1. **OpenAI** (デフォルト)
   - 環境変数: `TRANSCRIPTION_PROVIDER=openai`
   - APIキー: `OPENAI_API_KEY`

2. **LemonFox.ai**
   - 環境変数: `TRANSCRIPTION_PROVIDER=lemonfox`
   - APIキー: `LEMONFOX_API_KEY`
   - 特徴: 話者分離機能内蔵、コスト効率が良い

3. **Whisper** (ローカル)
   - 環境変数: `TRANSCRIPTION_PROVIDER=whisper`
   - ローカルモデルを使用

### 切り替え方法
`.env`ファイルで`TRANSCRIPTION_PROVIDER`を設定して、コンテナを再起動する。

## Zoom SDK設定

### 開発環境
- 現在は開発用のSDKキーを使用中
- 実際のZoom会議には接続不可

### 本番環境への移行
1. Zoom App Marketplaceでアプリを本番申請
2. 承認後、本番用のSDK Key/Secretを取得
3. `.env.production`ファイルに本番用認証情報を設定
4. 環境変数を切り替えてコンテナを再起動

## テストコマンド

### 文字起こしテスト
```bash
docker compose exec django python manage.py transcribe
```

### 環境確認
```bash
docker compose logs django
docker compose logs celery
docker compose logs zoom_bot_server
```

## 注意事項
- 本番用のAPIキーは`.env.production`に保存
- 開発用のAPIキーは`.env.development`に保存
- コミット時は機密情報を含まないよう注意