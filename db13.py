import sqlite3
import random
from datetime import datetime, timedelta

# ================== 配置参数 ==================
NUM_USERS = 10         # 普通用户数量
DEVICES_PER_USER = 5   # 每个用户绑定的设备数量
BASE_EVENTS = 20       # 普通设备事件数 
HOT_DEVICE_EVENTS = 80 # 高频设备事件数
HOT_DEVICE_COUNT = 3   # 高频设备数量
# =============================================

def generate_mac():
    """生成唯一MAC地址"""
    return ":".join(f"{random.randint(0x00, 0xff):02x}" for _ in range(6)).upper()

def generate_device_name():
    """生成设备名称"""
    schools = ["第一中学", "实验小学", "科技大学附中"]
    areas = ["教学A区", "实验楼区域", "操场西侧"]
    return f"{random.choice(schools)}，{random.choice(areas)}"

def generate_timestamp(start, end):
    """生成随机时间戳"""
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def create_test_data(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # 清空测试数据（保留管理员）
        c.execute("DELETE FROM events")
        c.execute("DELETE FROM mac_user")
        c.execute("DELETE FROM mac")
        c.execute("DELETE FROM user WHERE role != 'admin'")

        # ========== 用户生成 ==========
        users = []
        # 创建普通用户（10个）
        for _ in range(NUM_USERS):
            username = f"user_{random.randint(1000,9999)}"
            c.execute("""
                INSERT INTO user (username, password, role)
                VALUES (?, ?, 'user')
            """, (username, "123456"))
            users.append(c.lastrowid)

        # ========== 设备绑定 ==========
        all_macs = []
        for user_id in users:
            for _ in range(DEVICES_PER_USER):
                # 生成唯一MAC
                while True:
                    mac = generate_mac()
                    if mac not in all_macs:
                        all_macs.append(mac)
                        break
                
                # 插入设备表
                c.execute("INSERT INTO mac (mac_address) VALUES (?)", (mac,))
                
                # 绑定到用户
                c.execute("""
                    INSERT INTO mac_user (mac_address, device_name, user_id)
                    VALUES (?, ?, ?)
                """, (mac, generate_device_name(), user_id))

        # ========== 特殊标记高频设备 ==========
        hot_devices = random.sample(all_macs, HOT_DEVICE_COUNT)
        print(f"[高频设备]：{hot_devices}")

        # ========== 生成事件记录 ==========
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2024, 1, 1)
        
        events_data = []
        for mac in all_macs:
            # 高频设备生成更多事件
            event_count = HOT_DEVICE_EVENTS if mac in hot_devices else BASE_EVENTS
            for _ in range(event_count):
                event_time = generate_timestamp(start_date, end_date)
                events_data.append((
                    mac,
                    event_time.strftime("%Y-%m-%d %H:%M:%S")
                ))
        
        c.executemany("""
            INSERT INTO events (mac_address, event_datetime)
            VALUES (?, ?)
        """, events_data)

        conn.commit()
        print(f"[成功] 生成测试数据：")
        print(f"- 用户：{NUM_USERS} 普通用户 + 1 管理员")
        print(f"- 设备：{len(all_macs)} 个（含{HOT_DEVICE_COUNT}个高频设备）")
        print(f"- 总事件记录：{len(events_data)} 条")
        print(f"- 高频设备事件：{HOT_DEVICE_EVENTS} 条/设备")
        print(f"- 普通设备事件：{BASE_EVENTS} 条/设备")

    except Exception as e:
        conn.rollback()
        print(f"[错误] 数据生成失败：{str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_data("violence_events.db")