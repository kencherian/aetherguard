import sqlite3
from datetime import datetime

def generate_security_report():
    # Establish a connection to our shared enterprise database file
    conn = sqlite3.connect('aetherguard.db')
    cursor = conn.cursor()

    print("\n" + "="*70)
    print(f"🔒 AETHERGUARD COMPLIANCE & AUDIT REPORT  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # 1. Pull Overall Metric Aggregations
    cursor.execute("SELECT COUNT(*) FROM audit_ledger")
    total_transactions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_ledger WHERE status = 'PASSED'")
    passed_transactions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_ledger WHERE status = 'BLOCKED'")
    blocked_violations = cursor.fetchone()[0]

    print(f"📈 TELEMETRY OVERVIEW:")
    print(f"   Processed Transactions: {total_transactions}")
    print(f"   Cleared Guardrails:     {passed_transactions} ✅")
    print(f"   Containment Blocks:     {blocked_violations} ❌")
    print("-"*70)

    # 2. Extract and Format Recent Incidents Ledger
    print("📋 RECENT LEDGER ENTRIES:")
    cursor.execute("SELECT id, timestamp, agent_id, action, amount, status, reason FROM audit_ledger ORDER BY id DESC LIMIT 10")
    records = cursor.fetchall()

    if not records:
        print("   No transactions recorded in ledger yet.")
    else:
        for row in records:
            rec_id, ts, agent, action, amt, status, reason = row
            status_indicator = "✅ [PASS]" if status == "PASSED" else "❌ [BLOCK]"
            
            print(f" [{rec_id}] {ts} - {status_indicator} Agent: {agent} | Action: {action}")
            if amt > 0:
                print(f"       Financial Scope: ${amt}")
            if reason:
                print(f"       Violation Logged: {reason}")
            print("-" * 50)

    conn.close()

if __name__ == '__main__':
    generate_security_report()