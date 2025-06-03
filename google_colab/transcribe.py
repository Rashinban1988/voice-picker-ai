# whisper公式をインストール
!pip install git+https://github.com/openai/whisper.git

# 必要なライブラリもインストール
!pip install pyannote.audio torch torchaudio pydub noisereduce pyngrok

---

# インポートとモデルロード
import torch
import os
import re
import numpy as np
import noisereduce as nr
from google.colab import userdata
from pydub import AudioSegment
from pyannote.audio import Pipeline, Audio
from pyannote.audio.pipelines.utils.hook import ProgressHook
import torchaudio
import whisper
from moviepy.editor import VideoFileClip

# Whisper
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = whisper.load_model("large-v3").to(device) # tiny,base,small,medium,large-v1,large-v2,large-v3

# Hugging Face dialization
HF_TOKEN = userdata.get('hf_token')
os.environ["HUGGINGFACE_TOKEN"] = HF_TOKEN

# pyannote
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=os.environ["HUGGINGFACE_TOKEN"]
).to(device)

---

def process_audio(file_path, file_extension):
    if file_extension == ".wav":
        return file_path, file_extension

    try:
        # 一時ファイルのパスを生成
        temp_wav = file_path.rsplit(".", 1)[0] + "_temp.wav"
        final_wav = file_path.rsplit(".", 1)[0] + ".wav"

        # MP4ファイルの場合、まず音声を抽出
        if file_extension.lower() in ['.mp4', '.avi', '.mov', '.wmv']:
            video = VideoFileClip(file_path)
            if video.audio is None:
                raise ValueError("動画ファイルに音声が含まれていません")
            # 一時的なWAVファイルを作成
            video.audio.write_audiofile(temp_wav, fps=16000)
            video.close()
            file_path = temp_wav
            file_extension = ".wav"

        # 音声データの読み込み
        audio = AudioSegment.from_file(file_path, format=file_extension.replace(".", ""), frame_rate=16000, sample_width=2, channels=1)

        # 音声データの検証
        if len(audio) == 0:
            raise ValueError("音声データが空です")

        # 音声の正規化
        audio = audio.normalize()

        # ノイズ除去
        samples = np.array(audio.get_array_of_samples())
        reduced_noise = nr.reduce_noise(
            y=samples,
            sr=audio.frame_rate,
            prop_decrease=0.5,
            time_constant_s=4,
            freq_mask_smooth_hz=500,
            time_mask_smooth_ms=50,
            thresh_n_mult_nonstationary=1.5,
            sigmoid_slope_nonstationary=15,
            n_std_thresh_stationary=1.5,
            clip_noise_stationary=True,
            use_tqdm=False,
            n_jobs=1,
            use_torch=True,
            device="cuda"
        )

        # 音声データの再構築
        audio = AudioSegment(
            reduced_noise.tobytes(),
            frame_rate=audio.frame_rate,
            sample_width=audio.sample_width,
            channels=audio.channels
        )

        # 最終的なWAVファイルの保存
        audio.export(final_wav, format="wav")

        # 一時ファイルの削除
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

        return final_wav, ".wav"

    except Exception as e:
        # エラー発生時も一時ファイルを削除
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except:
                pass
        print(f"音声処理中にエラーが発生しました: {str(e)}")
        raise

---

# --- 文字起こし ---
def transcribe_audio(file_path):
    print('文字起こしを始めます')
    result = model.transcribe(file_path, language="ja")
    return result

---

# --- 話者分離 ---
def perform_diarization(file_path):
    waveform, sample_rate = torchaudio.load(file_path)
    with ProgressHook() as hook:
        diarization = pipeline({"waveform": waveform, "sample_rate": sample_rate}, hook=hook)
    return diarization

---

