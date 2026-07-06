import json
import ast
from http.server import BaseHTTPRequestHandler, HTTPServer

class SandboxWorkerHandler(BaseHTTPRequestHandler):
    
    def do_POST(self):
        if self.path == "/sandbox":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                code_payload = data.get("code_payload", "")
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            print(f"\n[Python Worker] Analyzing incoming code payload...")
            is_safe = self.evaluate_ast(code_payload)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            if is_safe:
                print("✅ [Worker Result] Code pattern verified as safe.")
                response = {"status": "approved"}
            else:
                print("❌ [Worker Result] Vulnerability pattern identified! Blocking thread.")
                response = {"status": "blocked", "reason": "Blacklisted system call execution attempted."}
                
            self.wfile.write(json.dumps(response).encode('utf-8'))

    def evaluate_ast(self, code_string):
        try:
            parsed_tree = ast.parse(code_string)
            for node in ast.walk(parsed_tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    # Flag dangerous low-level file or command interventions
                    if node.func.id in ["eval", "exec", "open", "import", "os", "sys"]:
                        print(f"   [VIOLATION DETECTED] Forbidden keyword call: '{node.func.id}'")
                        return False
            return True
        except Exception as e:
            print(f"   [COMPILE ERROR] Token pattern syntax invalid: {e}")
            return False

def run_worker(port=5000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, SandboxWorkerHandler)
    print(f"🐍 [WORKER] Python AST Security Sandbox listening on port {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    from init_db import provision_database
    try:
        provision_database()
    except Exception as e:
        print(f"Database setup skipped or failed: {e}")
        
    run_worker()