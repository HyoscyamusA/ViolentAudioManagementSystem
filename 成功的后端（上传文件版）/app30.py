from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from inference_demo import IsViolent
import pandas as pd

app = Flask(__name__)
CORS(app)

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
                        timestamp DATETIME NOT NULL,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS audio_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        filepath TEXT NOT NULL,
                        upload_time DATETIME NOT NULL,
                        device_id TEXT NOT NULL,
                        violent_prob FLOAT NOT NULL,
                        non_violent_prob FLOAT NOT NULL)''')

    conn.commit()
    conn.close()

def insert_event(device_id, device_name):
    """插入事件记录"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    timestamp = datetime.now()
    cursor.execute('''INSERT INTO events (timestamp, device_id, device_name) 
                      VALUES (?, ?, ?)''', (timestamp, device_id, device_name))
    conn.commit()
    conn.close()
    print(f"事件记录插入成功: 设备 {device_id}, 时间 {timestamp}")

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': '未检测到文件'}), 400
    
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.wav'):
        return jsonify({'message': '仅支持WAV格式文件'}), 400
    
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        violent_probability, non_violent_probability = IsViolent(filepath)
        print(f"暴力概率: {violent_probability}, 非暴力概率: {non_violent_probability}")

        filename = secure_filename(file.filename)
        upload_time = datetime.now()
        device_id = request.form.get('device_id', 'unknown')
        device_name = request.form.get('device_name', 'unknown')
        
        if violent_probability > 0.5:
            insert_event(device_id, device_name)

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO audio_files 
                          (filename, filepath, upload_time, device_id, violent_prob, non_violent_prob)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (filename, filepath, upload_time, device_id, violent_probability, non_violent_probability))
        conn.commit()
        conn.close()
        
        return jsonify({'violent_probability': violent_probability, 'non_violent_probability': non_violent_probability}), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误: {str(e)}'}), 500

@app.route('/api/line_chart_data', methods=['GET'])
def get_line_chart_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT DATE(timestamp) as event_date, device_id, COUNT(*) 
                          FROM events GROUP BY event_date, device_id ORDER BY event_date''')
        data = cursor.fetchall()
        conn.close()
        
        formatted_data = {}
        for date, device_id, count in data:
            if date not in formatted_data:
                formatted_data[date] = {}
            formatted_data[date][device_id] = {'event_count': count}

        return jsonify(formatted_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap_data():
    try:
        device_id = request.args.get('device_id', 'unknown')
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT timestamp, device_id FROM events WHERE device_id = ?''', (device_id,))
        data = cursor.fetchall()
        conn.close()

        if not data:
            return jsonify({'message': '没有找到相关设备的数据'}), 404

        df = pd.DataFrame(data, columns=["timestamp", "device_id"])
        df['month'] = pd.to_datetime(df['timestamp']).dt.strftime('%b')
        df['day'] = pd.to_datetime(df['timestamp']).dt.day
        df_grouped = df.groupby(['month', 'day']).size().reset_index(name='event_count')

        return jsonify(df_grouped.to_dict(orient='records')), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
