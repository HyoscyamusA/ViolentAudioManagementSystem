import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# 初始化数据库
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # 创建用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    # 创建设备 MAC 地址表
    c.execute('''
        CREATE TABLE IF NOT EXISTS mac (
            mac_address TEXT PRIMARY KEY
        )
    ''')
    # 创建用户绑定设备表
    c.execute('''
        CREATE TABLE IF NOT EXISTS mac_user (
            mac_address TEXT,
            device_name TEXT,
            user_id INTEGER,
            FOREIGN KEY (mac_address) REFERENCES mac(mac_address),
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
    ''')
    # 创建事件表
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            mac_address TEXT,
            event_datetime TEXT,
            user_id INTEGER,
            FOREIGN KEY (mac_address) REFERENCES mac(mac_address),
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
    ''')
    # 插入默认管理员账户
    c.execute("INSERT OR IGNORE INTO user (username, password, role) VALUES ('admin', 'root', 'admin')")
    conn.commit()
    conn.close()

# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT id, role FROM user WHERE username =? AND password =?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['role'] = user[1]
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO user (username, password, role) VALUES (?,?, 'user')", (username, password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='用户名已存在')
        finally:
            conn.close()
    return render_template('register.html')

# 注销功能
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('login'))

# 检查用户是否登录
def is_logged_in():
    return 'user_id' in session

# 主页
@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return render_template('index.html')

# 图表页面
@app.route('/charts')
def charts():
    if not is_logged_in():
        return redirect(url_for('login'))
    role = session['role']
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role == 'admin':
        c.execute("SELECT mac_address FROM mac")
    else:
        c.execute("SELECT mac_address FROM mac_user WHERE user_id =?", (user_id,))
    devices = c.fetchall()
    conn.close()
    return render_template('charts.html', devices=devices)

# 获取设备列表 API
@app.route('/api/devices')
def get_devices():
    if not is_logged_in():
        return [], 401
    role = session['role']
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role == 'admin':
        c.execute("SELECT mac_address FROM mac")
    else:
        c.execute("SELECT mac_address FROM mac_user WHERE user_id =?", (user_id,))
    devices = [{'device_id': device[0]} for device in c.fetchall()]
    conn.close()
    return devices

# 获取热力图数据 API
@app.route('/api/heatmap_data')
def get_heatmap_data():
    if not is_logged_in():
        return [], 401
    role = session['role']
    user_id = session['user_id']
    device_id = request.args.get('device_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role == 'admin':
        c.execute("SELECT strftime('%m', event_datetime) as month, strftime('%d', event_datetime) as day, COUNT(*) as event_count FROM events WHERE mac_address =? GROUP BY month, day", (device_id,))
    else:
        c.execute("SELECT strftime('%m', event_datetime) as month, strftime('%d', event_datetime) as day, COUNT(*) as event_count FROM events WHERE mac_address =? AND user_id =? GROUP BY month, day", (device_id, user_id))
    records = [{'month': row[0], 'day': row[1], 'event_count': row[2]} for row in c.fetchall()]
    conn.close()
    return records

# 获取折线图数据 API
@app.route('/api/line_chart_data')
def get_line_chart_data():
    if not is_logged_in():
        return {}, 401
    role = session['role']
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role == 'admin':
        c.execute("SELECT mac_address, event_datetime, COUNT(*) as event_count FROM events GROUP BY mac_address, event_datetime")
    else:
        c.execute("SELECT mac_address, event_datetime, COUNT(*) as event_count FROM events WHERE user_id =? GROUP BY mac_address, event_datetime", (user_id,))
    records = c.fetchall()
    data = {}
    for mac, date, count in records:
        if date not in data:
            data[date] = {}
        data[date][mac] = {'event_count': count}
    conn.close()
    return data

# 历史记录页面
@app.route('/history')
def history():
    if not is_logged_in():
        return redirect(url_for('login'))
    role = session['role']
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role == 'admin':
        c.execute("SELECT e.mac_address, e.event_datetime, mu.device_name FROM events e JOIN mac_user mu ON e.mac_address = mu.mac_address")
    else:
        c.execute("SELECT e.mac_address, e.event_datetime, mu.device_name FROM events e JOIN mac_user mu ON e.mac_address = mu.mac_address WHERE e.user_id =?", (user_id,))
    events = c.fetchall()
    conn.close()
    return render_template('history.html', events=events)

# 获取音频文件列表 API
@app.route('/api/audio_files')
def get_audio_files():
    if not is_logged_in():
        return [], 401
    role = session['role']
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if role == 'admin':
        c.execute("SELECT e.mac_address, e.event_datetime, mu.device_name FROM events e JOIN mac_user mu ON e.mac_address = mu.mac_address")
    else:
        c.execute("SELECT e.mac_address, e.event_datetime, mu.device_name FROM events e JOIN mac_user mu ON e.mac_address = mu.mac_address WHERE e.user_id =?", (user_id,))
    events = [{'mac_address': row[0], 'event_datetime': row[1], 'device_name': row[2]} for row in c.fetchall()]
    conn.close()
    return events

if __name__ == '__main__':
    init_db()
    app.run(debug=True)