# Docker Composeのインストール

## Dockerのインストール

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

## Docker Composeのインストール

```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## Docker Composeのバージョン確認

```bash
docker compose version
```

## Dokeグループにユーザを追加

```bash
sudo usermod -aG docker $USER
```

## 変更を反映

```bash
newgrp docker
```

## git hubから各プロジェクトをクローン

### 1. sshキーの作成

```bash
ssh-keygen -t ed25519 -C "rashinban1988@gmail.com" -f ~/.ssh/id_ed25519 -N ""
```

### 2. sshキーの配置

```bash
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
```

### 3. git hubから各プロジェクトをクローン

```bash
git clone リポジトリURL
```
