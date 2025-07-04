from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import sqlite3
from datetime import timedelta

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your_secret_key'  # 请替换为更安全的密钥
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)

bcrypt = Bcrypt(app)
jwt = JWTManager(app)

DATABASE = 'events.db'

def init_db():
    """初始化数据库，创建用户表"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT CHECK(role IN ('admin', 'user')) NOT NULL
                    )''')
    
    # 默认管理员账户
    cursor.execute("SELECT * FROM user WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_password = bcrypt.generate_password_hash('root').decode('utf-8')
        cursor.execute("INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)", ('admin', hashed_password, 'admin'))
    
    conn.commit()
    conn.close()

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')  # 默认为普通用户

    if not username or not password:
        return jsonify({'message': '用户名和密码不能为空'}), 400
    
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)", (username, password_hash, role))
        conn.commit()
        conn.close()
        return jsonify({'message': '注册成功'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': '用户名已存在'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash, role FROM user WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and bcrypt.check_password_hash(user[1], password):
        access_token = create_access_token(identity={'id': user[0], 'role': user[2]})
        return jsonify({'token': access_token, 'role': user[2]}), 200
    else:
        return jsonify({'message': '用户名或密码错误'}), 401

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({'message': '访问成功', 'user': current_user}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True)