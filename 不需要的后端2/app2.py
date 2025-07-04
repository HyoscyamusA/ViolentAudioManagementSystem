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

    # 创建用户表
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL
                    )''')

    # 创建设备 MAC 表
    cursor.execute('''CREATE TABLE IF NOT EXISTS mac (
                        mac_address TEXT PRIMARY KEY
                    )''')

    # 创建用户绑定设备表
    cursor.execute('''CREATE TABLE IF NOT EXISTS mac_user (
                        mac_address TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        FOREIGN KEY (mac_address) REFERENCES mac(mac_address),
                        FOREIGN KEY (user_id) REFERENCES user(id)
                    )''')

    # 创建事件表
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        mac_address TEXT NOT NULL,
                        event_datetime TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        FOREIGN KEY (mac_address) REFERENCES mac(mac_address),
                        FOREIGN KEY (user_id) REFERENCES user(id)
                    )''')

    # 插入默认管理员账户
    try:
        import hashlib
        password_hash = hashlib.sha256('root'.encode()).hexdigest()
        cursor.execute('''INSERT INTO user (username, password_hash, role) 
                          VALUES (?, ?, ?)''', ('admin', password_hash, 'admin'))
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()

def insert_event(device_id, event_datetime, device_name):
    """插入事件记录"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute('''INSERT INTO events (device_id, event_datetime, device_name) 
                          VALUES (?, ?, ?)''', (device_id, event_datetime, device_name))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Error: Event with device_id {device_id} and event_datetime {event_datetime} already exists.")
    finally:
        conn.close()

import hashlib
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
from inference_demo import IsViolent
import pandas as pd

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)  # 设置会话密钥

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE = 'events.db'

# 初始化数据库
init_db()

# 注册接口
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'message': '用户名和密码不能为空'}), 400

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO user (username, password_hash, role) 
                          VALUES (?, ?, ?)''', (username, password_hash, role))
        conn.commit()
        conn.close()
        return jsonify({'message': '注册成功'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'message': '用户名已存在'}), 400

# 登录接口
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': '用户名和密码不能为空'}), 400

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''SELECT id, role FROM user WHERE username = ? AND password_hash = ?''', (username, password_hash))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user_id'] = user[0]
        session['role'] = user[1]
        return jsonify({'message': '登录成功', 'role': user[1]}), 200
    else:
        return jsonify({'message': '用户名或密码错误'}), 401

# 登出接口
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return jsonify({'message': '登出成功'}), 200

# 检查用户是否登录的装饰器
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 修改原有的接口，添加登录验证
@app.route('/upload', methods=['POST'])
@login_required
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
        upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        device_id = request.form.get('device_id', 'unknown')
        device_name = request.form.get('device_name', 'unknown')
        event_datetime = upload_time  # 精确到秒
        
        if violent_probability > 0.5:
            insert_event(device_id, event_datetime, device_name)

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


@app.route('/api/devices', methods=['GET'])
@login_required
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


@app.route('/api/audio_files', methods=['GET'])
@login_required
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
@login_required
def get_audio_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/line_chart_data', methods=['GET'])
@login_required
def get_line_chart_data():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT device_id, SUBSTR(event_datetime, 1, 10) AS event_date, COUNT(*) 
                          FROM events GROUP BY device_id, event_date ORDER BY event_date''')
        data = cursor.fetchall()
        conn.close()
        
        formatted_data = {}
        for device_id, date, count in data:
            if date not in formatted_data:
                formatted_data[date] = {}
            formatted_data[date][device_id] = {'event_count': count}

        return jsonify(formatted_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

@app.route('/api/heatmap_data', methods=['GET'])
@login_required
def get_heatmap_data():
    try:
        device_id = request.args.get('device_id', 'unknown')
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT strftime('%m', event_datetime) AS month, 
                                 strftime('%d', event_datetime) AS day, 
                                 COUNT(*) AS event_count
                          FROM events WHERE device_id = ? 
                          GROUP BY month, day''', (device_id,))
        data = cursor.fetchall()
        conn.close()

        heatmap_data = [{'month': row[0], 'day': int(row[1]), 'event_count': row[2]} for row in data]
        return jsonify(heatmap_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True)



