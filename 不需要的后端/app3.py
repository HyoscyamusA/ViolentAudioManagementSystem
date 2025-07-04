from flask import Flask, request, jsonify
import os
import sqlite3
from flask_cors import CORS
from inference_demo import IsViolent  # 你的GMM模型预测函数

app = Flask(__name__)
CORS(app)

# 数据库连接函数
def get_db_connection():
    conn = sqlite3.connect('events.db')
    conn.row_factory = sqlite3.Row
    return conn

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': '未检测到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': '未选择任何文件'}), 400

    if not file.filename.endswith('.wav'):
        return jsonify({'message': '仅支持WAV格式文件'}), 400

    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # 记录上传文件信息
        conn = get_db_connection()
        conn.execute('INSERT INTO uploads (filename) VALUES (?)', (file.filename,))
        conn.commit()

        # 进行预测
        violent_probability, non_violent_probability = IsViolent(filepath)
        conn.execute('''
        INSERT INTO violence_events (violent_probability, non_violent_probability)
        VALUES (?, ?)
        ''', (violent_probability, non_violent_probability))
        conn.commit()
        conn.close()

        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/get_violence_data', methods=['GET'])
def get_violence_data():
    conn = get_db_connection()
    cursor = conn.execute('SELECT event_time, violent_probability FROM violence_events')
    data = cursor.fetchall()
    conn.close()

    labels = [row['event_time'] for row in data]
    violent_probabilities = [row['violent_probability'] for row in data]

    return jsonify({'labels': labels, 'violent_probabilities': violent_probabilities})

if __name__ == '__main__':
    app.run(debug=True)
