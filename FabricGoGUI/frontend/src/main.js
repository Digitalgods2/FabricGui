// Fabric GUI - Frontend Logic
// Communicates with Go backend via Wails bindings

import {
    GetPatterns, GetModels, SendChat, CheckHealth, GetBaseURL, SetBaseURL,
    OpenFileDialog, SaveFileDialog, AddHistoryEntry, GetHistoryCount, GetHistoryEntry,
    SavePreferences, LoadPreferences, StartServer, StopServer, IsServerRunning
} from '../wailsjs/go/main/App.js';
import { EventsOn } from '../wailsjs/runtime/runtime.js';

// ============================================
// State
// ============================================
const state = {
    patterns: [],
    models: {},
    selectedPattern: '',
    selectedModel: '',
    selectedVendor: '',
    isProcessing: false,
    serverOnline: false,
    serverStarting: false,
    theme: 'dark',
    historyIndex: -1,
    historyCount: 0,
    currentOutput: '',
};

// ============================================
// DOM Elements
// ============================================
const elements = {
    // Status
    serverStatus: document.getElementById('serverStatus'),
    statusLed: document.getElementById('statusLed'),
    statusText: document.getElementById('statusText'),

    // Pattern
    patternSearch: document.getElementById('patternSearch'),
    patternSelect: document.getElementById('patternSelect'),

    // Model
    modelSelect: document.getElementById('modelSelect'),

    // Preview
    commandPreview: document.getElementById('commandPreview'),

    // I/O
    inputText: document.getElementById('inputText'),
    outputText: document.getElementById('outputText'),

    // Buttons
    sendBtn: document.getElementById('sendBtn'),
    cancelBtn: document.getElementById('cancelBtn'),
    copyBtn: document.getElementById('copyBtn'),
    clearInputBtn: document.getElementById('clearInputBtn'),
    clearOutputBtn: document.getElementById('clearOutputBtn'),
    pasteBtn: document.getElementById('pasteBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
    importBtn: document.getElementById('importBtn'),
    saveBtn: document.getElementById('saveBtn'),

    // History
    historyPrevBtn: document.getElementById('historyPrevBtn'),
    historyNextBtn: document.getElementById('historyNextBtn'),
    historyCount: document.getElementById('historyCount'),

    // Settings Modal
    settingsModal: document.getElementById('settingsModal'),
    baseUrlInput: document.getElementById('baseUrlInput'),
    testConnectionBtn: document.getElementById('testConnectionBtn'),
    connectionResult: document.getElementById('connectionResult'),
    saveSettingsBtn: document.getElementById('saveSettingsBtn'),
    cancelSettingsBtn: document.getElementById('cancelSettingsBtn'),
    closeSettingsBtn: document.getElementById('closeSettingsBtn'),

    // Loading
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText'),

    // Theme
    themeToggle: document.getElementById('themeToggle'),

    // Toast
    toastContainer: document.getElementById('toastContainer'),
};

// ============================================
// Initialization
// ============================================
async function init() {
    console.log('Fabric GUI initializing...');

    // Load preferences (includes theme)
    await loadPreferences();

    // Initialize theme
    initTheme();

    // Check server status
    await checkServerStatus();

    // Load data if server is online
    if (state.serverOnline) {
        await loadPatterns();
        await loadModels();
    }

    // Update history display
    await updateHistoryDisplay();

    // Set up event listeners
    setupEventListeners();

    // Set up Wails events for streaming
    setupWailsEvents();

    // Start periodic health check
    setInterval(checkServerStatus, 5000);

    console.log('Fabric GUI initialized');
}

// ============================================
// Preferences
// ============================================
async function loadPreferences() {
    try {
        const prefs = await LoadPreferences();
        if (prefs) {
            if (prefs.baseUrl) {
                elements.baseUrlInput.value = prefs.baseUrl;
            }
            if (prefs.theme) {
                state.theme = prefs.theme;
            }
            // Restore last used pattern/model
            if (prefs.lastPattern) {
                state.selectedPattern = prefs.lastPattern;
            }
            if (prefs.lastModel) {
                state.selectedModel = prefs.lastModel;
            }
            if (prefs.lastVendor) {
                state.selectedVendor = prefs.lastVendor;
            }
        }
    } catch (e) {
        console.error('Failed to load preferences:', e);
    }
}

async function savePreferences() {
    try {
        await SavePreferences({
            baseUrl: elements.baseUrlInput.value,
            theme: state.theme,
            lastPattern: state.selectedPattern,
            lastModel: state.selectedModel,
            lastVendor: state.selectedVendor,
        });
    } catch (e) {
        console.error('Failed to save preferences:', e);
    }
}

// ============================================
// Server Status
// ============================================
async function checkServerStatus() {
    try {
        const isOnline = await CheckHealth();
        updateServerStatus(isOnline);

        // Load data if server just came online
        if (isOnline && !state.serverOnline) {
            await loadPatterns();
            await loadModels();
            showToast('Connected to Fabric server', 'success');
        }

        state.serverOnline = isOnline;
    } catch (e) {
        updateServerStatus(false);
        state.serverOnline = false;
    }
}

function updateServerStatus(isOnline) {
    elements.statusLed.classList.toggle('online', isOnline);
    elements.statusLed.classList.toggle('offline', !isOnline);
    elements.statusText.textContent = isOnline ? 'Connected' : 'Click to Start';
    elements.serverStatus.classList.toggle('starting', state.serverStarting);
}

// Toggle server on/off
async function toggleServer() {
    if (state.serverStarting) return;

    if (state.serverOnline) {
        // Stop the server
        try {
            await StopServer();
            showToast('Server stopped', 'info');
            state.serverOnline = false;
            updateServerStatus(false);
        } catch (e) {
            showToast(`Failed to stop server: ${e}`, 'error');
        }
    } else {
        // Start the server
        state.serverStarting = true;
        elements.statusText.textContent = 'Starting...';
        elements.serverStatus.classList.add('starting');
        showToast('Starting Fabric server...', 'info');

        try {
            await StartServer();
            // Wait a moment and check health
            await new Promise(r => setTimeout(r, 2000));
            const isOnline = await CheckHealth();

            if (isOnline) {
                state.serverOnline = true;
                showToast('Server started successfully!', 'success');
                await loadPatterns();
                await loadModels();
            } else {
                showToast('Server started but not responding yet. Checking...', 'warning');
                // Keep checking
                await new Promise(r => setTimeout(r, 3000));
                const retryOnline = await CheckHealth();
                if (retryOnline) {
                    state.serverOnline = true;
                    showToast('Server is now ready!', 'success');
                    await loadPatterns();
                    await loadModels();
                }
            }
            updateServerStatus(state.serverOnline);
        } catch (e) {
            showToast(`Failed to start server: ${e}`, 'error');
        } finally {
            state.serverStarting = false;
            elements.serverStatus.classList.remove('starting');
        }
    }
}

// ============================================
// Theme Management
// ============================================
function initTheme() {
    // Check localStorage first (overrides preferences)
    const savedTheme = localStorage.getItem('fabric-gui-theme');

    if (savedTheme) {
        state.theme = savedTheme;
    } else if (!state.theme) {
        // Check system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        state.theme = prefersDark ? 'dark' : 'light';
    }

    applyTheme(state.theme);
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(state.theme);
    localStorage.setItem('fabric-gui-theme', state.theme);
    savePreferences();
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

// ============================================
// Load Data
// ============================================
async function loadPatterns() {
    try {
        const patterns = await GetPatterns();
        state.patterns = patterns || [];
        renderPatterns(state.patterns);
        restorePatternSelection();
    } catch (e) {
        console.error('Failed to load patterns:', e);
        elements.patternSelect.innerHTML = '<option disabled>Failed to load patterns</option>';
    }
}

async function loadModels() {
    try {
        const response = await GetModels();
        state.models = response?.vendors || {};
        renderModels(state.models);
        restoreModelSelection();
    } catch (e) {
        console.error('Failed to load models:', e);
        elements.modelSelect.innerHTML = '<option disabled>Failed to load models</option>';
    }
}

function renderPatterns(patterns) {
    elements.patternSelect.innerHTML = '';

    if (!patterns || patterns.length === 0) {
        elements.patternSelect.innerHTML = '<option disabled>No patterns available</option>';
        return;
    }

    patterns.forEach(pattern => {
        const option = document.createElement('option');
        option.value = pattern;
        option.textContent = pattern;
        elements.patternSelect.appendChild(option);
    });
}

function renderModels(vendors) {
    elements.modelSelect.innerHTML = '';

    if (!vendors || Object.keys(vendors).length === 0) {
        elements.modelSelect.innerHTML = '<option disabled>No models available</option>';
        return;
    }

    for (const [vendor, models] of Object.entries(vendors)) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = vendor.toUpperCase();

        models.forEach(model => {
            const option = document.createElement('option');
            option.value = `${vendor}:${model}`;
            option.textContent = model;
            optgroup.appendChild(option);
        });

        elements.modelSelect.appendChild(optgroup);
    }
}

// ============================================
// Pattern Search
// ============================================
function filterPatterns(query) {
    const filtered = state.patterns.filter(p =>
        p.toLowerCase().includes(query.toLowerCase())
    );
    renderPatterns(filtered);
}

// ============================================
// Restore Saved Selections
// ============================================
function restorePatternSelection() {
    if (state.selectedPattern) {
        const options = elements.patternSelect.options;
        for (let i = 0; i < options.length; i++) {
            if (options[i].value === state.selectedPattern) {
                elements.patternSelect.selectedIndex = i;
                updateCommandPreview();
                break;
            }
        }
    }
}

function restoreModelSelection() {
    if (state.selectedVendor && state.selectedModel) {
        const value = `${state.selectedVendor}:${state.selectedModel}`;
        const options = elements.modelSelect.options;
        for (let i = 0; i < options.length; i++) {
            if (options[i].value === value) {
                elements.modelSelect.selectedIndex = i;
                updateCommandPreview();
                break;
            }
        }
    }
}

// ============================================
// Command Preview
// ============================================
// ============================================
// Command Preview
// ============================================
function updateCommandPreview() {
    const pattern = state.selectedPattern || '[pattern]';
    const model = state.selectedModel || '[model]';

    // Simulate input piping for display
    let inputPreview = '';
    if (elements.inputText && elements.inputText.value) {
        inputPreview = 'echo "..." | ';
    }

    elements.commandPreview.textContent = `${inputPreview}fabric --pattern ${pattern} --model ${model}`;
}

// ============================================
// History Management
// ============================================
async function updateHistoryDisplay() {
    try {
        state.historyCount = await GetHistoryCount();
        elements.historyCount.textContent = state.historyCount > 0
            ? `${state.historyIndex + 1}/${state.historyCount}`
            : '0/0';

        // Update button states
        elements.historyPrevBtn.disabled = state.historyIndex <= 0;
        elements.historyNextBtn.disabled = state.historyIndex >= state.historyCount - 1 || state.historyCount === 0;
    } catch (e) {
        console.error('Failed to update history:', e);
    }
}

async function navigateHistory(direction) {
    const newIndex = state.historyIndex + direction;

    if (newIndex < 0 || newIndex >= state.historyCount) return;

    try {
        const entry = await GetHistoryEntry(newIndex);
        if (entry) {
            state.historyIndex = newIndex;

            // Load the entry
            state.selectedPattern = entry.pattern;
            elements.inputText.value = entry.input;
            elements.outputText.textContent = entry.output;

            // Update pattern selection
            const patternOptions = elements.patternSelect.options;
            for (let i = 0; i < patternOptions.length; i++) {
                if (patternOptions[i].value === entry.pattern) {
                    elements.patternSelect.selectedIndex = i;
                    break;
                }
            }

            updateCommandPreview();
            await updateHistoryDisplay();
            showToast(`Loaded history entry ${newIndex + 1}`, 'info');
        }
    } catch (e) {
        console.error('Failed to navigate history:', e);
    }
}

// ============================================
// File Operations
// ============================================
async function importFile() {
    try {
        const content = await OpenFileDialog();
        if (content) {
            elements.inputText.value = content;
            updateCommandPreview();
            showToast('File imported successfully', 'success');
        }
    } catch (e) {
        showToast(`Failed to import: ${e}`, 'error');
    }
}

async function saveOutput() {
    const content = elements.outputText.textContent;
    if (!content) {
        showToast('No output to save', 'warning');
        return;
    }

    try {
        const path = await SaveFileDialog(content);
        if (path) {
            showToast('Output saved successfully', 'success');
        }
    } catch (e) {
        showToast(`Failed to save: ${e}`, 'error');
    }
}

// ============================================
// Send Request
// ============================================
async function sendRequest() {
    const input = elements.inputText.value.trim();

    if (!input) {
        showToast('Please enter some text', 'warning');
        return;
    }

    if (!state.selectedPattern) {
        showToast('Please select a pattern', 'warning');
        return;
    }

    if (!state.selectedModel) {
        showToast('Please select a model', 'warning');
        return;
    }

    if (!state.serverOnline) {
        showToast('Server is offline', 'error');
        return;
    }

    // Set processing state
    const command = `echo "..." | fabric --pattern ${state.selectedPattern} --model ${state.selectedModel}`;
    elements.loadingText.textContent = command;
    setProcessingState(true);
    elements.outputText.textContent = '';
    state.currentOutput = '';

    try {
        await SendChat(state.selectedPattern, state.selectedVendor, state.selectedModel, input);
    } catch (e) {
        console.error('Send failed:', e);
        elements.outputText.textContent = `Error: ${e}`;
        showToast('Request failed', 'error');
    } finally {
        setProcessingState(false);
    }
}

function setProcessingState(processing) {
    state.isProcessing = processing;
    elements.sendBtn.disabled = processing;
    elements.sendBtn.classList.toggle('hidden', processing);
    elements.cancelBtn.classList.toggle('hidden', !processing);
    elements.loadingOverlay.classList.toggle('hidden', !processing);
}

// ============================================
// Wails Events (Streaming)
// ============================================
let eventsInitialized = false;

function setupWailsEvents() {
    // Prevent duplicate registration during hot-reload
    if (eventsInitialized) return;
    eventsInitialized = true;

    EventsOn('debug:log', (msg) => {
        console.log('[BACKEND]', msg);
    });

    EventsOn('chat:chunk', (content) => {
        state.currentOutput += content;
        elements.outputText.textContent = state.currentOutput;
        // Auto-scroll to bottom
        elements.outputText.scrollTop = elements.outputText.scrollHeight;
    });

    EventsOn('chat:error', (error) => {
        console.error('Chat error:', error);
        showToast(error, 'error');
    });

    EventsOn('chat:complete', async () => {
        console.log('[FRONTEND] Received chat:complete');
        // Small delay to ensure all chunks are rendered
        await new Promise(r => setTimeout(r, 200));

        setProcessingState(false);

        // Add to history
        if (state.currentOutput) {
            await AddHistoryEntry(
                state.selectedPattern,
                state.selectedModel,
                elements.inputText.value,
                state.currentOutput
            );
            state.historyCount++;
            state.historyIndex = state.historyCount - 1;
            await updateHistoryDisplay();
            showToast('Request completed', 'success');
        }
    });

    EventsOn('server:started', () => {
        showToast('Server started', 'success');
    });

    EventsOn('server:stopped', () => {
        showToast('Server stopped', 'info');
    });
}

// ============================================
// Toast Notifications
// ============================================
function showToast(message, type = 'info') {
    const icons = {
        success: '✓',
        error: '✗',
        warning: '⚠',
        info: 'ℹ',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close">✕</button>
    `;

    elements.toastContainer.appendChild(toast);

    // Close button
    toast.querySelector('.toast-close').addEventListener('click', () => {
        removeToast(toast);
    });

    // Auto-remove after 4 seconds
    setTimeout(() => {
        removeToast(toast);
    }, 4000);
}

function removeToast(toast) {
    toast.classList.add('toast-exit');
    setTimeout(() => {
        toast.remove();
    }, 300);
}

// ============================================
// Event Listeners
// ============================================
let listenersInitialized = false;

function setupEventListeners() {
    // Prevent duplicate registration during hot-reload
    if (listenersInitialized) return;
    listenersInitialized = true;
    // Pattern search
    elements.patternSearch.addEventListener('input', (e) => {
        filterPatterns(e.target.value);
    });

    // Pattern selection
    elements.patternSelect.addEventListener('change', (e) => {
        state.selectedPattern = e.target.value;
        updateCommandPreview();
        savePreferences(); // Persist selection
    });

    // Model selection
    elements.modelSelect.addEventListener('change', (e) => {
        const [vendor, model] = e.target.value.split(':');
        state.selectedVendor = vendor;
        state.selectedModel = model;
        updateCommandPreview();
        savePreferences(); // Persist selection
    });

    // Send button
    elements.sendBtn.addEventListener('click', sendRequest);

    // Cancel button
    elements.cancelBtn.addEventListener('click', () => {
        setProcessingState(false);
        showToast('Request cancelled', 'info');
    });

    // Copy button
    elements.copyBtn.addEventListener('click', async () => {
        const text = elements.outputText.textContent;
        if (text) {
            await navigator.clipboard.writeText(text);
            showToast('Copied to clipboard', 'success');
        }
    });

    // Clear buttons
    elements.clearInputBtn.addEventListener('click', () => {
        elements.inputText.value = '';
    });

    elements.clearOutputBtn.addEventListener('click', () => {
        elements.outputText.textContent = '';
        state.currentOutput = '';
    });

    // Paste button
    elements.pasteBtn.addEventListener('click', async () => {
        const text = await navigator.clipboard.readText();
        elements.inputText.value = text;
        showToast('Text pasted', 'success');
        updateCommandPreview();
    });

    // Copy Command button
    const copyCommandBtn = document.getElementById('copyCommandBtn');
    if (copyCommandBtn) {
        copyCommandBtn.addEventListener('click', async () => {
            // Re-generate command content to ensure it's up to date
            const pattern = state.selectedPattern || '[pattern]';
            const model = state.selectedModel || '[model]';
            let inputPrefix = '';

            if (elements.inputText && elements.inputText.value) {
                inputPrefix = 'echo "..." | ';
            }

            const command = `${inputPrefix}fabric --pattern ${pattern} --model ${model}`;
            await navigator.clipboard.writeText(command);
            showToast('Command copied to clipboard', 'success');
        });
    }

    // Input text change
    elements.inputText.addEventListener('input', () => {
        updateCommandPreview();
    });

    // Import button
    elements.importBtn.addEventListener('click', importFile);

    // Save button
    elements.saveBtn.addEventListener('click', saveOutput);

    // History navigation
    elements.historyPrevBtn.addEventListener('click', () => navigateHistory(-1));
    elements.historyNextBtn.addEventListener('click', () => navigateHistory(1));

    // Settings
    elements.settingsBtn.addEventListener('click', () => {
        elements.settingsModal.classList.remove('hidden');
    });

    elements.closeSettingsBtn.addEventListener('click', closeSettings);
    elements.cancelSettingsBtn.addEventListener('click', closeSettings);

    elements.settingsModal.querySelector('.modal-backdrop').addEventListener('click', closeSettings);

    elements.testConnectionBtn.addEventListener('click', async () => {
        const result = elements.connectionResult;
        result.textContent = 'Testing...';
        result.className = 'connection-result';

        try {
            await SetBaseURL(elements.baseUrlInput.value);
            const isOnline = await CheckHealth();

            if (isOnline) {
                result.textContent = '✓ Connection successful';
                result.className = 'connection-result success';
            } else {
                result.textContent = '✗ Server not responding';
                result.className = 'connection-result error';
            }
        } catch (e) {
            result.textContent = `✗ ${e}`;
            result.className = 'connection-result error';
        }
    });

    elements.saveSettingsBtn.addEventListener('click', async () => {
        await SetBaseURL(elements.baseUrlInput.value);
        await savePreferences();
        closeSettings();
        await checkServerStatus();

        if (state.serverOnline) {
            await loadPatterns();
            await loadModels();
        }

        showToast('Settings saved', 'success');
    });

    // Theme toggle
    elements.themeToggle.addEventListener('click', toggleTheme);

    // Server toggle
    elements.serverStatus.addEventListener('click', toggleServer);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter to send
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            if (!state.isProcessing) {
                sendRequest();
            }
        }

        // Ctrl+S to save output
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            saveOutput();
        }

        // Ctrl+O to import file
        if (e.ctrlKey && e.key === 'o') {
            e.preventDefault();
            importFile();
        }

        // Alt+Left for previous history
        if (e.altKey && e.key === 'ArrowLeft') {
            e.preventDefault();
            navigateHistory(-1);
        }

        // Alt+Right for next history
        if (e.altKey && e.key === 'ArrowRight') {
            e.preventDefault();
            navigateHistory(1);
        }

        // Escape to close modals
        if (e.key === 'Escape') {
            closeSettings();
        }
    });
}

function closeSettings() {
    elements.settingsModal.classList.add('hidden');
    elements.connectionResult.textContent = '';
}

// ============================================
// Start
// ============================================
document.addEventListener('DOMContentLoaded', init);
