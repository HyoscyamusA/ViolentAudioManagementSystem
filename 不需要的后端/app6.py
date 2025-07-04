from flask import Flask, request, jsonify
from flask_cors import CORS
import os  # 确保导入 os 模块
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
    cursor.execute("INSERT INTO events (event_date, violent_probability, non_violent_probability, device_id) VALUES (?, ?, ?, ?)",
                   (event_date, violent_probability, non_violent_probability, device_id))
    conn.commit()
    conn.close()

def get_heatmap_data():
    """获取按日期分组的暴力事件数据，用于热力图"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''SELECT strftime('%Y-%m-%d', event_date) AS date,
                             AVG(violent_probability) AS avg_violent_prob
                      FROM events
                      GROUP BY date
                      ORDER BY date ASC''')
    records = cursor.fetchall()
    conn.close()
    return records

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

        # 假设设备ID在请求中可以获取到（比如来自前端表单或请求头）
        device_id = request.form.get('device_id', 'unknown')  # 获取 device_id，如果没有则为 "unknown"

        # 插入到数据库
        insert_event(event_date, violent_probability, non_violent_probability, device_id)

        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap():
    # 获取热力图数据
    data = get_heatmap_data()
    heatmap_data = [{"date": record[0], "violent_prob": record[1]} for record in data]
    return jsonify(heatmap_data)

if __name__ == '__main__':
    init_db()  # 初始化数据库
    app.run(debug=True)
