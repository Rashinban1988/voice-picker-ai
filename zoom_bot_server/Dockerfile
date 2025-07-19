FROM --platform=linux/amd64 node:18

WORKDIR /app

# C++ビルド環境とライブラリをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libjsoncpp-dev \
    libasound2-dev \
    libpulse-dev \
    libssl-dev \
    pulseaudio \
    pulseaudio-utils \
    libxcb-shape0 \
    libxcb-image0 \
    libxcb-xfixes0 \
    libxcb-shm0 \
    libxcb-randr0 \
    libxcb-keysyms1 \
    libxcb-util1 \
    libxcb-xtest0 \
    libx11-xcb1 \
    libfontconfig1 \
    libfreetype6 \
    libgl1-mesa-glx \
    libegl1-mesa \
    && rm -rf /var/lib/apt/lists/*

# パッケージファイルをコピーして依存関係をインストール
COPY package*.json ./
RUN npm ci --only=production

# アプリケーションファイルをコピー
COPY . .

# ハイブリッドC++ボットのビルド（SDK統合準備完了）
WORKDIR /app/zoom_meeting_sdk/bot_implementation
RUN cp CMakeLists_hybrid.txt CMakeLists.txt && \
    mkdir -p build && cd build && \
    cmake .. && \
    make && \
    ls -la zoom_meeting_bot

# 作業ディレクトリを戻す
WORKDIR /app

# 録画ディレクトリを作成
RUN mkdir -p /app/media/zoom_recordings

# 必要なライブラリパスを設定
ENV LD_LIBRARY_PATH=/app/zoom_meeting_sdk:/app/zoom_meeting_sdk/qt_libs/Qt/lib:$LD_LIBRARY_PATH

# ポート4000を公開
EXPOSE 4000

# サーバーを起動
CMD ["node", "server.js"]