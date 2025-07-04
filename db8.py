import sqlite3
import random
import string
from datetime import datetime, timedelta

# 连接到 SQLite 数据库
conn = sqlite3.connect('violence.db')
cursor = conn.cursor()

# 生成随机字符串
def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))

# 生成随机 MAC 地址
def generate_mac_address():
    return ':'.join(['{:02x}'.format(random.randint(0, 255)) for _ in range(6)])

# 生成随机日期时间
def generate_random_datetime():
    start_date = datetime.now() - timedelta(days=365)
    end_date = datetime.now()
    random_time = start_date + (end_date - start_date) * random.random()
    return random_time.strftime('%Y-%m-%d %H:%M:%S')

# 插入用户数据
users = [
    ('admin', 'adminpassword', 'admin')
]
# 生成 10 个普通用户
for i in range(10):
    username = f'user{i}'
    password = f'password{i}'
    role = 'user'
    users.append((username, password, role))

for user in users:
    username = user[0]
    cursor.execute('SELECT id FROM user WHERE username =?', (username,))
    existing_user = cursor.fetchone()
    if not existing_user:
        cursor.execute('INSERT INTO user (username, password, role) VALUES (?,?,?)', user)

# 获取所有用户的 ID
cursor.execute('SELECT id FROM user')
user_ids = [row[0] for row in cursor.fetchall()]

# 插入 MAC 地址数据
mac_addresses = []
for _ in range(20):
    mac = generate_mac_address()
    mac_addresses.append(mac)
    cursor.execute('INSERT INTO mac (mac_address) VALUES (?)', (mac,))

# 插入 mac_user 数据
for mac in mac_addresses:
    user_id = random.choice(user_ids)
    device_name = random_string(8)
    cursor.execute('INSERT INTO mac_user (mac_address, device_name, user_id) VALUES (?,?,?)', (mac, device_name, user_id))

# 插入事件数据
for _ in range(100):
    mac_address = random.choice(mac_addresses)
    event_datetime = generate_random_datetime()
    user_id = random.choice(user_ids)
    cursor.execute('INSERT INTO events (mac_address, event_datetime, user_id) VALUES (?,?,?)', (mac_address, event_datetime, user_id))

# 提交更改并关闭连接
conn.commit()
conn.close()

print("数据插入完成。")