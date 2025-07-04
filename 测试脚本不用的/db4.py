# generate_test_data.py
import sqlite3
import random
from datetime import datetime, timedelta

def generate_test_data():
    # 数据库配置
    DATABASE = 'events.db'
    device_id = "device_4"  # 固定测试设备ID
    device_name = "测试区域A"  # 设备名称
    
    # 连接数据库
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 生成全年日期范围（示例使用2023年）
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)
    
    current_date = start_date
    while current_date <= end_date:
        # 生成随机事件数（制造明显差异）
        event_count = random.choice([
            random.randint(0, 5),    # 30%概率小值
            random.randint(10, 30),   # 50%概率中等值
            random.randint(40, 100)   # 20%概率高峰值
        ])

        # 插入测试数据
        cursor.execute('''
            INSERT INTO events (event_date, device_id, device_name, event_count)
            VALUES (?, ?, ?, ?)
        ''', (
            current_date.strftime('%Y-%m-%d'),
            device_id,
            device_name,
            event_count
        ))

        # 每月最后一天增加高峰
        if (current_date + timedelta(days=1)).month != current_date.month:
            cursor.execute('''
                UPDATE events 
                SET event_count = ? 
                WHERE event_date = ? AND device_id = ?
            ''', (
                random.randint(80, 120),
                current_date.strftime('%Y-%m-%d'),
                device_id
            ))

        current_date += timedelta(days=1)

    conn.commit()
    conn.close()
    print(f"已成功生成{device_id}全年测试数据")

if __name__ == '__main__':
    generate_test_data()