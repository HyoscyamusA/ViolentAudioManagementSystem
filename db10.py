import sqlite3
import random
from datetime import datetime, timedelta

# ================== 数据生成配置 ==================
NUM_ADMINS = 1         # 管理员数量
NUM_USERS = 50         # 普通用户数量
DEVICES_PER_USER = 5   # 每个用户绑定的设备数量
EVENTS_PER_DEVICE = 20 # 每个设备的事件记录数量
# ================================================

def generate_mac():
    """生成唯一MAC地址"""
    return ":".join(["{:02x}".format(random.randint(0x00, 0xff)) for _ in range(6)]).upper()

def generate_device_name():
    """生成符合要求的设备名称"""
    schools = ["第一中学", "实验小学", "科技大学附中", "外国语学校", "实验中学"]
    areas = ["教学A区", "实验楼区域", "操场西侧", "南校区", "图书馆区域"]
    return f"{random.choice(schools)}，{random.choice(areas)}"

def generate_username():
    """生成唯一用户名"""
    prefixes = ["user", "device", "admin", "manager"]
    return f"{random.choice(prefixes)}_{random.randint(1000,9999)}"

def generate_timestamp(start, end):
    """生成随机时间戳（已修复浮点错误）"""
    delta = end - start
    total_seconds = int(delta.total_seconds())  # 转换为整数
    return start + timedelta(seconds=random.randint(0, total_seconds))

def create_test_data(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # 清空现有数据
        c.execute("DELETE FROM events")
        c.execute("DELETE FROM mac_user")
        c.execute("DELETE FROM mac")
        c.execute("DELETE FROM user")
        
        # ========== 生成用户 ==========
        users = []
        # 生成管理员
        c.execute("INSERT INTO user (username, password, role) VALUES (?, ?, ?)",
                 ("admin", "admin123", "admin"))
        users.append({"id": 1, "role": "admin"})
        
        # 生成普通用户
        for i in range(2, NUM_USERS + 2):
            username = generate_username()
            c.execute("INSERT INTO user (username, password, role) VALUES (?, ?, ?)",
                     (username, "123456", "user"))
            users.append({"id": i, "role": "user"})
        
        # ========== 生成设备 ==========
        all_macs = set()
        for user in users:
            if user["role"] == "admin":
                continue  # 管理员不主动绑定设备
            
            # 为每个用户生成独立设备
            for _ in range(DEVICES_PER_USER):
                while True:
                    mac = generate_mac()
                    if mac not in all_macs:
                        all_macs.add(mac)
                        break
                
                # 插入mac表
                c.execute("INSERT INTO mac (mac_address) VALUES (?)", (mac,))
                
                # 插入mac_user表
                device_name = generate_device_name()
                c.execute("""
                    INSERT INTO mac_user (mac_address, device_name, user_id)
                    VALUES (?, ?, ?)
                """, (mac, device_name, user["id"]))
        
        # ========== 生成事件记录 ==========
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2024, 1, 1)
        
        c.execute("SELECT mac_address FROM mac")
        macs = [row[0] for row in c.fetchall()]
        
        for mac in macs:
            for _ in range(EVENTS_PER_DEVICE):
                event_time = generate_timestamp(start_date, end_date)
                c.execute("""
                    INSERT INTO events (mac_address, event_datetime, device_name)
                    VALUES (?, ?, ?)
                """, (
                    mac,
                    event_time.strftime("%Y-%m-%d %H:%M:%S"),
                    generate_device_name()
                ))
        
        conn.commit()
        print(f"成功生成数据：")
        print(f"- 用户：{NUM_USERS+1} 个（1管理员 + {NUM_USERS}普通用户）")
        print(f"- 设备：{len(macs)} 个")
        print(f"- 事件记录：{len(macs)*EVENTS_PER_DEVICE} 条")
        
    except Exception as e:
        conn.rollback()
        print("数据生成失败:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_data("violence_events.db")