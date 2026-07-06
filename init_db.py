import sqlite3
import os

def provision_database():
    # FIX: Ensure the directory exists inside the container volume
    db_dir = '/app/db'
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        
    db_path = os.path.join(db_dir, 'aetherguard.db')
    
    # Connects to the shared container volume path
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("📦 Provisioning AetherGuard Shared Container Tables...")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_policies (
            agent_id TEXT PRIMARY KEY,
            allowed_actions TEXT,
            max_transaction_limit INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            agent_id TEXT,
            action TEXT,
            amount INTEGER,
            status TEXT,
            reason TEXT
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM agent_policies")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO agent_policies (agent_id, allowed_actions, max_transaction_limit)
            VALUES ('procurement_bot_01', 'buy_inventory,check_status,execute_calculation', 10000)
        ''')
        print("🌱 Seeding baseline organizational parameters inside container volume successfully.")
    
    conn.commit()
    conn.close()
    print("✅ Shared Volume Database Ready.")

if __name__ == '__main__':
    provision_database()