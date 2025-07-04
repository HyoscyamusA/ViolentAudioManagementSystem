# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import sqlite3
import torch
import torchaudio
import torchaudio.compliance.kaldi as kaldi

app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = 'uploads'
DATABASE = 'violence.db'
MODEL_PATH = 'asrModel/final.pt'
CONFIG_PATH = 'asrModel/train.yaml'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 初始化数据库
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS detections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  timestamp DATETIME,
                  is_violent BOOLEAN)''')
    conn.commit()
    conn.close()


# 加载ASR模型
def load_model():
    # 此处需要根据实际模型结构进行初始化
    model = torch.jit.load(MODEL_PATH)
    model.eval()
    return model


# 特征提取
def extract_features(audio_path):
    waveform, sample_rate = torchaudio.load(audio_path)
    if sample_rate != 16000:
        waveform = torchaudio.transforms.Resample(
            orig_freq=sample_rate, new_freq=16000)(waveform)
    features = kaldi.fbank(waveform,
                           num_mel_bins=80,
                           frame_length=25,
                           frame_shift=10,
                           energy_floor=0.0)
    return features.unsqueeze(0)


# 暴力检测逻辑
def detect_violence(audio_path):
    try:
        # 此处应替换为实际检测逻辑
        features = extract_features(audio_path)
        # 使用模型进行预测
        # model = load_model()
        # prediction = model(features)
        # 示例随机结果
        return torch.rand(1).item() > 0.5
    except Exception as e:
        print(f"检测错误: {str(e)}")
        return False


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '无效文件'}), 400

    try:
        # 保存文件
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        # 检测暴力内容
        is_violent = detect_violence(filepath)

        # 记录到数据库
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT INTO detections (filename, timestamp, is_violent) VALUES (?, ?, ?)',
                  (file.filename, datetime.now(), int(is_violent)))
        conn.commit()
        conn.close()

        return jsonify({
            'filename': file.filename,
            'is_violent': is_violent,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stats/monthly', methods=['GET'])
def monthly_stats():
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''SELECT strftime('%Y-%m', timestamp) as month, 
                    COUNT(*) FROM detections 
                    WHERE is_violent = 1 
                    GROUP BY month''')
        data = [{'month': row[0], 'count': row[1]} for row in c.fetchall()]
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    init_db()
    app.run(port=5000, debug=True)