import sqlite3
from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# 初始化数据库
def init_db():
    conn = sqlite3.connect('violence.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS mac (
                    mac_address TEXT PRIMARY KEY
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS mac_user (
                    mac_address TEXT,
                    device_name TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (mac_address) REFERENCES mac(mac_address),
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS events (
                    mac_address TEXT,
                    event_datetime TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (mac_address) REFERENCES mac(mac_address),
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )''')
    c.execute("INSERT OR IGNORE INTO user (username, password, role) VALUES ('admin', 'root', 'admin')")
    conn.commit()
    conn.close()

# 登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('violence.db')
        c = conn.cursor()
        c.execute("SELECT id, role FROM user WHERE username =? AND password =?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['role'] = user[1]
            return redirect('/dashboard')
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

# 注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('violence.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO user (username, password, role) VALUES (?,?, 'user')", (username, password))
            conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Username already exists')
    return render_template('register.html')


# 仪表盘
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html')

# 设备绑定（示例）
@app.route('/device/add', methods=['POST'])
def add_device():
    if 'user_id' not in session:
        return redirect('/login')
    mac_address = request.form['mac_address']
    device_name = request.form['device_name']
    user_id = session['user_id']
    conn = sqlite3.connect('violence.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO mac_user (mac_address, device_name, user_id) VALUES (?,?,?)", 
                  (mac_address, device_name, user_id))
        conn.commit()
        return "设备绑定成功"
    except sqlite3.IntegrityError:
        conn.close()
        return "设备绑定失败，检查MAC地址是否已存在"
    finally:
        conn.close()

# 获取事件数据（图表用）
@app.route('/events/data')
def events_data():
    if 'user_id' not in session:
        return redirect('/login')
    conn = sqlite3.connect('violence.db')
    c = conn.cursor()
    if session['role'] == 'admin':
        c.execute("SELECT event_datetime FROM events")
    else:
        user_id = session['user_id']
        c.execute("SELECT event_datetime FROM events WHERE user_id=?", (user_id,))
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({'event_times': data})
# 设备列表（示例路由，需补充数据库查询）
@app.route('/device/list')
def device_list():
    if 'user_id' not in session:
        return redirect('/login')
    conn = sqlite3.connect('violence.db')
    c = conn.cursor()
    if session['role'] == 'admin':
        c.execute("SELECT * FROM mac_user")
    else:
        user_id = session['user_id']
        c.execute("SELECT * FROM mac_user WHERE user_id=?", (user_id,))
    devices = c.fetchall()
    conn.close()
    return render_template('device_list.html', devices=devices)
# 注销
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)