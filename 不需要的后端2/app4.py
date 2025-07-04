from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from inference_demo import IsViolent
import pandas as pd

# 初始化Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    pass


@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, role FROM user WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if not user_data:
        return None
    user = User()
    user.id = user_data[0]
    user.role = user_data[1]
    return user


# 更新后的数据库初始化
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user')''')

    # MAC地址表
    cursor.execute('''CREATE TABLE IF NOT EXISTS mac (
                        mac_address TEXT PRIMARY KEY)''')

    # 用户设备关联表
    cursor.execute('''CREATE TABLE IF NOT EXISTS mac_user (
                        mac_address TEXT REFERENCES mac(mac_address),
                        device_name TEXT,
                        user_id INTEGER REFERENCES user(id),
                        PRIMARY KEY (mac_address, user_id))''')

    # 事件表
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        mac_address TEXT REFERENCES mac(mac_address),
                        event_datetime TEXT,
                        user_id INTEGER REFERENCES user(id),
                        PRIMARY KEY (mac_address, event_datetime))''')

    # 音频文件表
    cursor.execute('''CREATE TABLE IF NOT EXISTS audio_files (
                        filename TEXT PRIMARY KEY,
                        upload_time TEXT NOT NULL,
                        user_id INTEGER REFERENCES user(id),
                        mac_address TEXT REFERENCES mac(mac_address),
                        violent_prob FLOAT NOT NULL,
                        non_violent_prob FLOAT NOT NULL)''')

    # 创建默认管理员（admin/root）
    try:
        cursor.executemany('INSERT OR IGNORE INTO user (username, password, role) VALUES (?, ?, ?)',
                           [('admin', 'root', 'admin'),
                            ('root', 'toor', 'admin')])
    except Exception as e:
        print(f"创建管理员账户时出错: {str(e)}")

    conn.commit()
    conn.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, password, role FROM user WHERE username = ?', (data['username'],))
    user = cursor.fetchone()
    conn.close()

    if user and data['password'] == user[1]:
        user_obj = User()
        user_obj.id = user[0]
        user_obj.role = user[2]
        login_user(user_obj)
        return jsonify({'success': True}), 200
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO user (username, password) VALUES (?, ?)',
                       (data['username'], data['password']))
        conn.commit()
        return jsonify({'success': True}), 201
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    finally:
        conn.close()


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': '未检测到文件'}), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.wav'):
        return jsonify({'message': '仅支持WAV格式文件'}), 400

    conn = None
    try:
        # 保存文件
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # 预测概率
        violent_probability, non_violent_probability = IsViolent(filepath)
        print(f"暴力概率: {violent_probability}, 非暴力概率: {non_violent_probability}")

        # 获取参数
        filename = secure_filename(file.filename)
        upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mac_address = request.form.get('mac_address')  # 改为mac_address

        # 验证设备权限
        if mac_address:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM mac_user WHERE mac_address = ? AND user_id = ?',
                           (mac_address, current_user.id))
            if not cursor.fetchone():
                return jsonify({'message': '无权使用该设备'}), 403

        # 记录事件（当暴力概率>0.5时）
        if violent_probability > 0.5 and mac_address:
            # 使用新的insert_event函数
            conn = conn or sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (mac_address, event_datetime, user_id)
                VALUES (?, ?, ?)
            ''', (mac_address, upload_time, current_user.id))
            conn.commit()

        # 保存到audio_files表
        conn = conn or sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audio_files 
            (filename, upload_time, user_id, mac_address, violent_prob, non_violent_prob)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (filename, upload_time, current_user.id, mac_address, violent_probability, non_violent_probability))
        conn.commit()

        return jsonify({
            'violent_probability': violent_probability,
            'non_violent_probability': non_violent_probability
        }), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误: {str(e)}'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/audio_files', methods=['GET'])
@login_required
def get_audio_files():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 管理员获取全部记录
        if current_user.role == 'admin':
            cursor.execute('''SELECT 
                                filename, 
                                upload_time, 
                                mac_address, 
                                violent_prob, 
                                non_violent_prob 
                            FROM audio_files''')

        # 普通用户获取自己的记录
        else:
            cursor.execute('''SELECT 
                                filename, 
                                upload_time, 
                                mac_address, 
                                violent_prob, 
                                non_violent_prob 
                            FROM audio_files
                            WHERE user_id = ? 
                            OR mac_address IN (
                                SELECT mac_address 
                                FROM mac_user 
                                WHERE user_id = ?
                            )''', (current_user.id, current_user.id))

        data = cursor.fetchall()
        audio_files = []

        for row in data:
            # 获取设备自定义名称（如果有）
            cursor.execute('''SELECT device_name 
                            FROM mac_user 
                            WHERE mac_address = ? AND user_id = ?''',
                           (row[2], current_user.id))
            device_name = cursor.fetchone()

            audio_files.append({
                'filename': row[0],
                'upload_time': row[1],
                'mac_address': row[2],
                'device_name': device_name[0] if device_name else "未命名设备",
                'violent_prob': row[3],
                'non_violent_prob': row[4]
            })

        return jsonify(audio_files), 200

    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

    finally:
        if conn:
            conn.close()


# 下方没修改
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

        return jsonify(
            {'violent_probability': violent_probability, 'non_violent_probability': non_violent_probability}), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误: {str(e)}'}), 500


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


@app.route('/api/line_chart_data', methods=['GET'])
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
    init_db()
    app.run(debug=True)
