from flask import Flask, render_template, flash, request, abort, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = '123'  # flash 加密

# 初始化数据库
def init_db():
    conn = sqlite3.connect('violence.db')
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
    c.execute("SELECT * FROM user WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO user (username, password, role) VALUES ('admin', 'root', 'admin')")
    conn.commit()
    conn.close()

# 数据库操作类
class DatabaseUtils:
    def __init__(self):
        self.conn = sqlite3.connect('violence.db')
        self.c = self.conn.cursor()

    def register_user(self, username, password):
        try:
            self.c.execute("INSERT INTO user (username, password, role) VALUES (?,?,?)", (username, password, 'user'))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def login_user(self, username, password):
        self.c.execute("SELECT id, role FROM user WHERE username =? AND password =?", (username, password))
        result = self.c.fetchone()
        if result:
            return result[0], result[1]
        return None, None

    def add_mac(self, mac_address):
        try:
            self.c.execute("INSERT INTO mac (mac_address) VALUES (?)", (mac_address,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def bind_mac_to_user(self, mac_address, device_name, user_id):
        try:
            self.c.execute("INSERT INTO mac_user (mac_address, device_name, user_id) VALUES (?,?,?)",
                           (mac_address, device_name, user_id))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def record_event(self, mac_address, user_id):
        event_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.c.execute("INSERT INTO events (mac_address, event_datetime, user_id) VALUES (?,?,?)",
                       (mac_address, event_datetime, user_id))
        self.conn.commit()

    def get_user_devices(self, user_id):
        self.c.execute("SELECT mac_address, device_name FROM mac_user WHERE user_id =?", (user_id,))
        return self.c.fetchall()

    def get_all_devices(self):
        self.c.execute("SELECT mac_address, device_name FROM mac_user")
        return self.c.fetchall()

    def get_user_events(self, user_id):
        self.c.execute("SELECT mac_address, event_datetime FROM events WHERE user_id =?", (user_id,))
        return self.c.fetchall()

    def get_all_events(self):
        self.c.execute("SELECT mac_address, event_datetime FROM events")
        return self.c.fetchall()

    def close(self):
        self.conn.close()

# 初始化数据库
init_db()

# 检查用户是否登录
def login_required(func):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# 首页
@app.route('/')
def hello_world():
    return redirect(url_for('login'))

# 注册
@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == "POST":
        form = request.form
        username = form.get('username')
        password = form.get('password')
        if not username:
            flash("请输入用户名")
            return render_template("register.html")
        if not password:
            flash("请输入密码")
            return render_template("register.html")
        db = DatabaseUtils()
        if db.register_user(username, password):
            flash("注册成功")
            return redirect(url_for('login'))
        else:
            flash("用户名已存在")
            return render_template("register.html")
    else:
        return render_template("register.html")

# 登录界面路由
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        form = request.form
        username = form.get('username')
        password = form.get('password')
        if not username:
            flash("请输入用户名")
            return render_template("login.html")
        if not password:
            flash("请输入密码")
            return render_template("login.html")
        db = DatabaseUtils()
        user_id, role = db.login_user(username, password)
        db.close()
        if user_id:
            session['user_id'] = user_id
            session['role'] = role
            return redirect(url_for('dashboard'))
        else:
            flash("用户名或密码错误")
            return render_template("login.html")
    else:
        return render_template("login.html")

# 仪表盘
@app.route('/dashboard')
@login_required
def dashboard():
    db = DatabaseUtils()
    if session['role'] == 'admin':
        devices = db.get_all_devices()
        events = db.get_all_events()
    else:
        devices = db.get_user_devices(session['user_id'])
        events = db.get_user_events(session['user_id'])
    db.close()
    return render_template("dashboard.html", devices=devices, events=events)

# 添加设备
@app.route('/add_device', methods=['POST', 'GET'])
@login_required
def add_device():
    if request.method == "POST":
        form = request.form
        mac_address = form.get('mac_address')
        device_name = form.get('device_name')
        if not mac_address:
            flash("请输入设备 MAC 地址")
            return render_template("add_device.html")
        if not device_name:
            flash("请输入设备名称")
            return render_template("add_device.html")
        db = DatabaseUtils()
        if db.add_mac(mac_address):
            if db.bind_mac_to_user(mac_address, device_name, session['user_id']):
                flash("设备添加成功")
                return redirect(url_for('dashboard'))
            else:
                flash("设备绑定失败")
        else:
            flash("设备 MAC 地址已存在")
        db.close()
        return render_template("add_device.html")
    else:
        return render_template("add_device.html")

# 记录事件
@app.route('/record_event/<mac_address>')
@login_required
def record_event(mac_address):
    db = DatabaseUtils()
    db.record_event(mac_address, session['user_id'])
    db.close()
    flash("事件记录成功")
    return redirect(url_for('dashboard'))

# 退出登录
@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('login'))

# 示例侧边栏页面 - 设备列表
@app.route('/device_list')
@login_required
def device_list():
    db = DatabaseUtils()
    if session['role'] == 'admin':
        devices = db.get_all_devices()
    else:
        devices = db.get_user_devices(session['user_id'])
    db.close()
    return render_template("device_list.html", devices=devices)

# 示例侧边栏页面 - 事件列表
@app.route('/event_list')
@login_required
def event_list():
    db = DatabaseUtils()
    if session['role'] == 'admin':
        events = db.get_all_events()
    else:
        events = db.get_user_events(session['user_id'])
    db.close()
    return render_template("event_list.html", events=events)

if __name__ == '__main__':
    app.run(debug=True)