from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from inference_demo import IsViolent  # 引用你的GMM模型预测函数
import pandas as pd

app = Flask(__name__)
CORS(app)  # 启用跨域支持

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')  # 设置上传文件夹的路径
if not os.path.exists(UPLOAD_FOLDER):  # 如果文件夹不存在，则创建该文件夹
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER  # 将上传文件夹路径存储在应用配置中

DATABASE = 'events.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 创建事件表格
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        event_count INTEGER NOT NULL)''')

    # 创建音频文件表
    cursor.execute('''CREATE TABLE IF NOT EXISTS audio_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        filepath TEXT NOT NULL,
                        upload_time DATETIME NOT NULL,
                        device_id TEXT NOT NULL,
                        violent_prob FLOAT NOT NULL,
                        non_violent_prob FLOAT NOT NULL)''')

    conn.commit()  # 提交更改
    conn.close()   # 关闭连接

def insert_event(event_date, device_id, device_name):
    """将事件信息插入数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 检查该设备是否在该日期已经存在记录
    cursor.execute('''SELECT event_count FROM events WHERE event_date = ? AND device_id = ?''', (event_date, device_id))
    existing_record = cursor.fetchone()

    if existing_record:
        # 如果存在记录，增加事件计数
        cursor.execute('''UPDATE events SET event_count = event_count + 1 WHERE event_date = ? AND device_id = ?''', (event_date, device_id))
    else:
        # 如果没有记录，插入新的记录
        cursor.execute('''INSERT INTO events (event_date, device_id, device_name, event_count) VALUES (?, ?, ?, ?)''',
                       (event_date, device_id, device_name, 1))  # 初始计数为1
    conn.commit()
    conn.close()
    print(f"成功插入/更新数据库：{event_date}, 设备ID: {device_id}, 设备名称: {device_name}")

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
        # 保存文件
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 使用 IsViolent 函数获取暴力事件的概率
        violent_probability, non_violent_probability = IsViolent(filepath)
        print(f"暴力概率：{violent_probability}, 非暴力概率：{non_violent_probability}")

        # 获取当前时间
        event_date = datetime.now().strftime('%Y-%m-%d')

        # 假设设备ID和设备名在请求中可以获取到（来自前端）
        device_id = request.form.get('device_id', 'unknown')
        device_name = request.form.get('device_name', 'unknown')

        # 只在暴力概率大于0.5时才插入数据
        if violent_probability > 0.5:
            insert_event(event_date, device_id, device_name)

        # 插入音频文件记录
        upload_time = datetime.now()
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO audio_files 
                       (filename, filepath, upload_time, device_id, violent_prob, non_violent_prob)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                     (filename, filepath, upload_time, device_id, violent_probability, non_violent_probability))
        conn.commit()
        conn.close()

        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/audio_files', methods=['GET'])
def get_audio_files():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT filename, upload_time, device_id, 
                   violent_prob, non_violent_prob 
            FROM audio_files 
            ORDER BY upload_time DESC
        ''')
        data = cursor.fetchall()
        conn.close()

        # 将查询结果转换为字典列表
        audio_files = []
        for row in data:
            audio_files.append({
                'filename': row[0],
                'upload_time': row[1],
                'device_id': row[2],
                'violent_prob': row[3],
                'non_violent_prob': row[4]
            })

        return jsonify(audio_files), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/uploads/<filename>')
def get_audio_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



@app.route('/api/devices', methods=['GET'])
def get_devices():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT device_id FROM events')
        devices = cursor.fetchall()
        conn.close()

        # 返回设备ID列表
        return jsonify([{'device_id': device[0]} for device in devices]), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/line_chart_data', methods=['GET'])
def get_line_chart_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT event_date, device_id, event_count 
                          FROM events 
                          ORDER BY event_date''')
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

