# サーバの設定

---

## ssh接続用の設定

### 1. とりあえずssh接続するための設定

- VPSサーバのパケットフィルターにて、22番ポートを開放
- ssh接続用の鍵を作成（VPS管理画面から鍵を作成）
- 鍵をダウンロード
- 鍵を~/.ssh/に配置
- 鍵のパーミッションを600に設定

```bash
chmod 600 ~/.ssh/xserver/MacYama.pem
```

---

### 2. セキュアにするためにssh接続の設定を変更

- sshd_configを編集

```bash
sudo vi /etc/ssh/sshd_config
```

- パスワード認証を無効にする

```bash
PasswordAuthentication no
```

- 公開鍵認証を有効にする

```bash
PubkeyAuthentication yes
```

- ログインユーザを制限する

```bash
AllowUsers root
```

`coding-rules.mdc`を参照しました。

`vpi`というユーザーを作成し、SSH公開鍵認証で利用できるようにする手順をまとめます。

---

## vpiユーザー作成とSSH公開鍵認証の設定手順

### 1. ユーザーの作成

```bash
sudo adduser vpi
```
- パスワードや情報入力を求められますが、パスワードは空欄でもOKです（後でパスワード認証を無効化するため）。

---

### 2. vpiユーザーにsudo権限を付与（必要な場合）

```bash
sudo usermod -aG sudo vpi
```

---

### 3. vpiユーザーのSSHディレクトリ作成

```bash
sudo mkdir -p /home/vpi/.ssh
sudo chmod 700 /home/vpi/.ssh
sudo chown vpi:vpi /home/vpi/.ssh
```

---

### 4. 公開鍵の登録

- ローカルPCの公開鍵（例：`~/.ssh/xserver/MacYama.pem.pub`や`id_rsa.pub`など）を
  `/home/vpi/.ssh/authorized_keys` にコピーします。

```bash
# 例: rootユーザーで作業中の場合
sudo cp /root/.ssh/authorized_keys /home/vpi/.ssh/authorized_keys
sudo chown vpi:vpi /home/vpi/.ssh/authorized_keys
sudo chmod 600 /home/vpi/.ssh/authorized_keys
```
- もしくは、ローカルPCから直接転送も可能です（`ssh-copy-id`コマンドなど）。

---

### 5. SSH設定の確認

- `/etc/ssh/sshd_config` で以下を確認してください。

```
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers vpi
PermitRootLogin no
```

---

### 6. SSHサービスの再起動

```bash
sudo systemctl restart sshd
```

---

### 7. vpiユーザーでSSH接続テスト

```bash
ssh -p 22 vpi@85.131.248.243
```

---

## 注意点

- 公開鍵が正しく登録されていないとログインできません。
- 必要に応じて`sudo`権限を付与してください。
- rootでの作業中は、必ず別ターミナルでvpiユーザーのSSH接続テストを行い、成功を確認してからrootセッションを閉じてください。

---

# Google ChromeのAPTリポジトリの公開鍵（GPGキー）をインストール

## 公開鍵をインストール
```bash
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
```

## リポジトリを追加
```bash
echo "deb [signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
```

## リポジトリを更新
```bash
sudo apt update
```
