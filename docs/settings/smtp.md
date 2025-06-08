# PostfixとDovecotでTLS（Let’s Encrypt証明書利用）を有効化

## Postfixのインストール

```bash
sudo apt-get install -y postfix
```

## letsencryptの設定

```bash
sudo certbot --nginx -d mail.voice-picker-ai.com
```

## 設定ファイルの編集

```bash
sudo vim /etc/postfix/main.cf
```

### 編集内容

```bash
smtpd_banner = $myhostname ESMTP $mail_name (Ubuntu)
biff = no

append_dot_mydomain = no
readme_directory = no
compatibility_level = 3.6

# Devecot
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes
smtpd_sasl_security_options = noanonymous
smtpd_sasl_local_domain = $myhostname
broken_sasl_auth_clients = yes

# opendkim
milter_default_action = accept
milter_protocol = 2
smtpd_milters = inet:localhost:12301
non_smtpd_milters = inet:localhost:12301

# TLS設定（Let's Encryptで取得したSSL証明書を使用）
smtpd_tls_cert_file = /etc/letsencrypt/live/mail.voice-picker-ai.com/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/mail.voice-picker-ai.com/privkey.pem
smtpd_use_tls = yes

# 必要に応じて encrypt に設定可能
smtpd_tls_security_level=may

# SMTPクライアント側のTLS設定
smtp_tls_CApath=/etc/ssl/certs
smtp_tls_security_level=may
smtp_tls_session_cache_database = btree:${data_directory}/smtp_scache

# リレー制限設定
smtpd_relay_restrictions = permit_mynetworks permit_sasl_authenticated defer_unauth_destination


# ドメインとホスト名の設定

# メールサーバーのホスト名を設定
myhostname = mail.voice-picker-ai.com

# 独自ドメイン名
mydomain = voice-picker-ai.com

# メール送信元のドメイン名
myorigin = $mydomain

# 受信対象のドメインとホスト名
mydestination = $myhostname, localhost.$mydomain, localhost, $mydomain

# 直接送信なので空のまま
relayhost =


# ネットワークの許可設定

# ローカルネットワークのみ許可
mynetworks = 127.0.0.0/8

# メールをMaildir形式で保存
home_mailbox = Maildir/

# メールボックスのサイズ制限なし
mailbox_size_limit = 0

# 受信者区切り文字
recipient_delimiter = +

# すべてのネットワークインターフェースでリッスン
inet_interfaces = all

# IPv4およびIPv6をサポート
inet_protocols = all

# 仮想エイリアスマップを有効にする
virtual_alias_maps = hash:/etc/postfix/virtual
```
