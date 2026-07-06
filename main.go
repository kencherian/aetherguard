package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	_ "modernc.org/sqlite" 
)

type AgentPayload struct {
	AgentID     string `json:"agent_id"`
	Action      string `json:"action"`
	Amount      int    `json:"amount"`
	CodePayload string `json:"code_payload"`
}

type SandboxRequest struct {
	CodePayload string `json:"code_payload"`
}

type SandboxResponse struct {
	Status string `json:"status"`
	Reason string `json:"reason"`
}

// SlackWebhookPayload structures the exact payload format Slack requires
type SlackWebhookPayload struct {
	Text string `json:"text"`
}

var db *sql.DB

func main() {
	var err error
	db, err = sql.Open("sqlite", "/app/db/aetherguard.db")
	if err != nil {
		fmt.Printf("Database connection failure: %v\n", err)
		return
	}
	defer db.Close()

	http.HandleFunc("/", proxyHandler)
	port := ":8080"
	fmt.Printf("🔒 [ALERT-READY] AetherGuard Gateway online on port %s...\n", port)
	if err := http.ListenAndServe(port, nil); err != nil {
		fmt.Printf("Engine failure: %v\n", err)
	}
}

func proxyHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		respondWithError(w, "Unable to read payload stream", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var payload AgentPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		respondWithError(w, "Malformed JSON", http.StatusBadRequest)
		return
	}

	fmt.Printf("\n[Database Proxy] Intercepted call from agent: %s\n", payload.AgentID)

	var allowedActionsStr string
	var maxLimit int

	query := "SELECT allowed_actions, max_transaction_limit FROM agent_policies WHERE agent_id = ?"
	err = db.QueryRow(query, payload.AgentID).Scan(&allowedActionsStr, &maxLimit)
	
	if err == sql.ErrNoRows {
		logAndReject(w, payload, "BLOCKED", fmt.Sprintf("Identity Unregistered: '%s'", payload.AgentID))
		return
	} else if err != nil {
		respondWithError(w, "Internal configuration error", http.StatusInternalServerError)
		return
	}

	actionAllowed := false
	actions := strings.Split(allowedActionsStr, ",")
	for _, a := range actions {
		if strings.TrimSpace(a) == payload.Action {
			actionAllowed = true
			break
		}
	}
	if !actionAllowed {
		logAndReject(w, payload, "BLOCKED", fmt.Sprintf("Action Violation: '%s' unauthorized.", payload.Action))
		return
	}

	if payload.Amount > maxLimit {
		logAndReject(w, payload, "BLOCKED", fmt.Sprintf("Budget Violation: Value $%d exceeds limit.", payload.Amount))
		return
	}

	if payload.Action == "execute_calculation" && payload.CodePayload != "" {
		isSafe := callPythonSandbox(payload.CodePayload)
		if !isSafe {
			logAndReject(w, payload, "BLOCKED", "Sandbox Exception: Python structural code parser rejected content.")
			return
		}
	}

	_, _ = db.Exec("INSERT INTO audit_ledger (agent_id, action, amount, status, reason) VALUES (?, ?, ?, ?, ?)",
		payload.AgentID, payload.Action, payload.Amount, "PASSED", "")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "approved"})
	fmt.Println("✅ [PASS] Request verified and committed to historical ledger.")
}

func callPythonSandbox(code string) bool {
	sandboxReq := SandboxRequest{CodePayload: code}
	jsonData, _ := json.Marshal(sandboxReq)

	resp, err := http.Post("http://sandbox_worker:5000/sandbox", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return false
	}
	defer resp.Body.Close()

	var sandboxResp SandboxResponse
	if err := json.NewDecoder(resp.Body).Decode(&sandboxResp); err != nil {
		return false
	}
	return sandboxResp.Status == "approved"
}

func logAndReject(w http.ResponseWriter, payload AgentPayload, status string, reason string) {
	_, err := db.Exec("INSERT INTO audit_ledger (agent_id, action, amount, status, reason) VALUES (?, ?, ?, ?, ?)",
		payload.AgentID, payload.Action, payload.Amount, status, reason)
	if err != nil {
		fmt.Printf("Ledger logging error: %v\n", err)
	}

	// Async dispatch to avoid interceptor performance penalties
	go sendWebhookAlert(payload, reason)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusForbidden)
	json.NewEncoder(w).Encode(map[string]string{"status": "blocked", "reason": reason})
	fmt.Printf("❌ [BLOCK] %s\n", reason)
}

func sendWebhookAlert(payload AgentPayload, reason string) {
	// FIX: Pull the Webhook destination dynamically from the container context
	webhookURL := os.Getenv("SLACK_WEBHOOK_URL")
	if webhookURL == "" {
		fmt.Println("📢 [ALERT SYSTEM] Alert dropped. SLACK_WEBHOOK_URL environment variable is empty.")
		return
	}

	alertText := fmt.Sprintf(
		"🚨 *AetherGuard Security Containment Alert*\n*Timestamp:* %s\n*Agent ID:* `%s`\n*Attempted Action:* `%s`\n*Financial Impact Scope:* $%d\n*Violation Exception:* _%s_",
		time.Now().Format("2006-01-02 15:04:05"),
		payload.AgentID,
		payload.Action,
		payload.Amount,
		reason,
	)

	webhookPayload := SlackWebhookPayload{Text: alertText}
	jsonData, err := json.Marshal(webhookPayload)
	if err != nil {
		return
	}

	resp, err := http.Post(webhookURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		fmt.Printf("⚠️ [ALERT EXCEPTION] Webhook communication failed: %v\n", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		print("📢 [ALERT SYSTEM] Real-time security alert dispatched successfully into Slack.")
	} else {
		fmt.Printf("⚠️ [ALERT SYSTEM] Remote channel responded with error code: %d\n", resp.StatusCode)
	}
}

func respondWithError(w http.ResponseWriter, message string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}