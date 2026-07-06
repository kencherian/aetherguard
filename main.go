package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	_ "modernc.org/sqlite" // Pure-Go SQLite configuration driver
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

var db *sql.DB

func main() {
	var err error
	// FIX: Points to the exact volume mount directory shared between all docker containers
	db, err = sql.Open("sqlite", "/app/db/aetherguard.db")
	if err != nil {
		fmt.Printf("Database connection failure: %v\n", err)
		return
	}
	defer db.Close()

	http.HandleFunc("/", proxyHandler)
	port := ":8080"
	fmt.Printf("🔒 [PERSISTENT] AetherGuard Gateway online on port %s...\n", port)
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

	// ---- LIVE SQL IDENTITY & PARAMETER QUERY ----
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

	// Action Check Matching
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

	// Budget Limit Matching
	if payload.Amount > maxLimit {
		logAndReject(w, payload, "BLOCKED", fmt.Sprintf("Budget Violation: Value $%d exceeds limit.", payload.Amount))
		return
	}

	// Deep Sandbox Execution Checking
	if payload.Action == "execute_calculation" && payload.CodePayload != "" {
		isSafe := callPythonSandbox(payload.CodePayload)
		if !isSafe {
			logAndReject(w, payload, "BLOCKED", "Sandbox Exception: Python structural code parser rejected content.")
			return
		}
	}

	// Log a successful verification entry into our ledger
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

	// FIX: Changed host endpoint destination from 'localhost' to 'sandbox_worker' service name
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

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusForbidden)
	json.NewEncoder(w).Encode(map[string]string{"status": "blocked", "reason": reason})
	fmt.Printf("❌ [BLOCK] %s\n", reason)
}

func respondWithError(w http.ResponseWriter, message string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}