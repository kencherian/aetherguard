import time
import json
import http.client

def fire_attack_vector(description, payload):
    print(f"\n🚀 Launching Attack Vector: {description}")
    print(f"   Payload: {json.dumps(payload)}")
    
    try:
        # Establish a direct socket connection to our Go Gateway Container
        conn = http.client.HTTPConnection("localhost", 8080)
        headers = {"Content-Type": "application/json"}
        
        conn.request("POST", "/", json.dumps(payload), headers)
        response = conn.getresponse()
        data = response.read().decode()
        
        print(f"   Gateway Response Status: {response.status}")
        print(f"   Gateway Body: {data}")
    except Exception as e:
        print(f"   ❌ Network Connectivity Error: {e}")
    finally:
        conn.close()

def run_automated_demo_suite():
    print("=" * 70)
    print("🎯 AETHERGUARD ADVERSARY EXPLOIT DEMO SUITE")
    print("=" * 70)
    print("Simulating a high-risk multi-agent deployment facing active corruption...")
    time.sleep(2)

    # Attack Vector 1: The Identity Spoof Attempt
    fire_attack_vector(
        "Spoofing an unregistered agent persona to hijack microservice paths",
        {"agent_id": "malicious_shadow_bot", "action": "check_status", "amount": 0}
    )
    time.sleep(1.5)

    # Attack Vector 2: The Economic Budget Runaway
    fire_attack_vector(
        "Forcing a procurement validation loop to trigger massive capital leakage",
        {"agent_id": "procurement_bot_01", "action": "buy_inventory", "amount": 950000}
    )
    time.sleep(1.5)

    # Attack Vector 3: Hidden Code Injection Attack
    fire_attack_vector(
        "Injecting an obfuscated shell invocation block through an allowed calculation filter",
        {
            "agent_id": "procurement_bot_01",
            "action": "execute_calculation",
            "amount": 0,
            "code_payload": "import sys; sys.modules['os'].system('cat /etc/passwd')"
        }
    )
    
    print("\n" + "=" * 70)
    print("🏁 AUTOMATED ADVERSARY SIMULATION COMPLETE")
    print("👉 Check your browser dashboard at http://localhost:3000 to view the blocks!")
    print("=" * 70)

if __name__ == '__main__':
    run_automated_demo_suite()