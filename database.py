"""
import sqlite3

def create_database():
    conn = sqlite3.connect('events.db')
    cursor = conn.cursor()

    # 创建上传记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # 创建暴力事件预测记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS violence_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        violent_probability REAL,
        non_violent_probability REAL
    );
    ''')

    conn.commit()
    conn.close()
    print("数据库创建成功！")

if __name__ == '__main__':
    create_database()
"""


"""
import sqlite3
from datetime import datetime

def init_db():
    # 创建数据库文件（如果没有的话）
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # 创建表格
    cursor.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        violent_probability REAL NOT NULL,
        non_violent_probability REAL NOT NULL,
        timestamp TEXT NOT NULL,
        device_id TEXT NOT NULL
    )''')

    conn.commit()
    conn.close()

def insert_record(filename, violent_probability, non_violent_probability, device_id):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # 插入数据到数据库
    cursor.execute('''INSERT INTO records (filename, violent_probability, non_violent_probability, timestamp, device_id)
                      VALUES (?, ?, ?, ?, ?)''', (filename, violent_probability, non_violent_probability, timestamp, device_id))
    
    conn.commit()
    conn.close()

def get_daily_records():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # 获取按日期分组的记录
    cursor.execute('''SELECT strftime('%Y-%m-%d', timestamp) AS date, 
                             AVG(violent_probability) AS avg_violent_prob,
                             AVG(non_violent_probability) AS avg_non_violent_prob
                      FROM records
                      GROUP BY date
                      ORDER BY date ASC''')
    records = cursor.fetchall()
    conn.close()
    return records

def get_heatmap_data():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # 获取所有记录的经纬度和暴力概率（示例数据，实际可以通过前端传过来的数据来定制）
    cursor.execute('SELECT device_id, violent_probability FROM records')
    data = cursor.fetchall()
    conn.close()
    return data
"""



import sqlite3
from datetime import datetime

def init_db():
    # 创建数据库文件（如果没有的话）
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # 创建表格（添加event_type字段标记事件类型）
    cursor.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        violent_probability REAL NOT NULL,
        non_violent_probability REAL NOT NULL,
        timestamp DATETIME NOT NULL,
        device_id TEXT NOT NULL,
        event_type TEXT NOT NULL -- 添加事件类型字段，暴力/非暴力
    )''')

    conn.commit()
    conn.close()

def insert_record(filename, violent_probability, non_violent_probability, device_id, event_type):
    """将记录插入数据库"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # 插入数据到数据库
    cursor.execute('''INSERT INTO records (filename, violent_probability, non_violent_probability, timestamp, device_id, event_type)
                      VALUES (?, ?, ?, ?, ?, ?)''', 
                   (filename, violent_probability, non_violent_probability, timestamp, device_id, event_type))
    
    conn.commit()
    conn.close()

def get_daily_records():
    """获取每天的暴力事件预测数据"""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # 获取按日期分组的记录，计算平均暴力和非暴力概率
    cursor.execute('''SELECT strftime('%Y-%m-%d', timestamp) AS date, 
                             AVG(violent_probability) AS avg_violent_prob,
                             AVG(non_violent_probability) AS avg_non_violent_prob
                      FROM records
                      GROUP BY date
                      ORDER BY date ASC''')
    records = cursor.fetchall()
    conn.close()
    return records

def get_heatmap_data():
    """获取用于日历热力图的数据"""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # 获取所有记录的暴力概率（以日期为单位，方便前端生成热力图）
    cursor.execute('''SELECT strftime('%Y-%m-%d', timestamp) AS date, 
                             AVG(violent_probability) AS avg_violent_prob
                      FROM records
                      GROUP BY date''')
    data = cursor.fetchall()
    conn.close()
    return data
