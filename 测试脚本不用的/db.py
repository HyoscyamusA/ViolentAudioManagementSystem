import sqlite3
from datetime import datetime

DATABASE = 'events.db'


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_date DATE NOT NULL,
                        device_id TEXT NOT NULL,
                        violent_probability REAL,
                        non_violent_probability REAL,
                        event_type TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def insert_event(event_date, device_id, violent_probability, non_violent_probability, event_type):
    """将事件信息插入数据库"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO events (event_date, device_id, violent_probability, non_violent_probability, event_type)
                      VALUES (?, ?, ?, ?, ?)''', 
                   (event_date, device_id, violent_probability, non_violent_probability, event_type))
    conn.commit()
    conn.close()

def get_heatmap_data():
    """获取用于热力图的数据"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''SELECT event_date, AVG(violent_probability) AS avg_violent_prob
                      FROM events
                      GROUP BY event_date''')
    data = cursor.fetchall()
    conn.close()
    return data
