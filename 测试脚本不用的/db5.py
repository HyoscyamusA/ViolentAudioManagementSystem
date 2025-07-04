import sqlite3
from datetime import datetime, timedelta
import random

DATABASE = 'events.db'

def insert_test_data():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 清空表数据（可选）
    cursor.execute("DELETE FROM events")
    cursor.execute("DELETE FROM audio_files")
    conn.commit()

    device_ids = ['Device_A', 'Device_B', 'Device_C']
    device_names = {'Device_A': '区域1', 'Device_B': '区域2', 'Device_C': '区域3'}
    
    # 生成事件数据（最近30天，每个设备随机生成事件）
    for i in range(30):
        for device_id in device_ids:
            if random.random() < 0.7:  # 70% 可能性发生事件
                timestamp = datetime.now() - timedelta(days=i, hours=random.randint(0, 23), minutes=random.randint(0, 59))
                cursor.execute('''INSERT INTO events (timestamp, device_id, device_name) 
                                  VALUES (?, ?, ?)''', (timestamp, device_id, device_names[device_id]))
    
    # 生成音频文件数据
    for i in range(50):
        device_id = random.choice(device_ids)
        filename = f"audio_{i}.wav"
        filepath = f"uploads/{filename}"
        upload_time = datetime.now() - timedelta(days=random.randint(0, 30))
        violent_prob = round(random.uniform(0.3, 0.9), 2)
        non_violent_prob = 1.0 - violent_prob
        cursor.execute('''INSERT INTO audio_files 
                          (filename, filepath, upload_time, device_id, violent_prob, non_violent_prob)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (filename, filepath, upload_time, device_id, violent_prob, non_violent_prob))
    
    conn.commit()
    conn.close()
    print("测试数据插入完成！")

if __name__ == '__main__':
    insert_test_data()