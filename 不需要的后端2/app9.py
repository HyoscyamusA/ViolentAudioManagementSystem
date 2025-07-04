from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import hashlib
import os
from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import hashlib
import os
import functools  # 新增导入

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = 'violence_detection.db'

# 数据库连接助手
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 初始化数据库
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
        ''')
        
        # 创建mac表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mac (
                mac_address TEXT PRIMARY KEY
            )
        ''')
        
        # 创建mac_user表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mac_user (
                mac_address TEXT,
                device_name TEXT,
                user_id INTEGER,
                FOREIGN KEY(mac_address) REFERENCES mac(mac_address),
                FOREIGN KEY(user_id) REFERENCES user(id),
                PRIMARY KEY (mac_address, user_id)
            )
        ''')
        
        # 创建events表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT,
                event_datetime DATETIME NOT NULL,
                user_id INTEGER,
                is_violence INTEGER DEFAULT 0,
                FOREIGN KEY(mac_address) REFERENCES mac(mac_address),
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        ''')
        
        # 创建默认管理员
        try:
            admin_pass = hashlib.sha256('admin'.encode()).hexdigest()
            root_pass = hashlib.sha256('root'.encode()).hexdigest()
            cursor.execute('INSERT INTO user (username, password, role) VALUES (?, ?, ?)', 
                         ('admin', admin_pass, 'admin'))
            cursor.execute('INSERT INTO user (username, password, role) VALUES (?, ?, ?)', 
                         ('root', root_pass, 'admin'))
            db.commit()
        except sqlite3.IntegrityError:
            pass

# 修正后的登录装饰器
def login_required(role=None):
    def decorator(f):
        @functools.wraps(f)  # 使用wraps保持函数元数据
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# 路由部分
@app.route('/dashboard')
@login_required()
def dashboard():
    return f"Welcome {session['username']} (Role: {session['role']})"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE username = ? AND password = ?',
                        (username, password)).fetchone()
        
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        try:
            db = get_db()
            db.execute('INSERT INTO user (username, password) VALUES (?, ?)',
                     (username, password))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username already exists')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required()
def dashboard():
    return f"Welcome {session['username']} (Role: {session['role']})"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)