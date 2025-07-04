# app.py - 改造后的主程序
from flask import Flask, render_template, flash, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///violence.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 数据库模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(120))
    role = db.Column(db.String(20), default='user')

class Mac(db.Model):
    mac_address = db.Column(db.String(17), primary_key=True)

class MacUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), db.ForeignKey('mac.mac_address'))
    device_name = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17))
    event_datetime = db.Column(db.DateTime)
    is_violent = db.Column(db.Boolean)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# 登录检查装饰器
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# 管理员权限检查装饰器
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

# 路由部分
@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password2 = request.form['password2']
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return redirect(url_for('register'))
        
        if password != password2:
            flash('两次密码不一致')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            password=generate_password_hash(password),
            role='user'
        )
        db.session.add(new_user)
        db.session.commit()
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/devices')
@login_required
def devices():
    if session['role'] == 'admin':
        devices = MacUser.query.all()
    else:
        devices = MacUser.query.filter_by(user_id=session['user_id']).all()
    return render_template('devices.html', devices=devices)

@app.route('/add-device', methods=['POST'])
@login_required
def add_device():
    mac = request.form['mac']
    device_name = request.form['device_name']
    
    # 验证MAC地址格式
    if not validate_mac(mac):
        flash('无效的MAC地址')
        return redirect(url_for('devices'))
    
    # 检查MAC是否已存在
    if Mac.query.get(mac) is None:
        db.session.add(Mac(mac_address=mac))
    
    new_device = MacUser(
        mac_address=mac,
        device_name=device_name,
        user_id=session['user_id']
    )
    db.session.add(new_device)
    db.session.commit()
    
    flash('设备添加成功')
    return redirect(url_for('devices'))

@app.route('/events')
@login_required
def events():
    if session['role'] == 'admin':
        events = Event.query.all()
    else:
        events = Event.query.filter_by(user_id=session['user_id']).all()
    return render_template('events.html', events=events)

@app.route('/charts')
@login_required
def charts():
    return render_template('charts.html')

# 初始化数据库
@app.cli.command('init-db')
def init_db():
    db.create_all()
    admin = User(
        username='admin',
        password=generate_password_hash('root'),
        role='admin'
    )
    db.session.add(admin)
    db.session.commit()
    print('数据库初始化完成')

if __name__ == '__main__':
    app.run(debug=True)