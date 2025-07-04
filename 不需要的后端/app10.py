from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
from inference_demo import IsViolent

app = Flask(__name__)
CORS(app)

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE = 'events.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        violent_probability REAL,
                        non_violent_probability REAL)''')
    conn.commit()
    conn.close()

def insert_event(event_date, device_id, device_name, violent_probability, non_violent_probability):
    """将事件信息插入数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO events (event_date, device_id, device_name, violent_probability, non_violent_probability)
                      VALUES (?, ?, ?, ?, ?)''',
                   (event_date, device_id, device_name, violent_probability, non_violent_probability))
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

        # 假设设备ID和设备名在请求中可以获取到（来自前端）
        device_id = request.form.get('device_id', 'unknown')  # 获取 device_id，如果没有则为 "unknown"
        device_name = request.form.get('device_name', 'unknown')  # 获取 device_name，地区名

        # 插入到数据库
        insert_event(event_date, device_id, device_name, violent_probability, non_violent_probability)

        # 返回预测结果
        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        # 如果发生任何异常，捕获并返回错误信息
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500


@app.route('/api/line_chart_data', methods=['GET'])
def get_line_chart_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT event_date, device_id, COUNT(*) 
                          FROM events 
                          GROUP BY event_date, device_id 
                          ORDER BY event_date''')
        data = cursor.fetchall()
        conn.close()

        # 格式化数据
        formatted_data = {}
        for record in data:
            date, device_id, count = record
            if date not in formatted_data:
                formatted_data[date] = {}
            formatted_data[date][device_id] = count

        return jsonify(formatted_data), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500


@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT event_date, device_id, COUNT(*) 
                          FROM events 
                          GROUP BY event_date, device_id 
                          ORDER BY event_date''')
        data = cursor.fetchall()
        conn.close()

        # 格式化数据
        formatted_data = []
        for record in data:
            date, device_id, count = record
            formatted_data.append({
                'date': date,
                'device_id': device_id,
                'count': count
            })

        return jsonify(formatted_data), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
