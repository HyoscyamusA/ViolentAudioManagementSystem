import sqlite3
from datetime import datetime

# 连接到数据库
DATABASE = 'events.db'
conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

# 插入一些测试数据（根据不同设备和日期）
test_data = [
    ('2025-02-01', 'device_1', 'Device A', 1),  # 设备 A 在 2025-02-01 上传了暴力事件
    ('2025-02-01', 'device_2', 'Device B', 1),  # 设备 B 在 2025-02-01 上传了暴力事件
    ('2025-02-02', 'device_1', 'Device A', 2),  # 设备 A 在 2025-02-02 上传了 2 次暴力事件
    ('2025-02-03', 'device_3', 'Device C', 1),  # 设备 C 在 2025-02-03 上传了暴力事件
    ('2025-02-04', 'device_2', 'Device B', 3),  # 设备 B 在 2025-02-04 上传了 3 次暴力事件
    ('2025-02-05', 'device_4', 'Device D', 1),  # 设备 D 在 2025-02-05 上传了暴力事件
    ('2025-02-06', 'device_1', 'Device A', 1),  # 设备 A 在 2025-02-06 上传了暴力事件
    ('2025-02-06', 'device_3', 'Device C', 1),  # 设备 C 在 2025-02-06 上传了暴力事件
    ('2025-02-07', 'device_2', 'Device B', 1),  # 设备 B 在 2025-02-07 上传了暴力事件
]

# 将测试数据插入数据库
cursor.executemany('''INSERT INTO events (event_date, device_id, device_name, event_count)
                       VALUES (?, ?, ?, ?)''', test_data)

# 提交事务并关闭连接
conn.commit()
conn.close()

print("测试数据已成功插入数据库。")
