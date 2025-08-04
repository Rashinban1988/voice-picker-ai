# キャッシュ問題の解決ガイド

## 問題の原因
UIを変更しても通常のリロードで前のUIに戻ってしまう問題は、静的ファイル（CSS、JavaScript）のキャッシュ戦略が適切に設定されていないことが原因です。

## 実施した修正

### 1. WhiteNoiseの導入
静的ファイルの配信とキャッシュ制御を改善するために、WhiteNoiseを導入しました。

#### インストール
```bash
pip install whitenoise
```

#### 設定の変更（config/settings.py）
- `whitenoise.middleware.WhiteNoiseMiddleware`をMIDDLEWAREに追加
- `STATICFILES_STORAGE`を設定してファイルのハッシュ値を含むファイル名を生成
- 開発環境と本番環境で異なるキャッシュ期間を設定

### 2. Cache Busterスクリプトの追加
開発環境でのキャッシュ問題を回避するため、`static/js/cache-buster.js`を追加しました。
このスクリプトは開発環境でのみ動作し、CSS/JSファイルにバージョンパラメータを追加します。

## 適用手順

### 1. 依存関係のインストール
```bash
docker compose exec django pip install whitenoise
```

### 2. 静的ファイルの収集
```bash
docker compose exec django python manage.py collectstatic --noinput --clear
```

### 3. Djangoサーバーの再起動
```bash
docker compose restart django
```

## Tailwind CSSのビルド

Tailwind CSSを使用している場合は、変更後に必ずビルドを実行してください：

```bash
# Tailwind CSSの開発モード（自動ビルド）
docker compose exec django python manage.py tailwind start

# または本番ビルド
docker compose exec django python manage.py tailwind build
```

## 開発時のベストプラクティス

1. **CSSファイルの変更後**
   ```bash
   docker compose exec django python manage.py tailwind build
   docker compose exec django python manage.py collectstatic --noinput
   ```

2. **強制リロード**
   - Chrome/Firefox: `Ctrl+Shift+R` (Windows/Linux) または `Cmd+Shift+R` (Mac)
   - ブラウザの開発者ツールを開いた状態でリロードボタンを右クリック → "Empty Cache and Hard Reload"

3. **開発者ツールでキャッシュを無効化**
   - Chrome DevTools → Network タブ → "Disable cache" にチェック
   - この設定は開発者ツールが開いている間のみ有効

## トラブルシューティング

### 問題が解決しない場合

1. **ブラウザキャッシュをクリア**
   ```
   設定 → プライバシーとセキュリティ → 閲覧履歴データの削除 → キャッシュされた画像とファイル
   ```

2. **Djangoの静的ファイルを再収集**
   ```bash
   docker compose exec django python manage.py collectstatic --noinput --clear
   ```

3. **WhiteNoiseの設定を確認**
   ```python
   # settings.pyで以下が設定されているか確認
   STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
   ```

4. **開発サーバーのログを確認**
   ```bash
   docker compose logs -f django
   ```

## 本番環境での推奨設定

本番環境では、Nginxなどのリバースプロキシで追加のキャッシュヘッダーを設定することを推奨します：

```nginx
location /static/ {
    alias /path/to/staticfiles/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## 参考リンク
- [WhiteNoise Documentation](http://whitenoise.evans.io/)
- [Django Static Files](https://docs.djangoproject.com/en/5.0/howto/static-files/)
- [django-tailwind Documentation](https://django-tailwind.readthedocs.io/)