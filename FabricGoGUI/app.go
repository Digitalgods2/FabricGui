package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct holds the application context and configuration
type App struct {
	ctx           context.Context
	baseURL       string
	client        *http.Client
	history       []HistoryEntry
	serverProcess *exec.Cmd
	serverMutex   sync.Mutex
}

// HistoryEntry represents a single history item
type HistoryEntry struct {
	Pattern string `json:"pattern"`
	Model   string `json:"model"`
	Input   string `json:"input"`
	Output  string `json:"output"`
	Time    int64  `json:"time"`
}

// Preferences holds user preferences
type Preferences struct {
	BaseURL         string `json:"baseUrl"`
	Theme           string `json:"theme"`
	AutoStartServer bool   `json:"autoStartServer"`
	LastPattern     string `json:"lastPattern"`
	LastModel       string `json:"lastModel"`
	LastVendor      string `json:"lastVendor"`
}

// ModelsResponse represents the API response for models
type ModelsResponse struct {
	Models  []string            `json:"models"`
	Vendors map[string][]string `json:"vendors"`
}

// ChatRequest represents a chat API request
type ChatRequest struct {
	Prompts []PromptRequest `json:"prompts"`
}

// PromptRequest represents a single prompt in a chat request
type PromptRequest struct {
	UserInput   string `json:"userInput"`
	Vendor      string `json:"vendor"`
	Model       string `json:"model"`
	PatternName string `json:"patternName"`
}

// StreamEvent represents a streamed response event
type StreamEvent struct {
	Type    string `json:"type"`
	Content string `json:"content"`
	Format  string `json:"format,omitempty"`
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{
		baseURL: "http://localhost:8080",
		client: &http.Client{
			Timeout: 0, // No timeout for streaming
		},
		history: []HistoryEntry{},
	}
}

// startup is called when the app starts
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	a.loadPreferences()
}

// shutdown is called when the app is closing - clean up server process
func (a *App) shutdown(ctx context.Context) {
	a.StopServer()
}

// getConfigDir returns the config directory path
func (a *App) getConfigDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	dir := filepath.Join(home, ".fabric_gui_go")
	os.MkdirAll(dir, 0755)
	return dir
}

// SetBaseURL updates the Fabric server base URL
func (a *App) SetBaseURL(url string) {
	a.baseURL = strings.TrimSuffix(url, "/")
}

// GetBaseURL returns the current base URL
func (a *App) GetBaseURL() string {
	return a.baseURL
}

// ============================================
// Server Management
// ============================================

// StartServer starts the Fabric server process
func (a *App) StartServer() error {
	a.serverMutex.Lock()
	defer a.serverMutex.Unlock()

	// Check if already running
	if a.serverProcess != nil && a.serverProcess.Process != nil {
		// Check if process is still alive
		if a.serverProcess.ProcessState == nil {
			return fmt.Errorf("server already running")
		}
	}

	// Find fabric executable
	fabricPath, err := exec.LookPath("fabric")
	if err != nil {
		return fmt.Errorf("fabric not found in PATH: %v", err)
	}

	// Start the server
	cmd := exec.Command(fabricPath, "--serve")

	// Capture output for logging
	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start server: %v", err)
	}

	a.serverProcess = cmd

	// Read output in background
	go func() {
		reader := bufio.NewReader(io.MultiReader(stdout, stderr))
		for {
			line, err := reader.ReadString('\n')
			if err != nil {
				break
			}
			// Emit server log event
			runtime.EventsEmit(a.ctx, "server:log", strings.TrimSpace(line))
		}
	}()

	// Wait a moment for server to start
	time.Sleep(2 * time.Second)

	// Check if it's responding
	if !a.CheckHealth() {
		// Give it more time
		time.Sleep(3 * time.Second)
	}

	runtime.EventsEmit(a.ctx, "server:started", "")
	return nil
}

