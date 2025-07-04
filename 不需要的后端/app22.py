from flask import Flask, request, jsonify
import os
import sqlite3
from flask_cors import CORS
from datetime import datetime
import pandas as pd

app = Flask(__name__)
CORS(app)  # 启用跨域支持

DATABASE = 'events.db'

from flask import Flask, request, jsonify
import os
import sqlite3
from flask_cors import CORS
from datetime import datetime
from inference_demo import IsViolent  # 引用你的GMM模型预测函数
import pandas as pd


app = Flask(__name__)
CORS(app)  # 启用跨域支持，以允许不同域的前端请求访问

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

    # 创建事件表格，添加 event_date, device_id, device_name, event_count 列
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        event_count INTEGER NOT NULL)''')  # 设备上传事件的计数
    conn.commit()
    conn.close()

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
    # 检查请求中是否包含文件
    if 'file' not in request.files:
        return jsonify({'message': '未检测到文件'}), 400  # 如果没有文件，返回错误信息

    file = request.files['file']  # 获取上传的文件

    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({'message': '未选择任何文件'}), 400  # 如果文件名为空，返回错误信息

    # 检查文件格式是否为.wav
    if not file.filename.endswith('.wav'):
        return jsonify({'message': '仅支持WAV格式文件'}), 400  # 如果文件不是.wav格式，返回错误信息

    try:
        # 保存上传的音频文件到指定文件夹
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)  # 设置文件保存路径
        file.save(filepath)  # 保存文件

        # 使用 IsViolent 函数获取暴力事件的概率
        violent_probability, non_violent_probability = IsViolent(filepath)

        # 打印暴力事件概率和非暴力事件概率到控制台
        print(f"暴力概率：{violent_probability}, 非暴力概率：{non_violent_probability}")

        # 获取当前时间
        event_date = datetime.now().strftime('%Y-%m-%d')

        # 假设设备ID和设备名在请求中可以获取到（来自前端）
        device_id = request.form.get('device_id', 'unknown')  # 获取 device_id，如果没有则为 "unknown"
        device_name = request.form.get('device_name', 'unknown')  # 获取设备名（地区名）

        # 只在暴力概率大于0.5时才插入数据
        if violent_probability > 0.5:
            insert_event(event_date, device_id, device_name)

        # 返回预测结果
        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        # 如果发生任何异常，捕获并返回错误信息
        print(f"发生错误：{str(e)}")  # 打印错误信息
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500  # 返回500表示服务器错误，并附带异常信息 
    



    # 获取所有设备ID
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
                          ORDER BY event_date''')  # 查询 event_count, event_date 和 device_id
        data = cursor.fetchall()
        conn.close()

        print("数据库返回的数据：", data)  # 打印返回的数据以供调试

        # 格式化数据
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
        device_id = request.args.get('device_id')
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('''SELECT event_date, device_id, event_count FROM events WHERE device_id = ?''', (device_id,))
        data = cursor.fetchall()
        conn.close()

        if not data:
            return jsonify({'message': 'No data found for the selected device'}), 404

        # 转换为DataFrame并处理数据
        df = pd.DataFrame(data, columns=["event_date", "device_id", "event_count"])
        df['month'] = pd.to_datetime(df['event_date']).dt.month_name().str[:3]  # 获取月份
        df['day'] = pd.to_datetime(df['event_date']).dt.day  # 获取日期

        # 按月和日期分组并求和
        df_grouped = df.groupby(['month', 'day']).sum().reset_index()

        if df_grouped.empty:
            return jsonify({'message': 'No event data for the selected device in this period'}), 404

        heatmap_data = df_grouped.to_dict(orient='records')
        return jsonify(heatmap_data), 200

    except Exception as e:
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
