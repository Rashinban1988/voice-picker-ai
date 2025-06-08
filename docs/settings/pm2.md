# pm2でnextjsを起動

## nvmのインストール

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
```

## nvmの有効化

```bash
export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

## nodeのインストール

```bash
nvm install 20
nvm use 20
```

## nodeのバージョン確認

```bash
node -v
npm -v
```

- node -vがv20.x.xになっていればOKです。
- npm -vが10.x.xになっていればOKです。

## pm2のインストール

```bash
sudo npm install -g pm2
```

## nextjsのビルド

```bash
npm run build
```

## nextjsの起動

```bash
pm2 start npm --name "nextjs" -- run start
```

## pm2の確認

```bash
pm2 list
```

## pm2の停止

```bash
pm2 stop nextjs
```

## pm2の再起動

```bash
pm2 restart nextjs
```

## pm2設定の保存

```bash
pm2 save
```
