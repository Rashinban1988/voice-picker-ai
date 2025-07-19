# Zoom General App 設定ガイド

## 1. Meeting SDK機能の有効化

### Features タブで以下を設定:

1. **Embed Meeting SDK** を有効化
   - Toggle ON にする
   - 「Use Meeting SDK」にチェック

2. **必要な機能を選択**:
   - ✅ Join meeting as a participant
   - ✅ Access raw audio stream
   - ✅ Start local recording
   - ✅ Access raw video stream (オプション)

## 2. 認証情報の確認

### App Credentials タブで確認:

1. **OAuth Credentials**:
   ```
   Client ID: [OAuth認証用]
   Client Secret: [OAuth認証用]
   ```

2. **Meeting SDK Credentials**:
   ```
   SDK Key: [Meeting SDK用]
   SDK Secret: [Meeting SDK用]
   ```

   ※ Meeting SDK Credentialsが表示されない場合は、Featuresタブで「Embed Meeting SDK」が有効になっているか確認

## 3. Scopes (権限) の設定

### Scopes タブで以下を追加:

- meeting:write
- meeting:read  
- recording:write
- recording:read
- user:read

## 4. Domain Allow List

### App Credentials タブで設定:

```
http://localhost:4000
http://localhost:3000
http://127.0.0.1:4000
http://127.0.0.1:3000
```

## 5. Redirect URLs for OAuth

```
http://localhost:4000/auth/callback
http://localhost:3000/auth/callback
```

## トラブルシューティング

### Meeting SDK Credentialsが表示されない場合:

1. Featuresタブを確認
2. 「Embed Meeting SDK」または「Meeting SDK」を探して有効化
3. ページをリロード
4. App Credentialsタブに戻る

### 「Add Feature」ボタンがある場合:

1. 「Add Feature」をクリック
2. 「Meeting SDK」を選択
3. 必要な設定を行う
4. 保存

## 確認すべきポイント

- General Appタイプであることを確認
- Meeting SDK機能が有効になっているか
- Development環境で作業しているか
- 必要なScopesが全て選択されているか