// StopServer stops the Fabric server process
func (a *App) StopServer() error {
	a.serverMutex.Lock()
	defer a.serverMutex.Unlock()

	if a.serverProcess == nil || a.serverProcess.Process == nil {
		return nil // Already stopped
	}

	// Kill the process
	if err := a.serverProcess.Process.Kill(); err != nil {
		return fmt.Errorf("failed to stop server: %v", err)
	}

	a.serverProcess.Wait()
	a.serverProcess = nil

	runtime.EventsEmit(a.ctx, "server:stopped", "")
	return nil
}

// IsServerRunning checks if the server process is running
func (a *App) IsServerRunning() bool {
	a.serverMutex.Lock()
	defer a.serverMutex.Unlock()

	if a.serverProcess == nil || a.serverProcess.Process == nil {
		return false
	}

	// Check if process is still alive
	return a.serverProcess.ProcessState == nil
}

// SavePreferences saves user preferences to disk
func (a *App) SavePreferences(prefs Preferences) error {
	dir := a.getConfigDir()
	if dir == "" {
		return fmt.Errorf("could not determine config directory")
	}

	a.baseURL = prefs.BaseURL

	data, err := json.MarshalIndent(prefs, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(dir, "preferences.json"), data, 0644)
}

// LoadPreferences loads user preferences from disk
func (a *App) LoadPreferences() (*Preferences, error) {
	return a.loadPreferences()
}

func (a *App) loadPreferences() (*Preferences, error) {
	dir := a.getConfigDir()
	if dir == "" {
		return &Preferences{BaseURL: "http://localhost:8080", Theme: "dark", AutoStartServer: true}, nil
	}

	data, err := os.ReadFile(filepath.Join(dir, "preferences.json"))
	if err != nil {
		return &Preferences{BaseURL: "http://localhost:8080", Theme: "dark", AutoStartServer: true}, nil
	}

	var prefs Preferences
	if err := json.Unmarshal(data, &prefs); err != nil {
		return &Preferences{BaseURL: "http://localhost:8080", Theme: "dark", AutoStartServer: true}, nil
	}

	// Apply loaded preferences
	if prefs.BaseURL != "" {
		a.baseURL = prefs.BaseURL
	}

	return &prefs, nil
}

// CheckHealth checks if the Fabric server is reachable
func (a *App) CheckHealth() bool {
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(a.baseURL + "/patterns/names")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

// GetPatterns fetches the list of available patterns from Fabric
func (a *App) GetPatterns() ([]string, error) {
	resp, err := a.client.Get(a.baseURL + "/patterns/names")
	if err != nil {
		return nil, fmt.Errorf("failed to fetch patterns: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("server returned status %d", resp.StatusCode)
	}

	var patterns []string
	if err := json.NewDecoder(resp.Body).Decode(&patterns); err != nil {
		return nil, fmt.Errorf("failed to parse patterns: %v", err)
	}

	return patterns, nil
}

// GetModels fetches the list of available models grouped by vendor
func (a *App) GetModels() (*ModelsResponse, error) {
	resp, err := a.client.Get(a.baseURL + "/models/names")
	if err != nil {
		return nil, fmt.Errorf("failed to fetch models: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("server returned status %d", resp.StatusCode)
	}

	var models ModelsResponse
	if err := json.NewDecoder(resp.Body).Decode(&models); err != nil {
		return nil, fmt.Errorf("failed to parse models: %v", err)
	}

	return &models, nil
}

// AddHistoryEntry adds an entry to history
func (a *App) AddHistoryEntry(pattern, model, input, output string) {
	entry := HistoryEntry{
		Pattern: pattern,
		Model:   model,
		Input:   input,
		Output:  output,
		Time:    time.Now().Unix(),
	}

	a.history = append(a.history, entry)

	// Keep only last 50 entries
	if len(a.history) > 50 {
		a.history = a.history[len(a.history)-50:]
	}
}

// GetHistory returns the history entries
func (a *App) GetHistory() []HistoryEntry {
	return a.history
}

// GetHistoryCount returns the number of history entries
func (a *App) GetHistoryCount() int {
	return len(a.history)
}

// GetHistoryEntry returns a specific history entry by index
func (a *App) GetHistoryEntry(index int) *HistoryEntry {
	if index < 0 || index >= len(a.history) {
		return nil
	}
	return &a.history[index]
}

// OpenFileDialog opens a file dialog and returns the selected file content
func (a *App) OpenFileDialog() (string, error) {
	selection, err := runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Import Text File",
		Filters: []runtime.FileFilter{
			{DisplayName: "Text Files", Pattern: "*.txt;*.md"},
			{DisplayName: "All Files", Pattern: "*.*"},
		},
	})
	if err != nil {
		return "", err
	}
	if selection == "" {
		return "", nil // User cancelled
	}

	content, err := os.ReadFile(selection)
	if err != nil {
		return "", fmt.Errorf("failed to read file: %v", err)
	}

	return string(content), nil
}

// SaveFileDialog opens a save dialog and saves the content
func (a *App) SaveFileDialog(content string) (string, error) {
	selection, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title:           "Save Output",
		DefaultFilename: "output.md",
		Filters: []runtime.FileFilter{
			{DisplayName: "Markdown", Pattern: "*.md"},
			{DisplayName: "Text Files", Pattern: "*.txt"},
			{DisplayName: "All Files", Pattern: "*.*"},
		},
	})
	if err != nil {
		return "", err
	}
	if selection == "" {
		return "", nil // User cancelled
	}

	err = os.WriteFile(selection, []byte(content), 0644)
	if err != nil {
		return "", fmt.Errorf("failed to save file: %v", err)
	}

	return selection, nil
}

