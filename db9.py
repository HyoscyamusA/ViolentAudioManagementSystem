import sqlite3
import random
from datetime import datetime, timedelta

def generate_mac():
    """生成随机的MAC地址"""
    return ":".join(["{:02x}".format(random.randint(0x00, 0xff)) for _ in range(6)]).upper()

def generate_device_name():
    """生成符合要求的设备名称"""
    schools = [
        "第一中学", "实验小学", "科技大学附中",
        "外国语学校", "实验中学", "师范附小",
        "育才学校", "朝阳小学", "第九中学"
    ]
    
    areas = [
        "教学A区", "实验楼区域", "操场西侧",
        "南校区", "图书馆区域", "食堂周边",
        "宿舍楼区域", "体育馆周边", "东校区"
    ]
    
    return f"{random.choice(schools)}，{random.choice(areas)}"

def generate_timestamp(start_date, end_date):
    """生成随机时间戳（修复浮点数问题）"""
    delta = end_date - start_date
    total_seconds = int(delta.total_seconds())  # 转换为整数
    random_seconds = random.randint(0, total_seconds)
    return start_date + timedelta(seconds=random_seconds)

def create_test_data(db_path, num_devices=100, records_per_device=100):
    # 连接数据库
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # 清空现有数据
        c.execute("DELETE FROM events")
        c.execute("DELETE FROM mac_user")
        c.execute("DELETE FROM mac")
        
        # 创建测试设备
        devices = []
        for _ in range(num_devices):
            mac = generate_mac()
            device_name = generate_device_name()
            
            # 插入mac表
            c.execute("INSERT INTO mac (mac_address) VALUES (?)", (mac,))
            
            # 插入mac_user表（假设用户ID 1为管理员）
            c.execute("""
                INSERT INTO mac_user (mac_address, device_name, user_id)
                VALUES (?, ?, 1)
            """, (mac, device_name))
            
            devices.append(mac)
        
        # 创建事件记录（时间范围调整为2023全年）
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2024, 1, 1)
        
        for mac in devices:
            for _ in range(records_per_device):
                event_time = generate_timestamp(start_date, end_date)
                c.execute("""
                    INSERT INTO events (mac_address, event_datetime, device_name)
                    VALUES (?, ?, ?)
                """, (
                    mac,
                    event_time.strftime("%Y-%m-%d %H:%M:%S"),
                    generate_device_name()  # 设备名称随机生成
                ))
        
        conn.commit()
        print(f"成功插入数据：{num_devices}个设备，{num_devices*records_per_device}条记录")
    
    except Exception as e:
        conn.rollback()
        print("数据插入失败:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_data("violence_events.db")