def diarization_and_transcription(file_path):
    try:
        # 1. ファイル拡張子判定とwav変換
        ext = os.path.splitext(file_path)[1]
        original_file_path = file_path
        if ext != ".wav":
            file_path, ext = process_audio(file_path, ext)
        print('ファイル変換完了')

        # 音声ファイルの存在確認
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"変換後の音声ファイルが見つかりません: {file_path}")

        # 音声データの検証
        audio = AudioSegment.from_file(file_path)
        if len(audio) == 0:
            raise ValueError("音声データが空です")

        # 2. 話者分離
        diarization = perform_diarization(file_path)
        print('話者分離完了')

        # 3. 文字起こし
        whisper_result = transcribe_audio(file_path)
        print('文字起こし完了')

        # 4. 各セグメントに話者ラベルをマッピング
        results = []
        segment_limit_time = 30  # 30秒の制限
        temp_threshold_time = segment_limit_time
        temp_segment_text = ""
        temp_segment_start_time = 0
        temp_segment_speaker = None

        for result in whisper_result['segments']:
            result_start = result['start']
            result_end = result['end']
            result_text = result['text']
            current_speaker = None

            # 話者セグメントのどこに該当するか探す
            for segment, _, speaker in diarization.itertracks(yield_label=True):
                segment_start_time = segment.start
                segment_end_time = segment.end
                if result_start <= segment_start_time <= result_end or result_start <= segment_end_time <= result_end:
                    current_speaker = speaker
                    break

            # 話者が変わるか、30秒を超える場合に結果を保存
            if current_speaker == temp_segment_speaker:
                if result_end < temp_threshold_time:
                    temp_segment_text += result_text
                else:
                    # 30秒を超えた場合、現在のセグメントを保存
                    results.append({
                        "start": temp_segment_start_time,
                        "end": result_end,
                        "speaker": temp_segment_speaker,
                        "text": temp_segment_text
                    })
                    # 新しいセグメントの開始
                    temp_segment_text = result_text
                    temp_threshold_time = result_start + segment_limit_time
                    temp_segment_start_time = result_start
                    temp_segment_speaker = current_speaker
            else:
                # 話者が変わった場合
                if temp_segment_text:  # 前のセグメントが存在する場合
                    results.append({
                        "start": temp_segment_start_time,
                        "end": result_end,
                        "speaker": temp_segment_speaker,
                        "text": temp_segment_text
                    })
                # 新しいセグメントの開始
                temp_segment_text = result_text
                temp_threshold_time = result_start + segment_limit_time
                temp_segment_start_time = result_start
                temp_segment_speaker = current_speaker

            print(f"[{result_start}s - {result_end}s] {current_speaker}: {result_text}")

        # 最後のセグメントが残っている場合は保存
        if temp_segment_text:
            results.append({
                "start": temp_segment_start_time,
                "end": result_end,
                "speaker": temp_segment_speaker,
                "text": temp_segment_text
            })

        print('マッピング完了')
        return results

    except Exception as e:
        print(f"処理中にエラーが発生しました: {str(e)}")
        raise
    finally:
        # 一時ファイルの削除
        if ext != ".wav" and os.path.exists(file_path) and file_path != original_file_path:
            try:
                os.remove(file_path)
            except:
                pass

---

# Flaskサーバの実装
from flask import Flask, request, jsonify
from google.colab import userdata
import threading
import json
import requests

app = Flask(__name__)

def process_and_notify(file_path, uploaded_file_id, django_api_url):
    try:
        # ここで文字起こし・話者分離
        transcriptions = diarization_and_transcription(file_path)
        # Django APIにPOST
        result = {}
        result['uploaded_file_id'] = uploaded_file_id
        result['transcriptions'] = transcriptions
        requests.post(django_api_url, json=result)

        # import os
        # os._exit(0)  # ランタイムを強制終了
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        # import os
        # os._exit(1)  # エラーコード1で終了

@app.route('/process', methods=['POST'])
def handle_audio():
    print('リクエスト受信')
    if 'file' not in request.files:
        return "ファイルがありません", 400

    file = request.files['file']
    file_path = f"/tmp/{file.filename}"
    file.save(file_path)

    # リクエストデータの取得方法を修正
    try:
        # リクエストデータをJSONとして解析
        data = json.loads(request.data)
        uploaded_file_id = data.get('uploaded_file_id')
    except (json.JSONDecodeError, AttributeError):
        # フォームデータから取得を試みる
        uploaded_file_id = request.form.get('uploaded_file_id')

    if not uploaded_file_id:
        return "uploaded_file_idが指定されていません", 400

    # 非同期で処理開始
    save_transcribes_endpoint = userdata.get('save_transcribe_endpoint')
    threading.Thread(target=process_and_notify, args=(file_path, uploaded_file_id, save_transcribes_endpoint)).start()
    return jsonify({"status": "受付完了"}), 202

---

# ngrokによる外部公開
!pip install pyngrok
# 既存のngrokセッションを終了
!pkill ngrok

# google.colab.userdataをインポート
from google.colab import userdata

YOUR_NGROK_TOKEN = userdata.get('ngrok_token')
# Use an f-string to pass the Python variable's value to the shell command
!ngrok config add-authtoken {YOUR_NGROK_TOKEN}

from pyngrok import ngrok
import requests
import json

# NgrokTunnelオブジェクトからURLを取得
tunnel = ngrok.connect(5000)
public_url = tunnel.public_url
print(public_url)

# リクエストボディ
data = {
    'code': 'ngrok',
    'value': public_url  # 文字列としてのURLを使用
}

api_url = userdata.get('api_url') + 'api/environments/ngrok/'
print(api_url)
content_type = 'application/json'
headers = {'Content-Type': content_type}
response = requests.post(api_url, headers=headers, data=json.dumps(data))

# レスポンスを確認
if response.status_code == 200 or response.status_code == 201:
    print("ngrokエンドポイントが正常に保存されました")
    print(f"保存されたエンドポイント: {public_url}")
else:
    print(f"エラーが発生しました: {response.status_code}")
    print(response.text)
print(public_url)

---

# サーバ起動
app.run(port=5000)