from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3
import hashlib
import os
import functools

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['DATABASE'] = 'violence_detection.db'
app.config['INIT_ADMINS'] = [('admin', 'admin'), ('root', 'root')]

# 数据库辅助函数
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )''')
        
        # MAC地址表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mac (
                mac_address TEXT PRIMARY KEY
            )''')
        
        # 用户设备关联表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mac_user (
                mac_address TEXT,
                device_name TEXT,
                user_id INTEGER,
                FOREIGN KEY(mac_address) REFERENCES mac(mac_address),
                FOREIGN KEY(user_id) REFERENCES user(id),
                PRIMARY KEY (mac_address, user_id)
            )''')
        
        # 事件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT,
                event_datetime DATETIME NOT NULL,
                user_id INTEGER,
                is_violence INTEGER DEFAULT 0,
                FOREIGN KEY(mac_address) REFERENCES mac(mac_address),
                FOREIGN KEY(user_id) REFERENCES user(id)
            )''')
        
        # 初始化管理员账户
        for username, password in app.config['INIT_ADMINS']:
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            try:
                cursor.execute('INSERT INTO user (username, password, role) VALUES (?, ?, ?)',
                             (username, hashed_pw, 'admin'))
            except sqlite3.IntegrityError:
                pass
        db.commit()

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

# 登录装饰器（带权限控制）
def login_required(roles=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                flash('请先登录')
                return redirect(url_for('login'))
                
            if roles and session.get('role') not in roles:
                flash('权限不足')
                return redirect(url_for('dashboard'))
                
            return f(*args, **kwargs)
        return wrapped
    return decorator

# 路由配置
@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = hashlib.sha256(request.form.get('password', '').encode()).hexdigest()
        
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE username = ? AND password = ?',
                        (username, password)).fetchone()
        
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        
        flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('请输入用户名和密码')
            return redirect(url_for('register'))
        
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            db = get_db()
            db.execute('INSERT INTO user (username, password) VALUES (?, ?)',
                      (username, hashed_pw))
            db.commit()
            flash('注册成功，请登录')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名已存在')
        except Exception as e:
            flash('注册失败：{}'.format(str(e)))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required()
def dashboard():
    db = get_db()
    
    # 获取用户设备
    devices = db.execute('''
        SELECT mu.mac_address, mu.device_name 
        FROM mac_user mu
        WHERE mu.user_id = ?
    ''', (session['user_id'],)).fetchall()
    
    # 获取事件统计
    if session['role'] == 'admin':
        events = db.execute('''
            SELECT e.*, u.username 
            FROM events e
            JOIN user u ON e.user_id = u.id
        ''').fetchall()
    else:
        events = db.execute('''
            SELECT * FROM events 
            WHERE user_id = ?
        ''', (session['user_id'],)).fetchall()
    
    return render_template('dashboard.html',
                         username=session['username'],
                         role=session['role'],
                         devices=devices,
                         events=events)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 设备管理路由
@app.route('/device/add', methods=['POST'])
@login_required(roles=['user', 'admin'])
def add_device():
    mac_address = request.form.get('mac_address')
    device_name = request.form.get('device_name')
    
    if not mac_address or not device_name:
        flash('请填写完整设备信息')
        return redirect(url_for('dashboard'))
    
    db = get_db()
    try:
        # 先插入mac表
        db.execute('INSERT OR IGNORE INTO mac (mac_address) VALUES (?)', (mac_address,))
        # 关联用户设备
        db.execute('''
            INSERT INTO mac_user (mac_address, device_name, user_id)
            VALUES (?, ?, ?)
        ''', (mac_address, device_name, session['user_id']))
        db.commit()
        flash('设备添加成功')
    except sqlite3.IntegrityError:
        flash('设备已存在或MAC地址重复')
    except Exception as e:
        flash(f'添加失败：{str(e)}')
    
    return redirect(url_for('dashboard'))

# 事件记录接口
@app.route('/event/add', methods=['POST'])
@login_required()
def add_event():
    data = request.get_json()
    
    required_fields = ['mac_address', 'event_datetime', 'is_violence']
    if not all(field in data for field in required_fields):
        return {'status': 'error', 'message': 'Missing required fields'}, 400
    
    try:
        db = get_db()
        db.execute('''
            INSERT INTO events (mac_address, event_datetime, user_id, is_violence)
            VALUES (?, ?, ?, ?)
        ''', (data['mac_address'], data['event_datetime'], session['user_id'], data['is_violence']))
        db.commit()
        return {'status': 'success'}, 201
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)