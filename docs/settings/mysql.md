# MySQLのインストール

## gitからclone

```bash
git clone web-db .
```

## docker composeを起動

```bash
docker compose up -d
```

## コンテナに入る

```bash
docker exec -it web-db-mysql-1 mysql -uroot -p
```

## データベースの作成

```bash
CREATE DATABASE djanto_app;
```

## sailユーザへの権限の付与

```bash
GRANT ALL PRIVILEGES ON djanto_app.* TO 'sail'@'%';
FLUSH PRIVILEGES;
```
