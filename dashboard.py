import sqlite3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class DashboardHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            
            # Fetch the data from the local SQLite database
            metrics, logs = self.fetch_database_state()
            
            # Formulate the dashboard interface with HTML and embedded CSS
            html_content = self.render_html(metrics, logs)
            self.wfile.write(html_content.encode('utf-8'))

    def fetch_database_state(self):
        conn = sqlite3.connect('/app/db/aetherguard.db')
        cursor = conn.cursor()
        
        # 1. Fetch metrics counters
        cursor.execute("SELECT COUNT(*) FROM audit_ledger")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM audit_ledger WHERE status = 'PASSED'")
        passed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM audit_ledger WHERE status = 'BLOCKED'")
        blocked = cursor.fetchone()[0]
        
        # 2. Fetch the last 10 security logs
        cursor.execute("SELECT id, timestamp, agent_id, action, amount, status, reason FROM audit_ledger ORDER BY id DESC LIMIT 10")
        logs = cursor.fetchall()
        
        conn.close()
        return {"total": total, "passed": passed, "blocked": blocked}, logs

    def render_html(self, metrics, logs):
        # Base UI layout design
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AetherGuard Enterprise Console</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f1f5f9; margin: 0; padding: 30px; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 30px; }}
                h1 {{ color: #38bdf8; margin: 0; font-size: 28px; }}
                .badge {{ background-color: #1e293b; padding: 6px 12px; border-radius: 20px; font-size: 14px; border: 1px solid #475569; color: #94a3b8; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 40px; }}
                .metric-card {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
                .metric-title {{ font-size: 14px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }}
                .metric-value {{ font-size: 36px; font-weight: bold; margin-top: 10px; }}
                .text-blue {{ color: #38bdf8; }}
                .text-green {{ color: #10b981; }}
                .text-red {{ color: #f43f5e; }}
                .table-container {{ background: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; }}
                .table-title {{ padding: 20px; font-size: 18px; font-weight: bold; border-bottom: 1px solid #334155; background: #1e293b; }}
                table {{ width: 100%; border-collapse: collapse; text-align: left; }}
                th {{ background: #0f172a; padding: 15px 20px; font-size: 14px; color: #94a3b8; text-transform: uppercase; }}
                td {{ padding: 15px 20px; border-bottom: 1px solid #334155; font-size: 15px; }}
                tr:last-child td {{ border-bottom: none; }}
                .status-pass {{ color: #10b981; font-weight: bold; background: rgba(16,185,129,0.1); padding: 4px 8px; border-radius: 6px; }}
                .status-block {{ color: #f43f5e; font-weight: bold; background: rgba(244,63,94,0.1); padding: 4px 8px; border-radius: 6px; }}
                .reason-text {{ color: #94a3b8; font-size: 13px; font-style: italic; display: block; margin-top: 4px; }}
            </style>
            <script>setTimeout(function() {{ location.reload(); }}, 2500);</script>
        </head>
        <body>
            <div class="container">
                <header>
                    <div>
                        <h1>🔒 AetherGuard Security Core</h1>
                        <p style="margin: 5px 0 0 0; color: #94a3b8;">Deterministic Agent Containment & Semantic Compliance Gateway</p>
                    </div>
                    <div class="badge">Engine Status: Hybrid Core Active</div>
                </header>

                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-title">Total Interceptions</div>
                        <div class="metric-value text-blue">{metrics['total']}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Cleared Guardrails</div>
                        <div class="metric-value text-green">{metrics['passed']}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Containment Blocks</div>
                        <div class="metric-value text-red">{metrics['blocked']}</div>
                    </div>
                </div>

                <div class="table-container">
                    <div class="table-title">Real-Time Security Audit Ledger</div>
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Agent ID</th>
                                <th>Requested Action</th>
                                <th>Scope / Budget</th>
                                <th>Security Decision</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        if not logs:
            html += "<tr><td colspan='5' style='text-align:center; color:#94a3b8; font-style:italic;'>No transaction streams audited yet.</td></tr>"
        else:
            for row in logs:
                rec_id, ts, agent, action, amt, status, reason = row
                status_style = "status-pass" if status == "PASSED" else "status-block"
                status_label = "APPROVED" if status == "PASSED" else "BLOCKED"
                amount_display = f"${amt}" if amt > 0 else "N/A"
                reason_html = f"<span class='reason-text'>⚠️ {reason}</span>" if reason else ""
                
                html += f"""
                <tr>
                    <td style="color: #94a3b8;">{ts}</td>
                    <td style="font-weight: 500;">{agent}</td>
                    <td><code>{action}</code></td>
                    <td>{amount_display}</td>
                    <td>
                        <span class="{status_style}">{status_label}</span>
                        {reason_html}
                    </td>
                </tr>
                """
                
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
        """
        return html

def run_dashboard(port=3000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"🖥️  [UI] AetherGuard Web Console live at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard.")
        httpd.server_close()

if __name__ == '__main__':
    run_dashboard()