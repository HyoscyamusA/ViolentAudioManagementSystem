from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # 用于 session 管理
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

# 用户表
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='user')  # 'admin' 或 'user'

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

# 设备表
class Mac(db.Model):
    mac_address = db.Column(db.String(17), primary_key=True)

# 用户绑定设备表
class MacUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), db.ForeignKey('mac.mac_address'), nullable=False)
    device_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# 事件表
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), db.ForeignKey('mac.mac_address'), nullable=False)
    event_datetime = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# 初始化数据库，并创建默认管理员
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('root')
        db.session.add(admin)
        db.session.commit()

# 注册 API
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': '用户名和密码不能为空！'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': '用户名已存在！'}), 400

    new_user = User(username=username, role='user')
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': '注册成功！'}), 201

# 登录 API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'message': '用户名或密码错误！'}), 401

    session['user_id'] = user.id  # 存储 session
    session['role'] = user.role

    return jsonify({'message': '登录成功！', 'role': user.role}), 200

# 获取设备列表（仅用户自己的设备）
@app.route('/api/devices', methods=['GET'])
def get_user_devices():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': '请先登录！'}), 401

    devices = MacUser.query.filter_by(user_id=user_id).all()
    devices_list = [{'mac_address': d.mac_address, 'device_name': d.device_name} for d in devices]

    return jsonify(devices_list), 200

# 绑定设备（用户绑定 MAC 地址）
@app.route('/api/bind_device', methods=['POST'])
def bind_device():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': '请先登录！'}), 401

    data = request.json
    mac_address = data.get('mac_address')
    device_name = data.get('device_name')

    if not Mac.query.filter_by(mac_address=mac_address).first():
        return jsonify({'message': '设备 MAC 地址不存在！'}), 404

    if MacUser.query.filter_by(mac_address=mac_address, user_id=user_id).first():
        return jsonify({'message': '你已绑定该设备！'}), 400

    new_binding = MacUser(mac_address=mac_address, device_name=device_name, user_id=user_id)
    db.session.add(new_binding)
    db.session.commit()

    return jsonify({'message': '设备绑定成功！'}), 201

# 获取历史事件
@app.route('/api/history', methods=['GET'])
def get_history():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': '请先登录！'}), 401

    user_devices = MacUser.query.filter_by(user_id=user_id).all()
    user_device_mac = [d.mac_address for d in user_devices]

    events = Event.query.filter(Event.mac_address.in_(user_device_mac)).all()
    history_data = [{'mac_address': e.mac_address, 'event_datetime': e.event_datetime} for e in events]

    return jsonify(history_data), 200

# 退出登录 API
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': '退出成功！'}), 200

if __name__ == '__main__':
    app.run(debug=True)
