import sqlite3
import random
from datetime import datetime, timedelta

def generate_timestamp(start, end):
    """生成指定时间范围内的随机时间戳"""
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def insert_events_except_target(db_path, exclude_mac, events_per_device=20):
    """为除指定MAC外的设备生成事件记录"""
    conn = sqlite3.connect(db_path)
    
    try:
        # 获取所有MAC地址（自动统一为大写格式）
        cursor = conn.execute("SELECT UPPER(mac_address) FROM mac")
        all_macs = [row[0] for row in cursor.fetchall()]
        
        # 过滤排除设备（统一处理大小写）
        exclude_mac_upper = exclude_mac.upper()
        filtered_macs = [mac for mac in all_macs if mac != exclude_mac_upper]
        
        if not filtered_macs:
            print("没有符合条件的设备需要插入事件")
            return

        # 生成时间范围
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2024, 1, 1)
        
        # 准备插入数据
        events_data = []
        for mac in filtered_macs:
            for _ in range(events_per_device):
                event_time = generate_timestamp(start_date, end_date)
                events_data.append((
                    mac,
                    event_time.strftime("%Y-%m-%d %H:%M:%S")
                ))
        
        # 批量插入数据库
        conn.executemany("""
            INSERT INTO events (mac_address, event_datetime)
            VALUES (?, ?)
        """, events_data)
        
        conn.commit()
        print(f"成功插入 {len(events_data)} 条事件记录")
        print(f"- 排除设备: {exclude_mac}")
        print(f"- 目标设备数: {len(filtered_macs)}")
        print(f"- 每个设备插入数: {events_per_device}")

    except Exception as e:
        conn.rollback()
        print(f"操作失败: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    # 使用示例
    insert_events_except_target(
        db_path="violence_events.db",
        exclude_mac="e4-5f-01-8a-17-86",  # 支持任意大小写格式
        events_per_device=20
    )