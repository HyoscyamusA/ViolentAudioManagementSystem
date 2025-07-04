import sqlite3
from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for
from flask import g
import bcrypt
from flask import Flask, request, render_template

app = Flask(__name__)
app.secret_key = '123321'

# 初始化数据库
def init_db():
    conn = sqlite3.connect('violence_events.db')
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

# 获取数据库连接
def get_db_connection():
    if 'db' not in g:
        g.db = sqlite3.connect('violence_events.db')
        g.db.row_factory = sqlite3.Row
    return g.db

# 关闭数据库连接
@app.teardown_appcontext
def close_db_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('violence_events.db')
        c = conn.cursor()
        c.execute("SELECT id, username, role FROM user WHERE username =? AND password =?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2]
            return redirect('/dashboard')
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

# 注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')  # 直接使用明文密码
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')

        conn = sqlite3.connect('violence_events.db')
        c = conn.cursor()
        try:
            # 直接插入明文密码（危险操作！）
            c.execute("INSERT INTO user (username, password, role) VALUES (?, ?, 'user')", 
                      (username, password))  # 移除了哈希
            conn.commit()
            conn.close()
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

# 设备绑定路由
@app.route('/device/bind', methods=['GET', 'POST'])
def device_bind():
    if 'username' not in session:
        return "请先登录", 401
    
    if request.method == 'POST':
        mac_address = request.form['mac_address'].strip()
        device_name = request.form.get('device_name', '默认设备名').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查MAC是否存在
        cursor.execute('SELECT COUNT(*) FROM mac WHERE mac_address =?', (mac_address,))
        if cursor.fetchone()[0] == 0:
            flash("错误：MAC地址不存在", "error")
            conn.close()
            return redirect(url_for('device_bind'))
        
        # 检查是否已被当前用户绑定
        cursor.execute('''
            SELECT COUNT(*) 
            FROM mac_user 
            WHERE mac_address =? 
            AND user_id =?
        ''', (mac_address, session['user_id']))
        if cursor.fetchone()[0] > 0:
            flash("错误：该设备已绑定到您的账户", "error")
            conn.close()
            return redirect(url_for('device_bind'))
        
        # 检查是否被其他用户绑定
        cursor.execute('''
            SELECT COUNT(*) 
            FROM mac_user 
            WHERE mac_address =? 
            AND user_id !=?
        ''', (mac_address, session['user_id']))
        if cursor.fetchone()[0] > 0:
            flash("错误：该设备已被其他用户绑定", "error")
            conn.close()
            return redirect(url_for('device_bind'))
        
        # 执行绑定
        try:
            cursor.execute('''
                INSERT INTO mac_user (mac_address, device_name, user_id)
                VALUES (?, ?, ?)
            ''', (mac_address, device_name, session['user_id']))
            conn.commit()
            flash("设备绑定成功", "success")
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("绑定失败，数据完整性错误", "error")
        finally:
            conn.close()
        
        return redirect(url_for('device_manage'))
    
    return render_template('device_bind.html')

# 管理员查看所有设备路由
@app.route('/device/all')
def device_all():
    if 'username' not in session or session['role'] != 'admin':
        return "权限不足", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 查询mac表所有设备，以及绑定情况
    cursor.execute('''
        SELECT 
            m.mac_address, 
            mu.device_name, 
            mu.user_id, 
            u.username 
        FROM mac m
        LEFT JOIN mac_user mu ON m.mac_address = mu.mac_address
        LEFT JOIN user u ON mu.user_id = u.id
    ''')
    
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('device_all.html', devices=devices)


@app.route('/events/all')
def events_all():
    if 'username' not in session:
        return "请先登录", 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, role FROM user WHERE username =?', (session['username'],))
    user_info = cursor.fetchone()
    if not user_info:
        return "用户不存在", 404

    user_id = user_info['id']
    role = user_info['role']

    # 基础查询语句
    base_query = '''
        SELECT 
            e.event_datetime, 
            e.mac_address, 
            mu.device_name
    '''
    join_clause = 'FROM events e JOIN mac_user mu ON e.mac_address = mu.mac_address '
    where_clause = []
    params = []

    if role == 'admin':
        base_query += ', u.username '
        join_clause += 'JOIN user u ON e.user_id = u.id '
    else:
        where_clause.append("e.user_id =?")
        params.append(user_id)

    # 处理筛选条件
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    device_mac = request.args.get('device_mac')

    if start_date:
        where_clause.append("e.event_datetime >=?")
        params.append(f"{start_date} 00:00:00")
    if end_date:
        where_clause.append("e.event_datetime <=?")
        params.append(f"{end_date} 23:59:59")
    if device_mac:
        where_clause.append("e.mac_address =?")
        params.append(device_mac)

    # 组合查询语句
    final_query = base_query + join_clause
    if where_clause:
        final_query += "WHERE " + " AND ".join(where_clause)

    # 打印最终查询语句和参数，用于调试
    print("Final Query:", final_query)
    print("Parameters:", params)

    cursor.execute(final_query, params)
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return render_template('events_all.html', records=records, role=role)

# 设备管理
@app.route('/device/manage')
def device_manage():
    if 'username' not in session:
        return "请先登录", 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, role FROM user WHERE username =?', (session['username'],))
    user_info = cursor.fetchone()
    if not user_info:
        return "用户不存在", 404
    user_id = user_info['id']
    role = user_info['role']
    if role == 'admin':
        cursor.execute('''
            SELECT 
                mac.mac_address, 
                mac_user.device_name, 
                user.username AS username 
            FROM mac 
            JOIN mac_user ON mac.mac_address = mac_user.mac_address 
            JOIN user ON mac_user.user_id = user.id
        ''')
    else:
        cursor.execute('''
            SELECT 
                mac.mac_address, 
                mac_user.device_name 
            FROM mac 
            JOIN mac_user ON mac.mac_address = mac_user.mac_address 
            WHERE mac_user.user_id =?
        ''', (user_id,))
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('device_manage.html', devices=devices, role=role)

@app.route('/device/unbind', methods=['POST'])
def device_unbind():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    mac_address = request.form.get('mac_address')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_id = session.get('user_id')
    role = session.get('role')
    
    try:
        if role == 'admin':
            # 管理员解绑任意设备
            cursor.execute('DELETE FROM mac_user WHERE mac_address = ?', (mac_address,))
        else:
            # 普通用户解绑自己的设备
            cursor.execute('''
                DELETE FROM mac_user 
                WHERE mac_address = ? AND user_id = ?
            ''', (mac_address, user_id))
        
        conn.commit()
        return jsonify({"status": "success", "message": "解绑成功"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"解绑失败：{str(e)}"}), 500
    finally:
        conn.close()

@app.route('/device/update_name')
def update_device_name():
    if 'username' not in session:
        return "请先登录", 401
    
    mac_address = request.args.get('mac_address')
    new_name = request.args.get('new_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id, role FROM user WHERE username =?', (session['username'],))
        user_info = cursor.fetchone()
        if not user_info:
            conn.close()
            return "用户不存在", 404
        
        user_id = user_info['id']
        role = user_info['role']
        
        if role == 'admin':
            cursor.execute('UPDATE mac_user SET device_name =? WHERE mac_address =?', (new_name, mac_address))
        else:
            cursor.execute('UPDATE mac_user SET device_name =? WHERE mac_address =? AND user_id =?', 
                          (new_name, mac_address, user_id))
        
        conn.commit()
        return 'success'
    except sqlite3.Error as e:
        conn.rollback()  # 出错时回滚事务
        return f"设备名称更新失败，数据库错误：{str(e)}", 500
    finally:
        conn.close()

# 数据可视化页面
@app.route('/data_visualization')
def data_visualization():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('data_visualization.html')

# 获取折线图数据
@app.route('/api/line_chart_data', methods=['GET'])
def get_line_chart_data():
    if 'user_id' not in session:
        return redirect('/login')
    try:
        conn = sqlite3.connect('violence_events.db')
        cursor = conn.cursor()
        if session['role'] == 'admin':
            cursor.execute('''
                SELECT 
                    e.mac_address, 
                    SUBSTR(e.event_datetime, 1, 10) AS event_date, 
                    COUNT(*) AS event_count,
                    mu.device_name
                FROM events e 
                JOIN mac_user mu ON e.mac_address = mu.mac_address 
                GROUP BY e.mac_address, event_date 
                ORDER BY event_date
            ''')
        else:
            user_id = session['user_id']
            cursor.execute('''
                SELECT 
                    e.mac_address, 
                    SUBSTR(e.event_datetime, 1, 10) AS event_date, 
                    COUNT(*) AS event_count,
                    mu.device_name
                FROM events e 
                JOIN mac_user mu ON e.mac_address = mu.mac_address 
                WHERE mu.user_id = ?
                GROUP BY e.mac_address, event_date 
                ORDER BY event_date
            ''', (user_id,))
        
        data = cursor.fetchall()
        conn.close()
        formatted_data = {}
        for mac_address, date, count, device_name in data:
            if date not in formatted_data:
                formatted_data[date] = {}
            formatted_data[date][mac_address] = {
                'event_count': count,
                'device_name': device_name,
                'device_id': mac_address  # 明确返回设备ID（mac_address）
            }
        return jsonify(formatted_data), 200
    except Exception as e:
        return jsonify({'message': f'服务器内部错误：{str(e)}'}), 500

# 获取设备列表
@app.route('/api/devices')
def get_devices():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "未登录"}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session['user_id']
    role = session['role']
    
    if role == 'admin':
        cursor.execute('''
            SELECT 
                mu.mac_address AS device_id, 
                mu.device_name
            FROM mac_user mu
        ''')
    else:
        cursor.execute('''
            SELECT 
                mu.mac_address AS device_id, 
                mu.device_name
            FROM mac_user mu 
            WHERE mu.user_id = ?
        ''', (user_id,))
    
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(devices)

# 获取热力图数据
@app.route('/api/heatmap_data')
def get_heatmap_data():
    device_id = request.args.get('device_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            strftime('%m', event_datetime) AS month, 
            strftime('%d', event_datetime) AS day, 
            COUNT(*) AS event_count
        FROM events
        WHERE mac_address =?
        GROUP BY month, day
    ''', (device_id,))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(records)

# 注销
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)