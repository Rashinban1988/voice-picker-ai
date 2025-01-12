# ベースイメージとしてPythonの公式イメージを使用
FROM python:3.10

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    curl \
    libssl-dev \
    libffi-dev \
    build-essential \
    && curl -sL https://deb.nodesource.com/setup_14.x | bash - \
    && apt-get install -y nodejs \
    && apt-get install -y npm \
    && apt-get clean

# 環境変数を設定
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 作業ディレクトリを設定
WORKDIR /code

# 依存関係のインストール
COPY requirements.txt /code/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# プロジェクトのファイルをコンテナにコピー
COPY . /code/

# アプリケーションを起動するコマンド
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]