// SendChat sends a chat request and streams the response
func (a *App) SendChat(pattern, vendor, model, input string) error {
	// Build request
	reqBody := ChatRequest{
		Prompts: []PromptRequest{
			{
				UserInput:   input,
				Vendor:      vendor,
				Model:       model,
				PatternName: pattern,
			},
		},
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %v", err)
	}

	req, err := http.NewRequest("POST", a.baseURL+"/chat", strings.NewReader(string(jsonBody)))
	if err != nil {
		return fmt.Errorf("failed to create request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := a.client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("server error %d: %s", resp.StatusCode, string(body))
	}

	// Read streaming response (SSE format: "data: {...json...}")
	// Use Scanner for robust line reading
	scanner := bufio.NewScanner(resp.Body)
	// Increase buffer size just in case (max 1MB lines)
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)

	var fullOutput string

	for scanner.Scan() {
		line := scanner.Text()

		if len(line) > 0 {
			line = strings.TrimSpace(line)
			if line != "" {
				// Strip "data: " prefix
				if strings.HasPrefix(line, "data: ") {
					line = strings.TrimPrefix(line, "data: ")
				} else if strings.HasPrefix(line, "data:") {
					line = strings.TrimPrefix(line, "data:")
				}

				if line != "" {
					var event StreamEvent
					if err := json.Unmarshal([]byte(line), &event); err == nil {
						switch event.Type {
						case "content":
							runtime.EventsEmit(a.ctx, "chat:chunk", event.Content)
							fullOutput += event.Content
						case "complete":
							// Some servers/models might send the final chunk in the complete event
							if event.Content != "" {
								runtime.EventsEmit(a.ctx, "chat:chunk", event.Content)
								fullOutput += event.Content
							}
							runtime.EventsEmit(a.ctx, "chat:complete", "")
							a.AddHistoryEntry(pattern, model, input, fullOutput)
							return nil
						case "usage":
							// ignore usage events
						}
					}
				}
			}
		}
	}

	if err := scanner.Err(); err != nil {
		return fmt.Errorf("error reading stream: %v", err)
	}

	a.AddHistoryEntry(pattern, model, input, fullOutput)
	runtime.EventsEmit(a.ctx, "chat:complete", "")
	return nil
}
