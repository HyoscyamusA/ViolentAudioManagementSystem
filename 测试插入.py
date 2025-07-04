import sqlite3

def init_db():
    conn = sqlite3.connect('violence_events.db')
    c = conn.cursor()
    
    # 启用外键约束（关键步骤！）
    c.execute("PRAGMA foreign_keys = ON")

    c.execute('''CREATE TABLE IF NOT EXISTS mac (
                    mac_address TEXT PRIMARY KEY
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS mac_user (
                    mac_address TEXT,
                    device_name TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (mac_address) REFERENCES mac(mac_address) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )''')
    conn.commit()
    conn.close()

def insert_mac_without_user(mac_address):
    conn = sqlite3.connect('violence_events.db')
    c = conn.cursor()
    
    try:
        # 先插入主表（使用 IGNORE 避免重复）
        c.execute("INSERT OR IGNORE INTO mac (mac_address) VALUES (?)", (mac_address,))
        
        # 再插入关联表（确保外键存在）
        c.execute('''INSERT INTO mac_user (mac_address, device_name, user_id)
                     VALUES (?, NULL, NULL)''', (mac_address,))
        
        conn.commit()
        print(f"成功插入 MAC 地址: {mac_address}")
    
    except sqlite3.IntegrityError as e:
        print(f"插入失败: {str(e)} (可能违反外键约束)")
    
    finally:
        conn.close()

# 初始化数据库（如果尚未创建）
init_db()

# 调用函数插入特定 MAC 地址
insert_mac_without_user('e4-5f-01-8a-17-86')