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
# 修改登录路由查询语句
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('violence.db')
        c = conn.cursor()
        # 添加 username 到查询结果中
        c.execute("SELECT id, username, role FROM user WHERE username =? AND password =?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]  # 保存用户名到 session
            session['role'] = user[2]
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

# 在 app.py 中添加以下路由
@app.route('/events/all')
def events_all():
    return render_template('events_all.html')  # 需创建对应模板

@app.route('/device/manage')
def device_manage():
    return render_template('device_manage.html')  # 需创建对应模板


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


# 数据可视化
@app.route('/data_visualization')
def data_visualization():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('data_visualization.html')  # 需创建对应模板


# 获取折线图数据
@app.route('/api/line_chart_data', methods=['GET'])
def get_line_chart_data():
    if 'user_id' not in session:
        return redirect('/login')
    try:
        conn = sqlite3.connect('violence.db')
        cursor = conn.cursor()
        if session['role'] == 'admin':
            cursor.execute('''SELECT mac_address, SUBSTR(event_datetime, 1, 10) AS event_date, COUNT(*) 
                              FROM events GROUP BY mac_address, event_date ORDER BY event_date''')
        else:
            user_id = session['user_id']
            cursor.execute("SELECT mac_address FROM mac_user WHERE user_id=?", (user_id,))
            user_macs = [row[0] for row in cursor.fetchall()]
            if not user_macs:
                conn.close()
                return jsonify({})
            query = '''SELECT mac_address, SUBSTR(event_datetime, 1, 10) AS event_date, COUNT(*) 
                       FROM events WHERE mac_address IN ({}) 
                       GROUP BY mac_address, event_date ORDER BY event_date'''.format(
                ','.join(['?'] * len(user_macs))
            )
            cursor.execute(query, user_macs)

        data = cursor.fetchall()
        conn.close()

        formatted_data = {}
        for mac_address, date, count in data:
            if date not in formatted_data:
                formatted_data[date] = {}
            formatted_data[date][mac_address] = {'event_count': count}

        return jsonify(formatted_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

# 获取热力图数据
@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap_data():
    if 'user_id' not in session:
        return redirect('/login')
    try:
        device_id = request.args.get('device_id', 'unknown')
        conn = sqlite3.connect('violence.db')
        cursor = conn.cursor()
        if session['role'] == 'admin':
            cursor.execute('''SELECT strftime('%m', event_datetime) AS month, 
                                     strftime('%d', event_datetime) AS day, 
                                     COUNT(*) AS event_count
                              FROM events WHERE mac_address =? 
                              GROUP BY month, day''', (device_id,))
        else:
            user_id = session['user_id']
            cursor.execute("SELECT mac_address FROM mac_user WHERE user_id=?", (user_id,))
            user_macs = [row[0] for row in cursor.fetchall()]
            if device_id not in user_macs:
                conn.close()
                return jsonify([])
            cursor.execute('''SELECT strftime('%m', event_datetime) AS month, 
                                     strftime('%d', event_datetime) AS day, 
                                     COUNT(*) AS event_count
                              FROM events WHERE mac_address =? 
                              GROUP BY month, day''', (device_id,))

        data = cursor.fetchall()
        conn.close()

        heatmap_data = [{'month': row[0], 'day': int(row[1]), 'event_count': row[2]} for row in data]
        return jsonify(heatmap_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500


# 设备列表
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