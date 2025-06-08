# nginxのインストール

```bash
sudo apt update
sudo apt install nginx
```

## nginxの設定

### djangoの設定

```bash
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    client_max_body_size 1G;
    server_name django.voice-picker-ai.com;

    ssl_certificate /etc/letsencrypt/live/django.voice-picker-ai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/django.voice-picker-ai.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://localhost:88;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name django.voice-picker-ai.com;
    return 301 https://$host$request_uri;
}
```

### nextjsの設定

```bash
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name voice-picker-ai.com;

    ssl_certificate /etc/letsencrypt/live/voice-picker-ai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/voice-picker-ai.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name voice-picker-ai.com;
    return 301 https://$host$request_uri;
}
```

### 設定の反映

```bash
sudo nginx -t
sudo systemctl restart nginx
```


---

# SSL証明書の設定

## 証明書のインストール

```bash
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
```

## 証明書の取得

```bash
sudo certbot --nginx -d django.voice-picker-ai.com
sudo certbot --nginx -d voice-picker-ai.com
```

## 証明書の更新

```bash
sudo certbot renew --dry-run
```

## 証明書の削除

```bash
sudo certbot delete --cert-name django.voice-picker-ai.com
sudo certbot delete --cert-name voice-picker-ai.com
```
