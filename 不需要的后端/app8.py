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

DATABASE = 'events.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # 修改表格，添加 device_id 列
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        violent_probability REAL,
                        non_violent_probability REAL,
                        device_id TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def insert_event(event_date, violent_probability, non_violent_probability, device_id):
    """将事件信息插入数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO events (event_date, violent_probability, non_violent_probability, device_id) VALUES (?, ?, ?, ?) ",
                   (event_date, violent_probability, non_violent_probability, device_id))
    conn.commit()
    print(f"成功插入数据库：{event_date}, 设备ID: {device_id}, 暴力概率: {violent_probability}, 非暴力概率: {non_violent_probability}")
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

        # 打印暴力事件概率和非暴力事件概率到控制台
        print(f"暴力概率：{violent_probability}, 非暴力概率：{non_violent_probability}")

        # 获取当前时间
        event_date = datetime.now().strftime('%Y-%m-%d')

        # 假设设备ID在请求中可以获取到（比如来自前端表单或请求头）
        device_id = request.form.get('device_id', 'unknown')  # 获取 device_id，如果没有则为 "unknown"

        # 插入到数据库
        insert_event(event_date, violent_probability, non_violent_probability, device_id)

        # 返回预测结果
        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        # 如果发生任何异常，捕获并返回错误信息
        print(f"发生错误：{str(e)}")  # 打印错误信息
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500  # 返回500表示服务器错误，并附带异常信息

@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap_data():
    try:
        # 你可以从数据库中获取数据并返回给前端
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events")  # 示例，获取所有事件
        events = cursor.fetchall()
        conn.close()

        # 返回事件数据，作为热力图的基础数据
        return jsonify(events), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500


    # 启动Flask应用
if __name__ == '__main__':
    init_db()  # 初始化数据库
    app.run(debug=True)  # 启动Flask服务器，开启调试模式
