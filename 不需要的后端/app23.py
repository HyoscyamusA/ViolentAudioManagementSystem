from flask import Flask, request, jsonify
import os
import sqlite3
import pandas as pd
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 启用跨域支持

DATABASE = 'events.db'

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        event_count INTEGER NOT NULL)''')
    conn.commit()
    conn.close()

# 插入事件数据
def insert_event(event_date, device_id, device_name):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''SELECT event_count FROM events WHERE event_date = ? AND device_id = ?''', (event_date, device_id))
    existing_record = cursor.fetchone()
    if existing_record:
        cursor.execute('''UPDATE events SET event_count = event_count + 1 WHERE event_date = ? AND device_id = ?''', (event_date, device_id))
    else:
        cursor.execute('''INSERT INTO events (event_date, device_id, device_name, event_count) VALUES (?, ?, ?, ?)''',
                       (event_date, device_id, device_name, 1))
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
        filepath = os.path.join('uploads', file.filename)
        file.save(filepath)
        event_date = datetime.now().strftime('%Y-%m-%d')
        device_id = request.form.get('device_id', 'unknown')
        device_name = request.form.get('device_name', 'unknown')
        insert_event(event_date, device_id, device_name)
        return jsonify({'message': '上传成功'}), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap_data():
    try:
        device_id = request.args.get('device_id', 'unknown')
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT event_date, device_id, event_count FROM events WHERE device_id = ?''', (device_id,))
        data = cursor.fetchall()
        conn.close()

        if not data:
            return jsonify({'message': '没有找到相关设备的数据'}), 404

        df = pd.DataFrame(data, columns=["event_date", "device_id", "event_count"])
        df['month'] = pd.to_datetime(df['event_date']).dt.month_name().str[:3]
        df['day'] = pd.to_datetime(df['event_date']).dt.day
        df_grouped = df.groupby(['month', 'day']).sum().reset_index()

        heatmap_data = df_grouped.to_dict(orient='records')
        return jsonify(heatmap_data), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/line_chart_data', methods=['GET'])
def get_line_chart_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT event_date, device_id, event_count FROM events ORDER BY event_date''')
        data = cursor.fetchall()
        conn.close()

        formatted_data = {}
        for record in data:
            date, device_id, count = record
            if date not in formatted_data:
                formatted_data[date] = {}
            formatted_data[date][device_id] = {'event_count': count}

        return jsonify(formatted_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
