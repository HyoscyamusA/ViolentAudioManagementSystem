from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
from inference_demo import IsViolent  # 引用你的GMM模型预测函数

app = Flask(__name__)
CORS(app)

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# SQLite数据库配置
DATABASE = 'events.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        violent_probability REAL,
                        non_violent_probability REAL)''')
    conn.commit()
    conn.close()

def insert_event(event_date, violent_probability, non_violent_probability):
    """将事件信息插入数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO events (event_date, violent_probability, non_violent_probability) VALUES (?, ?, ?)",
                   (event_date, violent_probability, non_violent_probability))
    conn.commit()
    conn.close()

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

        # 使用 IsViolent 函数获取暴力事件的概率
        violent_probability, non_violent_probability = IsViolent(filepath)

        # 获取当前时间
        event_date = datetime.now().strftime('%Y-%m-%d')

        # 插入到数据库
        insert_event(event_date, violent_probability, non_violent_probability)

        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

if __name__ == '__main__':
    init_db()  # 初始化数据库
    app.run(debug=True)
