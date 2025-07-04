import sqlite3
import random
from datetime import datetime, timedelta

# 设备列表
device_ids = ['device_1', 'device_2', 'device_3', 'device_4', 'device_5', 'device_6', 'device_7', 'device_8']
device_names = ['Device A', 'Device B', 'Device C', 'Device D', 'Device E', 'Device F', 'Device G', 'Device H']

# 设置日期范围
start_date = datetime(2025, 2, 1)
end_date = datetime(2025, 2, 28)
date_range = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

# 模拟数据
def generate_data():
    data = []
    for date in date_range:
        for device_id, device_name in zip(device_ids, device_names):
            # 使得2月7日至2月28日期间的设备事件次数差距更大
            if date >= datetime(2025, 2, 7):
                # 模拟高波动：在2月7日后设备的事件次数可以极端波动
                event_count = random.randint(100, 200)  # 增大事件次数差距
            else:
                # 2月1日到2月6日之间设置更小的波动
                event_count = random.randint(1, 50)
            
            data.append((date.strftime('%Y-%m-%d'), device_id, device_name, event_count))
    return data

# 数据库路径
DATABASE = 'events.db'

def insert_data_to_db(data):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 创建表格（如果不存在）
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        event_count INTEGER NOT NULL)''')

    # 插入数据
    cursor.executemany('''INSERT INTO events (event_date, device_id, device_name, event_count) 
                           VALUES (?, ?, ?, ?)''', data)

    conn.commit()
    conn.close()
    print(f"{len(data)} 条数据已成功插入！")

# 生成数据并插入数据库
data = generate_data()
insert_data_to_db(data)
