"""
Fabric Mini GUI - A desktop client for interacting with Fabric AI patterns.

This application provides a graphical interface for sending text to Fabric patterns
and receiving AI-processed responses.
"""

import json
import logging
import os
import subprocess
import signal
import threading
import time
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, scrolledtext, filedialog
from typing import Dict, List, Optional, Any

import requests


# Configure logging
LOG_DIR = Path.home() / ".fabric_gui"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "fabric_gui.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration persistence."""
    
    CONFIG_FILE = LOG_DIR / "config.json"
    
    DEFAULT_CONFIG = {
        "base_url": "http://localhost:8080",
        "api_key": "",
        "request_timeout": 300,  # 5 minutes
        "last_pattern": "",
        "window_geometry": "900x600",
        "auto_start_server": False,
        "stop_server_on_exit": True,
        "server_health_check_interval": 5,
        "fabric_command": "fabric"
    }
    
    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            if cls.CONFIG_FILE.exists():
                with open(cls.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to handle new config keys
                    return {**cls.DEFAULT_CONFIG, **config}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
        return cls.DEFAULT_CONFIG.copy()
    
    @classmethod
    def save(cls, config: Dict[str, Any]) -> None:
        """Save configuration to file."""
        try:
            with open(cls.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")


class OutputHistory:
    """Manages output history with navigation."""
    
    def __init__(self, max_size: int = 50):
        self.history: List[Dict[str, str]] = []
        self.max_size = max_size
        self.current_index = -1
    
    def add(self, pattern: str, input_text: str, output_text: str) -> None:
        """Add an entry to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "pattern": pattern,
            "input": input_text,
            "output": output_text
        }
        self.history.append(entry)
        if len(self.history) > self.max_size:
            self.history.pop(0)
        self.current_index = len(self.history) - 1
    
    def get_current(self) -> Optional[Dict[str, str]]:
        """Get current history entry."""
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index]
        return None
    
    def previous(self) -> Optional[Dict[str, str]]:
        """Move to previous entry."""
        if self.current_index > 0:
            self.current_index -= 1
            return self.history[self.current_index]
        return None
    
    def next(self) -> Optional[Dict[str, str]]:
        """Move to next entry."""
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return self.history[self.current_index]
        return None
    
    def has_previous(self) -> bool:
        return self.current_index > 0
    
    def has_next(self) -> bool:
        return self.current_index < len(self.history) - 1
    
    def update_current_output(self, output_text: str) -> None:
        """Update the output of the current history entry."""
        if 0 <= self.current_index < len(self.history):
            self.history[self.current_index]["output"] = output_text


class ServerManager:
    """Manages Fabric server process and health monitoring."""
    
    def __init__(self, fabric_command: str = "fabric", base_url: str = "http://localhost:8080"):
        self.fabric_command = fabric_command
        self.base_url = base_url
        self.process: Optional[subprocess.Popen] = None
        self.is_online = False
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = False
    
    def start_server(self) -> bool:
        """Start the Fabric server process in a new console window."""
        if self.process and self.process.poll() is None:
            logger.warning("Server is already running")
            return False
        
        try:
            # Resolve full path to fabric
            import shutil
            fabric_path = shutil.which(self.fabric_command)
            if not fabric_path:
                logger.error(f"Fabric command not found: {self.fabric_command}")
                return False
                
            logger.info(f"Starting Fabric server in new console: {fabric_path} --serve")
            
            # Configure startup info to minimize the window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 7  # SW_SHOWMINNOACTIVE
            
            # Start server process in a new visible console window
            # This mimics the user manually opening a terminal, which we know works.
            # We do NOT pipe stdout/stderr, so it appears in the new window.
            self.process = subprocess.Popen(
                [fabric_path, "--serve"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                startupinfo=startupinfo,
                close_fds=True
            )
            
            logger.info(f"Server process started with PID: {self.process.pid}")
            
            # Wait a moment for server to initialize
            time.sleep(2)
            
            # Check if process is still running
            if self.process.poll() is not None:
                logger.error("Server process terminated immediately")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def stop_server(self, timeout: int = 5) -> bool:
        """Stop the Fabric server process."""
        if not self.process or self.process.poll() is not None:
            logger.info("Server is not running")
            return True
        
        try:
            logger.info(f"Stopping server (PID: {self.process.pid})")
            
            # Try graceful shutdown first
            if os.name == 'nt':
                # Windows: send CTRL_BREAK_EVENT
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # Unix: send SIGTERM
                self.process.terminate()
            
            # Wait for process to exit
            try:
                self.process.wait(timeout=timeout)
                logger.info("Server stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Server did not stop gracefully, forcing...")
                self.process.kill()
                self.process.wait()
                logger.info("Server force-stopped")
            
            self.process = None
            self.is_online = False
            return True
        
        except Exception as e:
            logger.error(f"Failed to stop server: {e}")
            return False
    
    def check_health(self) -> bool:
        """Check if server is responding."""
        try:
            resp = requests.get(f"{self.base_url}/config", timeout=2)
            is_healthy = resp.status_code == 200
            
            if is_healthy != self.is_online:
                logger.info(f"Server status changed: {'online' if is_healthy else 'offline'}")
            
            self.is_online = is_healthy
            return is_healthy
        
        except Exception:
            if self.is_online:
                logger.info("Server is offline")
            self.is_online = False
            return False
    
    def start_health_monitoring(self, interval: int = 5, callback: Optional[callable] = None):
        """Start periodic health checks in background thread."""
        if self._health_check_thread and self._health_check_thread.is_alive():
            return
        
        self._stop_health_check = False
        
        def monitor():
            while not self._stop_health_check:
                self.check_health()
                if callback:
                    callback(self.is_online)
                time.sleep(interval)
        
        self._health_check_thread = threading.Thread(target=monitor, daemon=True)
        self._health_check_thread.start()
        logger.info(f"Health monitoring started (interval: {interval}s)")

    def get_patterns(self) -> Optional[List[str]]:
        """Get list of available patterns from server."""
        try:
            # Try to fetch patterns from the server
            # Valid endpoint is /patterns/names
            resp = requests.get(f"{self.base_url}/patterns/names", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return sorted(data)
                return sorted(data.get("patterns", []))
            return []
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return None

    def get_models(self) -> Dict[str, List[str]]:
        """Get list of available models from fabric CLI."""
        try:
            # Run fabric --listmodels
            import shutil
            fabric_path = shutil.which(self.fabric_command)
            if not fabric_path:
                return {}

            # Run command
            result = subprocess.run(
                [fabric_path, "--listmodels"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to list models: {result.stderr}")
                return {}

            models_by_provider = {}
            
            # Parse output
            # Format: [index] Provider|Model or just Model
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                
                # Strip index like [123]
                import re
                # Match [123] at start, allowing for whitespace
                match = re.match(r'^\[\d+\]\s*(.*)$', line)
                if match:
                    content = match.group(1).strip()
                    
                    if '|' in content:
                        provider, model = content.split('|', 1)
                        provider = provider.strip()
                        model = model.strip()
                    else:
                        provider = "Other"
                        model = content.strip()
                        
                    if provider not in models_by_provider:
                        models_by_provider[provider] = []
                    models_by_provider[provider].append(model)
            
            return models_by_provider
            
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return {}

    def get_default_model(self) -> Optional[str]:
        """Get default model from Fabric config."""
        try:
            # Config is usually at ~/.config/fabric/.env
            config_path = Path.home() / ".config" / "fabric" / ".env"
            
            if not config_path.exists():
                return None
                
            # Read file
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Parse DEFAULT_MODEL=...
            import re
            match = re.search(r'^DEFAULT_MODEL=(.+)$', content, re.MULTILINE)
            if match:
                return match.group(1).strip()
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting default model: {e}")
            return None

    def normalize_base_url(self, url: str) -> str:
        """Normalize and validate base URL."""
        url = url.strip()
        if not url:
            raise ValueError("Base URL cannot be empty")
        
        if url.endswith("/"):
            url = url[:-1]
            
        return url
    
    def stop_health_monitoring(self):
        """Stop health check monitoring."""
        self._stop_health_check = True
        if self._health_check_thread:
            self._health_check_thread.join(timeout=2)
        logger.info("Health monitoring stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current server status."""
        return {
            "is_online": self.is_online,
            "process_running": self.process is not None and self.process.poll() is None,
            "pid": self.process.pid if self.process else None
        }
    
    def is_running(self) -> bool:
        """Check if server is running (process exists and is online)."""
        return self.is_online


class ContextMenu:
    """Standard right-click context menu for text widgets."""
    
    def __init__(self, widget: tk.Widget):
        self.widget = widget
        self.menu = tk.Menu(widget, tearoff=0)
        self.menu.add_command(label="Cut", command=self._cut)
        self.menu.add_command(label="Copy", command=self._copy)
        self.menu.add_command(label="Paste", command=self._paste)
        self.menu.add_separator()
        self.menu.add_command(label="Select All", command=self._select_all)
        
        # Bind right-click event
        widget.bind("<Button-3>", self._show_menu)
        
    def _show_menu(self, event):
        """Show the context menu."""
        # Check if widget is read-only or disabled
        state = str(self.widget.cget("state"))
        is_readonly = state == "disabled" or (hasattr(self.widget, "cget") and self.widget.cget("state") == "readonly")
        
        # Enable/disable items based on state and content
        if is_readonly:
            self.menu.entryconfig("Cut", state="disabled")
            self.menu.entryconfig("Paste", state="disabled")
        else:
            self.menu.entryconfig("Cut", state="normal")
            self.menu.entryconfig("Paste", state="normal")
            
        # Check if there is a selection for Copy/Cut
        try:
            has_selection = bool(self.widget.selection_get())
        except tk.TclError:
            has_selection = False
            
        self.menu.entryconfig("Copy", state="normal" if has_selection else "disabled")
        if not is_readonly:
            self.menu.entryconfig("Cut", state="normal" if has_selection else "disabled")
            
        self.menu.tk_popup(event.x_root, event.y_root)
        
    def _cut(self):
        """Cut selection."""
        try:
            self.widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass
            
    def _copy(self):
        """Copy selection."""
        try:
            self.widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass
            
    def _paste(self):
        """Paste from clipboard."""
        try:
            self.widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass
            
    def _select_all(self):
        """Select all text."""
        self.widget.focus_force()
        self.widget.event_generate("<<SelectAll>>")
        # Fallback for widgets that might not support <<SelectAll>> natively or correctly
        if isinstance(self.widget, (tk.Text, scrolledtext.ScrolledText)):
            self.widget.tag_add("sel", "1.0", "end")
        elif isinstance(self.widget, tk.Entry):
            self.widget.select_range(0, "end")


class FabricGUI(ctk.CTk):
    """Main application window for Fabric GUI."""
    
    def __init__(self):
        super().__init__()
        
        # Configure CustomTkinter
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        # Load configuration
        self.app_config = ConfigManager.load()
        
        # Initialize history
        self.history = OutputHistory()
        
        # Configure ttk style for Combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", 
            fieldbackground="#333333", 
            background="#333333", 
            foreground="white", 
            arrowcolor="white",
            bordercolor="#333333",
            darkcolor="#333333",
            lightcolor="#333333",
            font=("Roboto", 12)
        )
        style.map("TCombobox", 
            fieldbackground=[("readonly", "#333333")], 
            selectbackground=[("readonly", "#1f538d")], 
            selectforeground=[("readonly", "white")],
            background=[("readonly", "#333333")]
        )
        # Configure dropdown listbox style (requires option_add)
        self.option_add('*TCombobox*Listbox.background', '#333333')
        self.option_add('*TCombobox*Listbox.foreground', 'white')
        self.option_add('*TCombobox*Listbox.selectBackground', '#1f538d')
        self.option_add('*TCombobox*Listbox.selectForeground', 'white')
        
        # Initialize server manager
        self.server_manager = ServerManager(
            fabric_command=self.app_config["fabric_command"],
            base_url=self.app_config["base_url"]
        )
        
        # Request cancellation
        self.cancel_request = False
        self.current_request_thread: Optional[threading.Thread] = None
        self.current_process = None  # For subprocess execution
        
        # UI Variables
        self.base_url_var = tk.StringVar(value=self.app_config["base_url"])
        self.api_key_var = tk.StringVar(value=self.app_config["api_key"])
        self.pattern_var = tk.StringVar(value=self.app_config["last_pattern"])
        self.status_var = tk.StringVar(value="Ready")
        self.command_var = tk.StringVar(value="")
        
        # Update command preview when pattern changes
        self.pattern_var.trace_add("write", self._update_command_preview)
        self._update_command_preview()  # Initialize command preview
        
        # Setup window
        self.title("Fabric Mini GUI")
        self.geometry(self.app_config["window_geometry"])
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Build UI
        self._build_menu()
        self._build_server_frame()
        self._build_pattern_frame()
        self._build_info_frame()
        self._build_io_frame()
        
        # Keyboard shortcuts
        self._setup_shortcuts()
        
        # Start health monitoring
        self.server_manager.start_health_monitoring(
            interval=self.app_config["server_health_check_interval"],
            callback=self._on_server_status_change
        )
        
        # Auto-start server if configured
        if self.app_config["auto_start_server"]:
            self.after(1000, self._auto_start_server)
        
        # Load patterns automatically on start
        self.after(500, self.load_patterns)
        
        logger.info("Fabric GUI started")
    
    # -----------------------------
    # UI Construction
    # -----------------------------
    
    def _build_menu(self):
        """Build menu bar."""
        # CustomTkinter doesn't have a native menu bar, so we keep tk.Menu for now.
        # It works on Windows.
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Output...", command=self.save_output, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Copy Output", command=self.copy_output, accelerator="Ctrl+C")
        edit_menu.add_command(label="Clear Output", command=self.clear_output)
        edit_menu.add_separator()
        edit_menu.add_command(label="Paste Input", command=self.paste_input)
        edit_menu.add_command(label="Clear Input", command=self.clear_input)
        
        # History menu
        history_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="History", menu=history_menu)
        history_menu.add_command(label="Previous", command=self.history_previous, accelerator="Alt+Left")
        history_menu.add_command(label="Next", command=self.history_next, accelerator="Alt+Right")
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="View Logs", command=self.view_logs)
        help_menu.add_command(label="About", command=self.show_about)
    
    def _build_server_frame(self):
        """Build server configuration frame with status LED and controls."""
        # Using CTkFrame instead of LabelFrame (not available in ctk)
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=5)
        
        # Title for the frame (simulating LabelFrame)
        title_label = ctk.CTkLabel(frame, text="Server Configuration", font=("Roboto", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=8, sticky="w", padx=10, pady=(5, 0))
        
        # Content container
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.grid(row=1, column=0, columnspan=8, sticky="ew", padx=5, pady=5)
        
        # LED Status Indicator
        led_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        led_frame.pack(side="left", padx=5)
        
        ctk.CTkLabel(led_frame, text="Status:").pack(side="left", padx=(0, 5))
        
        self.status_led = tk.Canvas(led_frame, width=20, height=20, highlightthickness=0, bg="black")
        self.status_led.pack(side="left")
        self.led_indicator = self.status_led.create_oval(2, 2, 18, 18, fill="red", outline="darkred")
        
        # Tooltip for LED
        self._create_tooltip(self.status_led, "Server: Offline")
        
        # Base URL
        ctk.CTkLabel(content_frame, text="Base URL:").pack(side="left", padx=5)
        entry_url = ctk.CTkEntry(content_frame, textvariable=self.base_url_var, width=200)
        entry_url.pack(side="left", padx=5)
        self._add_context_menu(entry_url)
        
        # API Key
        ctk.CTkLabel(content_frame, text="API Key:").pack(side="left", padx=5)
        entry_key = ctk.CTkEntry(content_frame, textvariable=self.api_key_var, width=150, show="*")
        entry_key.pack(side="left", padx=5)
        self._add_context_menu(entry_key)
        
        # Control buttons
        btn_test = ctk.CTkButton(content_frame, text="Test", command=self.on_test_server, width=60)
        btn_test.pack(side="left", padx=5)
        
        self.btn_start_server = ctk.CTkButton(content_frame, text="Start", command=self.on_start_server, width=60)
        self.btn_start_server.pack(side="left", padx=5)
        
        self.btn_stop_server = ctk.CTkButton(content_frame, text="Stop", command=self.on_stop_server, width=60, state="disabled")
        self.btn_stop_server.pack(side="left", padx=5)
    
    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget."""
        # Store initial tooltip text
        widget.tooltip_text = text
        
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            # Use stored tooltip text
            tooltip_text = getattr(widget, 'tooltip_text', text)
            label = tk.Label(tooltip, text=tooltip_text, background="lightyellow", relief="solid", borderwidth=1)
            label.pack()
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
    
    def _add_context_menu(self, widget):
        """Add context menu to a widget."""
        ContextMenu(widget)
    
    def _build_pattern_frame(self):
        """Build pattern selection frame."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=5)
        
        # Title
        ctk.CTkLabel(frame, text="Pattern Selection", font=("Roboto", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 0))
        
        # Content
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(content_frame, text="Pattern:").pack(side="left", padx=5)
        
        # Use ttk.Combobox for native scrollbar support
        self.pattern_combo = ttk.Combobox(
            content_frame, 
            textvariable=self.pattern_var, 
            width=40,
            state="readonly",
            height=40
        )
        self.pattern_combo.pack(side="left", padx=5, fill="x", expand=True)
        
        # Note: ttk.Combobox has native scrolling, no need for custom binding
        
        btn_load = ctk.CTkButton(content_frame, text="Refresh Patterns", command=self.load_patterns)
        btn_load.pack(side="left", padx=5)
        
        # Model Selection
        model_frame = ctk.CTkFrame(frame, fg_color="transparent")
        model_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(model_frame, text="Model:").pack(side="left", padx=5)
        
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            width=40,
            state="readonly",
            height=40
        )
        self.model_combo.pack(side="left", padx=5, fill="x", expand=True)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_selected)
        
        # Default Model Label
        self.default_model_label = ctk.CTkLabel(
            model_frame, 
            text="Default: (loading...)", 
            text_color="gray",
            cursor="hand2"
        )
        self.default_model_label.pack(side="left", padx=5)
        
        # Bind click and hover events
        self.default_model_label.bind("<Button-1>", lambda e: self.reset_model_selection())
        self.default_model_label.bind("<Enter>", lambda e: self.default_model_label.configure(text_color="#3B8ED0")) # Blue on hover
        self.default_model_label.bind("<Leave>", lambda e: self.default_model_label.configure(text_color="gray"))
        
        frame.columnconfigure(0, weight=1)
        
        # Load models
        self.after(1000, self.load_models)

    def reset_model_selection(self):
        """Reset model selection to default."""
        self.model_var.set("")
        self._update_command_preview()
        self.status_var.set("Model reset to default")
        # Flash the label to indicate action
        original_color = self.default_model_label.cget("text_color")
        self.default_model_label.configure(text_color="green")
        self.after(300, lambda: self.default_model_label.configure(text_color="gray"))
    
    def _build_info_frame(self):
        """Build info frame with status and command preview."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=5)
        
        # Status
        status_frame = ctk.CTkFrame(frame, fg_color="transparent")
        status_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(status_frame, text="Status", font=("Roboto", 14, "bold")).pack(anchor="w")
        self.status_label = ctk.CTkLabel(
            status_frame, 
            textvariable=self.status_var, 
            font=("Segoe UI", 14, "bold"),
            text_color=("#3B8ED0", "#1F6AA5") # Adaptive blue
        )
        self.status_label.pack(fill="x", pady=2)
        
        # Command Preview
        cmd_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cmd_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(cmd_frame, text="Command Preview", font=("Roboto", 14, "bold")).pack(anchor="w")
        cmd_entry = ctk.CTkEntry(
            cmd_frame, 
            textvariable=self.command_var, 
            state="readonly",
            font=("Consolas", 12)
        )
        cmd_entry.pack(fill="x", pady=2)
        
        # Actions
        action_frame = ctk.CTkFrame(frame, fg_color="transparent")
        action_frame.pack(side="left", padx=5, pady=5)
        
        ctk.CTkLabel(action_frame, text="Actions", font=("Roboto", 14, "bold")).pack(anchor="w")
        
        button_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_container.pack(fill="x", pady=2)
        
        self.btn_cancel = ctk.CTkButton(
            button_container, 
            text="Cancel", 
            command=self.on_cancel,
            state="disabled",
            fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE")
        )
        self.btn_cancel.pack(side="left", padx=2)
        
        self.btn_send = ctk.CTkButton(
            button_container, 
            text="Send", 
            command=self.on_send,
            width=100,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.btn_send.pack(side="left", padx=2)
    
    def _update_command_preview(self, *args):
        """Update the command preview based on current pattern."""
        pattern = self.pattern_var.get()
        cmd = self.app_config['fabric_command']
        
        if pattern:
            cmd += f" -p {pattern}"
            
        # Add model if selected
        if hasattr(self, 'model_var'):
            model_selection = self.model_var.get()
            if model_selection and not model_selection.endswith("(Default)"):
                # Extract model name from selection (strip indentation)
                model_name = model_selection.strip()
                # If it's a provider header (no indentation), ignore it in preview?
                # But our selection logic should prevent selecting headers.
                if model_name and not model_selection.startswith(" "): # It's a header
                     pass 
                elif model_name:
                    cmd += f" -m {model_name}"
                    
        self.command_var.set(cmd)
    
    def _add_context_menu(self, widget):
        """Add context menu to a widget."""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: widget.event_generate("<<SelectAll>>"))
        
        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)
            return "break"
            
        widget.bind("<Button-3>", show_menu)
        
    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget."""
        widget.tooltip_text = text
        
        def enter(event):
            text = getattr(widget, "tooltip_text", "")
            if not text:
                return
                
            x = widget.winfo_rootx() + 25
            y = widget.winfo_rooty() + 25
            
            # Create tooltip window
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            
            label = tk.Label(self.tooltip, text=text, justify='left',
                           background="#ffffff", relief='solid', borderwidth=1,
                           font=("tahoma", "10", "normal"))
            label.pack(ipadx=1)
            
        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                del self.tooltip
                
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def _build_io_frame(self):
        """Build input/output frame."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Input section
        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(input_frame, text="Input", font=("Roboto", 14, "bold")).pack(anchor="w")
        
        # Input Toolbar
        input_toolbar = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_toolbar.pack(fill="x", pady=(0, 5))
        
        ctk.CTkButton(input_toolbar, text="Paste", command=self.paste_input, width=60).pack(side="left", padx=2)
        ctk.CTkButton(input_toolbar, text="Clear", command=self.clear_input, width=60).pack(side="left", padx=2)
        
        self.input_text = ctk.CTkTextbox(
            input_frame, 
            wrap="word", 
            font=("Consolas", 14)
        )
        self.input_text.pack(fill="both", expand=True, padx=2, pady=2)
        # Bind context menu to internal text widget for correct event handling
        self._add_context_menu(self.input_text._textbox)
        
        # Output section
        output_frame = ctk.CTkFrame(frame, fg_color="transparent")
        output_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        ctk.CTkLabel(output_frame, text="Output", font=("Roboto", 14, "bold")).pack(anchor="w")
        
        # Output toolbar
        output_toolbar = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_toolbar.pack(fill="x", pady=(0, 5))
        
        ctk.CTkButton(output_toolbar, text="Copy", command=self.copy_output, width=60).pack(side="left", padx=2)
        ctk.CTkButton(output_toolbar, text="Save", command=self.save_output, width=60).pack(side="left", padx=2)
        ctk.CTkButton(output_toolbar, text="Clear", command=self.clear_output, width=60).pack(side="left", padx=2)
        
        # History navigation
        ctk.CTkFrame(output_toolbar, width=2, height=20, fg_color="gray50").pack(side="left", padx=5)
        
        self.btn_history_prev = ctk.CTkButton(
            output_toolbar, 
            text="<", 
            command=self.history_previous, 
            width=30
        )
        self.btn_history_prev.pack(side="left", padx=2)
        
        self.btn_history_next = ctk.CTkButton(
            output_toolbar, 
            text=">", 
            command=self.history_next, 
            width=30
        )
        self.btn_history_next.pack(side="left", padx=2)
        
        self.output_text = ctk.CTkTextbox(
            output_frame, 
            wrap="word", 
            state="disabled",
            font=("Consolas", 14)
        )
        self.output_text.pack(fill="both", expand=True, padx=2, pady=2)
        # Bind context menu to internal text widget
        self._add_context_menu(self.output_text._textbox)
        
        self._update_history_buttons()
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        self.bind("<Control-s>", lambda e: self.save_output())
        self.bind("<Control-c>", lambda e: self.copy_output())
        self.bind("<Alt-Left>", lambda e: self.history_previous())
        self.bind("<Alt-Right>", lambda e: self.history_next())
        self.bind("<Control-Return>", lambda e: self.on_send())
    
    def _bind_mousewheel_to_combobox(self, combobox):
        """Enable mouse wheel scrolling for combobox."""
        def on_mousewheel(event):
            values = combobox.cget("values")
            if not values:
                return
            
            current = combobox.get()
            try:
                index = list(values).index(current)
            except ValueError:
                index = 0
            
            # Scroll up or down
            if event.delta > 0:  # Scroll up
                index = max(0, index - 1)
            else:  # Scroll down
                index = min(len(values) - 1, index + 1)
            
            combobox.set(values[index])
        
        combobox.bind("<MouseWheel>", on_mousewheel)
    
    # -----------------------------
    # Helper Methods
    # -----------------------------
    
    def set_status(self, text: str):
        """Update status bar text."""
        self.status_var.set(text)
        self.update_idletasks()
        logger.info(f"Status: {text}")
    
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {"Content-Type": "application/json"}
        api_key = self.api_key_var.get().strip()
        if api_key:
            headers["X-API-Key"] = api_key
        return headers
    
    def normalize_base_url(self) -> str:
        """Normalize and validate base URL."""
        url = self.base_url_var.get().strip()
        
        if not url:
            raise ValueError("Base URL cannot be empty")
        
        if url.endswith("/"):
            url = url[:-1]
        
        # Warn about HTTP (not HTTPS)
        if url.startswith("http://") and "localhost" not in url and "127.0.0.1" not in url:
            logger.warning("Using insecure HTTP connection")
        
        self.base_url_var.set(url)
        return url
    
    def set_output_text(self, text: str):
        """Set output text widget content."""
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")
    
    def set_ui_state(self, processing: bool):
        """Enable/disable UI elements during processing."""
        state = "disabled" if processing else "normal"
        self.btn_send.configure(state=state)
        self.btn_cancel.configure(state="normal" if processing else "disabled")
    
    def _update_history_buttons(self):
        """Update history navigation button states."""
        self.btn_history_prev.configure(
            state="normal" if self.history.has_previous() else "disabled"
        )
        self.btn_history_next.configure(
            state="normal" if self.history.has_next() else "disabled"
        )
    
    def save_config(self):
        """Save current configuration."""
        self.app_config.update({
            "base_url": self.base_url_var.get(),
            "api_key": self.api_key_var.get(),
            "last_pattern": self.pattern_var.get(),
            "window_geometry": self.geometry()
        })
        ConfigManager.save(self.app_config)
    
    # -----------------------------
    # Content Extraction Methods
    # -----------------------------
    
    def extract_content_from_json(self, data: Any) -> str:
        """Extract content from JSON response."""
        if isinstance(data, dict):
            if "content" in data and "type" in data:
                return data["content"]
            return json.dumps(data, indent=2)
        elif isinstance(data, list):
            parts = []
            for item in data:
                if isinstance(item, dict) and item.get("type") == "content":
                    parts.append(item.get("content", ""))
            if parts:
                return "\n".join(parts)
            return json.dumps(data, indent=2)
        else:
            return str(data)
    
    def parse_sse_response(self, response: requests.Response) -> str:
        """Parse Server-Sent Events response."""
        contents = []
        
        try:
            for line in response.iter_lines(decode_unicode=True):
                if self.cancel_request:
                    logger.info("Request cancelled by user")
                    return "[Request cancelled]"
                
                if not line:
                    continue
                
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                
                # Extract content from Fabric response format
                if isinstance(obj, dict) and obj.get("type") == "content":
                    contents.append(obj.get("content", ""))
                elif isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict) and item.get("type") == "content":
                            contents.append(item.get("content", ""))
            
            return "\n".join(contents).strip()
        
        except Exception as e:
            logger.error(f"Error parsing SSE: {e}")
            raise
    
    def parse_sse_text(self, text: str) -> str:
        """Parse SSE content from a raw string."""
        contents = []
        
        try:
            for line in text.splitlines():
                if not line:
                    continue
                
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                
                # Extract content from Fabric response format
                if isinstance(obj, dict) and obj.get("type") == "content":
                    contents.append(obj.get("content", ""))
                elif isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict) and item.get("type") == "content":
                            contents.append(item.get("content", ""))
            
            return "\n".join(contents).strip()
        
        except Exception as e:
            logger.error(f"Error parsing SSE text: {e}")
            return text
            
    def on_test_server(self):
        """Test server connection."""
        base_url = self.base_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        
        if not base_url:
            messagebox.showerror("Error", "Base URL is required")
            return
            
        try:
            # Update config if changed
            if base_url != self.app_config["base_url"] or api_key != self.app_config["api_key"]:
                self.app_config["base_url"] = base_url
                self.app_config["api_key"] = api_key
                self.server_manager.base_url = self.server_manager.normalize_base_url(base_url)
                self.save_config()
            
            # Test connection
            is_online = self.server_manager.check_health()
            
            if is_online:
                messagebox.showinfo("Success", "Connected to Fabric server successfully!")
                self._on_server_status_change(True)
            else:
                messagebox.showerror("Error", "Could not connect to Fabric server.\nMake sure it is running and the URL is correct.")
                self._on_server_status_change(False)
                
        except Exception as e:
            logger.error(f"Test connection failed: {e}")
            messagebox.showerror("Error", f"Connection test failed: {str(e)}")
            
    def on_start_server(self):
        """Start the Fabric server."""
        try:
            self.btn_start_server.configure(state="disabled")
            self.set_status("Starting server...")
            
            success = self.server_manager.start_server()
            
            if success:
                self.set_status("Server started")
                self._on_server_status_change(True)
            else:
                self.set_status("Failed to start server")
                messagebox.showerror("Error", "Failed to start server. Check logs for details.")
                self.btn_start_server.configure(state="normal")
                
        except Exception as e:
            logger.error(f"Start server error: {e}")
            self.set_status("Error starting server")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.btn_start_server.configure(state="normal")
            
    def on_stop_server(self):
        """Stop the Fabric server."""
        if not messagebox.askyesno("Confirm", "Are you sure you want to stop the Fabric server?"):
            return
            
        try:
            self.btn_stop_server.configure(state="disabled")
            self.set_status("Stopping server...")
            
            success = self.server_manager.stop_server()
            
            if success:
                self.set_status("Server stopped")
                self._on_server_status_change(False)
            else:
                self.set_status("Failed to stop server")
                messagebox.showerror("Error", "Failed to stop server. Check logs for details.")
                self.btn_stop_server.configure(state="normal")
                
        except Exception as e:
            logger.error(f"Stop server error: {e}")
            self.set_status("Error stopping server")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.btn_stop_server.configure(state="normal")

    def _auto_start_server(self):
        """Auto-start server if configured."""
        logger.info("Auto-starting server...")
        self.on_start_server()
    
    def _on_server_status_change(self, is_online: bool):
        """Callback for server status changes."""
        # Update LED in main thread
        self.after(0, lambda: self._update_led_status(is_online))
    
    def _update_led_status(self, is_online: bool):
        """Update LED indicator based on server status."""
        if is_online:
            self.status_led.itemconfig(self.led_indicator, fill="green", outline="darkgreen")
            self._update_tooltip_text(self.status_led, "Server: Online")
            self.btn_start_server.configure(state="disabled")
            self.btn_stop_server.configure(state="normal")
            # Auto-load patterns when server comes online, but only if not already loaded
            current_values = self.pattern_combo.cget("values")
            if not current_values or current_values == ["No patterns found"] or current_values == ["Error loading patterns"]:
                self.load_patterns()
        else:
            self.status_led.itemconfig(self.led_indicator, fill="red", outline="darkred")
            self._update_tooltip_text(self.status_led, "Server: Offline")
            self.btn_start_server.configure(state="normal")
            self.btn_stop_server.configure(state="disabled")
    
    def _update_tooltip_text(self, widget, text):
        """Update tooltip text for a widget."""
        # Store tooltip text as widget attribute
        widget.tooltip_text = text

    def load_patterns(self):
        """Load available patterns from Fabric."""
        try:
            patterns = self.server_manager.get_patterns()
            if patterns is not None:
                if patterns:
                    logger.info(f"Loaded {len(patterns)} patterns")
                    self.pattern_combo.configure(values=patterns)
                    if self.app_config["last_pattern"] in patterns:
                        self.pattern_var.set(self.app_config["last_pattern"])
                    elif patterns:
                        self.pattern_var.set(patterns[0])
                else:
                    self.pattern_combo.configure(values=["No patterns found"])
                    self.pattern_var.set("")
            else:
                self.pattern_combo.configure(values=["Server Offline / Error"])
                self.pattern_var.set("")
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
            self.pattern_combo.configure(values=["Error loading patterns"])
            
    def on_send(self, event=None):
        """Handle send button click."""
        input_text = self.input_text.get("1.0", "end-1c")
        if not input_text.strip():
            messagebox.showwarning("Warning", "Please enter some text to process.")
            return
            
        # Check if server is running
        if not self.server_manager.is_running():
            if messagebox.askyesno("Server Offline", "The Fabric server appears to be offline. Start it now?"):
                self.on_start_server()
                # Wait a bit for server to start
                self.after(2000, lambda: self.on_send(event))
            return

        self.set_ui_state(processing=True)
        self.status_var.set("Processing...")
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        
        # Save input to history
        self.history.add(self.pattern_var.get(), input_text, "")
        
        # Start processing in a separate thread
        self.cancel_request = False
        self.current_request_thread = threading.Thread(target=self._process_request, args=(input_text,))
        self.current_request_thread.daemon = True
        self.current_request_thread.start()
        
    def on_cancel(self):
        """Handle cancel button click."""
        if self.current_request_thread and self.current_request_thread.is_alive():
            self.cancel_request = True
            self.status_var.set("Cancelling...")
            self.btn_cancel.configure(state="disabled")
            
    def load_models(self):
        """Load available models and populate dropdown."""
        try:
            models_by_provider = self.server_manager.get_models()
            if not models_by_provider:
                self.model_combo.configure(values=["Error loading models"])
                return

            display_values = []
            
            # Sort providers
            sorted_providers = sorted(models_by_provider.keys())
            
            for provider in sorted_providers:
                # Add Provider as a header (no indentation)
                display_values.append(provider)
                
                # Add models indented
                for model in sorted(models_by_provider[provider]):
                    display_values.append(f"  {model}")
            
            self.model_combo.configure(values=display_values)
            
            # Get default model
            default_model = self.server_manager.get_default_model()
            if default_model:
                self.default_model_label.configure(text=f"Default: {default_model}")
            else:
                self.default_model_label.configure(text="Default: (System Default)")
            
            # Restore last selected model if valid
            last_model = self.app_config.get("last_model", "")
            if last_model:
                # Try to find it in the list (it might be indented)
                if f"  {last_model}" in display_values:
                    self.model_var.set(f"  {last_model}")
                elif last_model in display_values: # Should not happen for models
                    self.model_var.set(last_model)
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            self.model_combo.configure(values=["Error loading models"])

    def _on_model_selected(self, event):
        """Handle model selection."""
        selection = self.model_var.get()
        if not selection.startswith("  "):
            # User selected a provider header, reset selection or ignore
            # Ideally we would disable selection of headers, but Combobox doesn't support that easily.
            # We'll just clear it or select the first child?
            # Let's just clear it for now to indicate invalid selection
            self.model_var.set("")
            return
            
        self._update_command_preview()

    def _process_request(self, input_text):
        """Process the request in a background thread."""
        try:
            pattern = self.pattern_var.get()
            if not pattern:
                self.after(0, lambda: messagebox.showwarning("Warning", "Please select a pattern."))
                self.after(0, lambda: self.set_ui_state(processing=False))
                return

            # Save last used pattern
            self.app_config["last_pattern"] = pattern
            
            # Save last used model
            model_selection = self.model_var.get()
            if model_selection and model_selection.startswith("  "):
                self.app_config["last_model"] = model_selection.strip()
            
            self.save_config()
            
            # Use subprocess to call fabric CLI directly
            fabric_cmd = self.app_config.get("fabric_command", "fabric")
            cmd = [fabric_cmd, "-p", pattern]
            
            # Add model flag if selected
            if model_selection and model_selection.startswith("  "):
                model_name = model_selection.strip()
                cmd.extend(["-m", model_name])
            
            # Prepare environment with unbuffered output
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            # Start process with unbuffered binary I/O
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Redirect stderr to stdout to prevent deadlock
                text=False, # Binary mode for unbuffered I/O
                bufsize=0,  # Unbuffered
                env=env
            )
            
            self.current_process = process
            
            # Helper function to write input in a separate thread
            def _write_input(proc, text):
                try:
                    if text:
                        # Encode to UTF-8
                        proc.stdin.write(text.encode('utf-8'))
                        proc.stdin.flush()
                    proc.stdin.close()
                except Exception as e:
                    logger.error(f"Error writing to stdin: {e}")

            # Start writer thread
            self.after(0, lambda: self.status_var.set("Sending input..."))
            writer_thread = threading.Thread(target=_write_input, args=(process, input_text))
            writer_thread.daemon = True
            writer_thread.start()
            
            full_output = ""
            
            # Use incremental decoder for correct UTF-8 handling across chunks
            import codecs
            decoder = codecs.getincrementaldecoder("utf-8")(errors='replace')
            
            # Buffer for filtering startup errors (like Ollama connection issues)
            startup_buffer = ""
            filtering_phase = True
            
            # Read stdout in chunks to ensure real-time updates without freezing UI
            while True:
                if self.cancel_request:
                    process.terminate()
                    break
                
                # Read a chunk of bytes (unbuffered)
                chunk = process.stdout.read(4096)
                
                if not chunk and process.poll() is not None:
                    break
                
                if chunk:
                    text = decoder.decode(chunk, final=False)
                    if not text:
                        continue
                        
                    if filtering_phase:
                        startup_buffer += text
                        
                        # If we have a newline or buffer is getting large, process it
                        if "\n" in startup_buffer or len(startup_buffer) > 1000:
                            # Split into lines to filter
                            lines = startup_buffer.splitlines(keepends=True)
                            
                            # If the last line is incomplete and buffer isn't too huge, keep it
                            pending = ""
                            if not startup_buffer.endswith("\n") and len(startup_buffer) <= 1000:
                                pending = lines.pop()
                            
                            filtered_text = ""
                            for line in lines:
                                # Filter out Ollama connection errors
                                if "Ollama Get" in line and "connectex" in line:
                                    continue
                                filtered_text += line
                            
                            if filtered_text:
                                self.after(0, self._append_output_text, filtered_text)
                            
                            # If we processed lines, we can probably stop filtering, 
                            # unless the error spans multiple lines (unlikely for this specific error)
                            # But to be safe, we'll stop filtering after the first batch of lines
                            # or if we have printed something real.
                            if filtered_text.strip():
                                filtering_phase = False
                                # Output pending immediately if we stop filtering
                                if pending:
                                    self.after(0, self._append_output_text, pending)
                                    pending = ""
                            
                            startup_buffer = pending
                            
                            # If buffer is still growing (no newlines found yet but > 1000 chars),
                            # just dump it to avoid holding back content
                            if len(startup_buffer) > 1000:
                                self.after(0, self._append_output_text, startup_buffer)
                                startup_buffer = ""
                                filtering_phase = False
                    else:
                        # Passthrough mode
                        self.after(0, self._append_output_text, text)
            
            # Flush any remaining bytes
            remaining = decoder.decode(b"", final=True)
            if remaining:
                if filtering_phase and startup_buffer:
                     # Process remaining buffer
                     remaining = startup_buffer + remaining
                self.after(0, self._append_output_text, remaining)
            
            # Wait for writer thread to finish
            writer_thread.join(timeout=1)
            
            if self.cancel_request:
                self.after(0, lambda: self.status_var.set("Cancelled"))
            elif process.returncode != 0:
                # Stderr is already in stdout, so we just check return code
                self.after(0, lambda: self.status_var.set("Completed (with error code)"))
                self.history.update_current_output(full_output)
            else:
                self.after(0, lambda: self.status_var.set("Completed"))
                self.history.update_current_output(full_output)
                
        except Exception as e:
            logger.error(f"Processing error: {e}")
            error_msg = str(e)
            self.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {error_msg}"))
            self.after(0, lambda: self.status_var.set("Error"))
        finally:
            self.after(0, lambda: self.set_ui_state(processing=False))
            self.current_request_thread = None
            self.current_process = None
            
    def _append_output_text(self, text):
        """Append text to the output text widget."""
        self.output_text.configure(state="normal")
        self.output_text.insert("end", text)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")
        
    def save_output(self):
        """Save output to a file."""
        text = self.output_text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Info", "No output to save.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.status_var.set(f"Saved to {os.path.basename(file_path)}")
            except Exception as e:
                logger.error(f"Error saving file: {e}")
                messagebox.showerror("Error", f"Could not save file: {e}")
                
    def copy_output(self):
        """Copy output to clipboard."""
        text = self.output_text.get("1.0", "end-1c")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_var.set("Copied to clipboard")
            
    def clear_output(self):
        """Clear output text."""
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        self.status_var.set("Output cleared")
        
    def paste_input(self):
        """Paste from clipboard to input."""
        try:
            text = self.clipboard_get()
            self.input_text.insert("end", text)
        except:
            pass
            
    def clear_input(self):
        """Clear input text."""
        self.input_text.delete("1.0", "end")
        
    def history_previous(self):
        """Navigate to previous history item."""
        entry = self.history.previous()
        if entry:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", entry["input"])
            self.set_output_text(entry["output"])
            # Also restore the pattern used
            if entry["pattern"] and entry["pattern"] in self.pattern_combo.cget("values"):
                self.pattern_var.set(entry["pattern"])
            self._update_history_buttons()
            
    def history_next(self):
        """Navigate to next history item."""
        entry = self.history.next()
        if entry:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", entry["input"])
            self.set_output_text(entry["output"])
            # Also restore the pattern used
            if entry["pattern"] and entry["pattern"] in self.pattern_combo.cget("values"):
                self.pattern_var.set(entry["pattern"])
            self._update_history_buttons()
            
    def _update_history_buttons(self):
        """Update history navigation button states."""
        self.btn_history_prev.configure(
            state="normal" if self.history.has_previous() else "disabled"
        )
        self.btn_history_next.configure(
            state="normal" if self.history.has_next() else "disabled"
        )
        
    def set_output_text(self, text: str):
        """Set output text widget content."""
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")
        
    def set_ui_state(self, processing: bool):
        """Enable/disable UI elements during processing."""
        state = "disabled" if processing else "normal"
        self.btn_send.configure(state=state)
        self.btn_cancel.configure(state="normal" if processing else "disabled")
        
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {"Content-Type": "application/json"}
        if self.app_config["api_key"]:
            headers["Authorization"] = f"Bearer {self.app_config['api_key']}"
        return headers
        
    def view_logs(self):
        """Open log file."""
        log_file = "fabric_gui.log"
        if os.path.exists(log_file):
            os.startfile(log_file)
        else:
            messagebox.showinfo("Info", "No log file found.")
            
    def show_about(self):
        """Show about dialog."""
        messagebox.showinfo("About", "Fabric Mini GUI\n\nA simple GUI for the Fabric AI framework.")
        
    def save_config(self):
        """Save current configuration."""
        ConfigManager.save(self.app_config)
        
    def on_closing(self):
        """Handle application closing."""
        # Only prompt if the GUI started the server (not an external one)
        if self.server_manager.process is not None and self.server_manager.is_running():
            if messagebox.askyesno("Stop Server", "Stop Fabric server before exiting?"):
                self.server_manager.stop_server()
        
        self.save_config()
        logger.info("Fabric GUI closed")
        self.destroy()

if __name__ == "__main__":
    app = FabricGUI()
    app.mainloop()
