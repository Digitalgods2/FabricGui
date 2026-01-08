"""
Fabric GUI - A desktop client for interacting with Fabric AI patterns.

Windows fixes:
- Fabric server flag is --address (NOT --port). Help shows: --address= (default :8080).
- When starting server, pass address as ':PORT' (e.g. ':8083').
- Auto-migrate older config that still has port_flag='--port' to '--address'.
- Keep base_url and server bind port in sync.
- Capture server stdout so failures show the real reason in logs/UI.
"""

import codecs
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import customtkinter as ctk
import requests

# -----------------------------
# Constants
# -----------------------------

MAX_HISTORY_SIZE = 50
CHUNK_SIZE = 4096
SERVER_HEALTH_CHECK_INTERVAL = 5  # seconds
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

FONT_HEADING = ("Roboto", 14, "bold")
FONT_CODE = ("Consolas", 12)
DEFAULT_WINDOW_SIZE = "900x600"

# -----------------------------
# Help Documentation
# -----------------------------

HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════╗
║                     FABRIC GUI - USER GUIDE                      ║
╚══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHAT IS FABRIC GUI?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fabric GUI is a desktop client for the Fabric AI framework. It provides
a graphical interface to run AI "patterns" - pre-built prompts that
transform your input text using AI models like GPT-4, Claude, etc.

Common use cases:
  • Summarizing articles, transcripts, or documents
  • Extracting key insights from meetings
  • Analyzing and improving writing
  • Generating code explanations
  • And many more patterns...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GETTING STARTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. START THE SERVER
   Click the "Start" button to launch the Fabric server.
   The LED indicator will turn green when ready.

2. SELECT A PATTERN
   Use the Pattern dropdown to choose what you want to do.
   Use the search box to filter patterns by name.

3. ENTER YOUR INPUT
   Paste or type text into the Input panel.
   Use "Import" to load text from a .txt or .md file.

4. CLICK SEND
   The output will appear in the Output panel.
   A pulsing animation shows processing is active.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SERVER MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STATUS LED:
  🔴 Red   = Server offline
  🟢 Green = Server online and ready

BUTTONS:
  [Start] - Launch the Fabric server
  [Stop]  - Shut down the server
  [Test]  - Check server connectivity

BASE URL:
  Default: http://localhost:8083
  The server runs on port 8083 to avoid common conflicts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INPUT/OUTPUT PANELS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT TOOLBAR:
  [Import] - Load text from a file (.txt, .md)
  [Paste]  - Paste from clipboard
  [Clear]  - Clear the input box

OUTPUT TOOLBAR:
  [Copy]   - Copy output to clipboard
  [Save]   - Save output to a file
  [Clear]  - Clear the output box
  [<] [>]  - Navigate through history

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  KEYBOARD SHORTCUTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Ctrl+Enter    Send request
  Ctrl+S        Save output to file
  Ctrl+C        Copy output to clipboard
  Alt+Left      Previous history entry
  Alt+Right     Next history entry

  Right-click any text box for Cut/Copy/Paste/Select All

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HISTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fabric GUI saves your last 50 requests automatically.

Use the [<] and [>] buttons or Alt+Arrow keys to navigate.
History includes the pattern used, input text, and output.
History persists between sessions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MODEL SELECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Model dropdown shows all available AI models grouped by provider.
Click "Default: ..." to reset to your configured default model.

Models are loaded from Fabric's configuration.
You can set your default model using: fabric --setup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Settings are saved automatically to:
  ~/.fabric_gui/config.json

You can manually edit this file to change:
  • auto_start_server: true/false
  • stop_server_on_exit: true/false
  • server_health_check_interval: seconds
  • fabric_command: path to Fabric executable

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  LOGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Logs are saved to: ~/.fabric_gui/fabric_gui.log

Log files rotate automatically:
  • Max size: 5 MB per file
  • Keeps 3 backup files
  • Total max: ~20 MB

View logs: Help → View Logs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Server won't start"
  → Make sure Fabric is installed (fabric --version)
  → Check if port 8083 is available
  → View logs for detailed error messages

"No patterns showing"
  → Start the server first
  → Click "Refresh Patterns"
  → Check server connectivity with "Test"

"Processing seems stuck"
  → Click "Cancel" to abort
  → Some AI models take longer than others
  → Check your internet connection

"Ollama connection errors"
  → This is normal if you don't have Ollama installed
  → These messages are filtered from output
  → Does not affect cloud models (GPT, Claude, etc.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ABOUT FABRIC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fabric is an open-source AI framework by Daniel Miessler.
Learn more: https://github.com/danielmiessler/fabric

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CREDITS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fabric GUI designed and developed by DigitalGods.ai
https://digitalgods.ai

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# -----------------------------
# Logging
# -----------------------------

LOG_DIR = Path.home() / ".fabric_gui"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "fabric_gui.log"

rotating_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[rotating_handler, logging.StreamHandler()],
)
logger = logging.getLogger("fabric_gui")


# -----------------------------
# Config
# -----------------------------

class ConfigManager:
    CONFIG_FILE = LOG_DIR / "config.json"

    DEFAULT_CONFIG = {
        "base_url": "http://localhost:8083",
        "last_pattern": "",
        "last_model": "",
        "window_geometry": DEFAULT_WINDOW_SIZE,
        "auto_start_server": False,
        "stop_server_on_exit": True,
        "server_health_check_interval": SERVER_HEALTH_CHECK_INTERVAL,
        "fabric_command": "fabric",
        # Fabric uses --address= for server bind, not --port
        "port_flag": "--address",
    }

    @classmethod
    def load(cls) -> Dict[str, Any]:
        cfg = cls.DEFAULT_CONFIG.copy()
        changed = False

        try:
            if cls.CONFIG_FILE.exists():
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    disk = json.load(f)
                cfg.update(disk)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

        # Normalize base_url (avoid trailing slash)
        try:
            base_url = str(cfg.get("base_url", "")).strip()
            if base_url.endswith("/"):
                base_url = base_url[:-1]
                cfg["base_url"] = base_url
                changed = True
        except Exception:
            pass

        # Migration: if config still uses old/invalid flag --port, switch to --address
        if str(cfg.get("port_flag", "")).strip() == "--port":
            cfg["port_flag"] = "--address"
            changed = True

        # Migration: if base_url is localhost:8080, bump to 8083 to avoid conflicts
        try:
            parsed = urlparse(str(cfg.get("base_url", "")))
            if parsed.hostname in ("localhost", "127.0.0.1") and (parsed.port is None or parsed.port == 8080):
                cfg["base_url"] = "http://localhost:8083"
                changed = True
        except Exception:
            cfg["base_url"] = "http://localhost:8083"
            changed = True

        if changed:
            cls.save(cfg)

        return cfg

    @classmethod
    def save(cls, config: Dict[str, Any]) -> None:
        try:
            with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")


# -----------------------------
# History
# -----------------------------

class OutputHistory:
    HISTORY_FILE = LOG_DIR / "history.json"

    def __init__(self, max_size: int = MAX_HISTORY_SIZE):
        self.history: List[Dict[str, str]] = []
        self.max_size = max_size
        self.current_index = -1
        self.load()

    def add(self, pattern: str, input_text: str, output_text: str) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "pattern": pattern,
            "input": input_text,
            "output": output_text,
        }
        self.history.append(entry)
        if len(self.history) > self.max_size:
            self.history.pop(0)
        self.current_index = len(self.history) - 1
        self.save()

    def update_current_output(self, output_text: str) -> None:
        if 0 <= self.current_index < len(self.history):
            self.history[self.current_index]["output"] = output_text
            self.save()

    def previous(self) -> Optional[Dict[str, str]]:
        if self.current_index > 0:
            self.current_index -= 1
            return self.history[self.current_index]
        return None

    def next(self) -> Optional[Dict[str, str]]:
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return self.history[self.current_index]
        return None

    def has_previous(self) -> bool:
        return self.current_index > 0

    def has_next(self) -> bool:
        return self.current_index < len(self.history) - 1

    def load(self) -> None:
        try:
            if self.HISTORY_FILE.exists():
                with open(self.HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.history = data.get("history", [])
                if len(self.history) > self.max_size:
                    self.history = self.history[-self.max_size :]
                if self.history:
                    self.current_index = len(self.history) - 1
                logger.info(f"Loaded {len(self.history)} history entries")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            self.history = []
            self.current_index = -1

    def save(self) -> None:
        try:
            with open(self.HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump({"history": self.history}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")


# -----------------------------
# Server Manager
# -----------------------------

class ServerManager:
    def __init__(self, fabric_command: str, base_url: str, port_flag: str):
        self.fabric_command = fabric_command
        self.base_url = self._normalize_base_url(base_url)
        self.port_flag = port_flag.strip() if port_flag else "--address"

        self.process: Optional[subprocess.Popen] = None
        self.is_online = False

        self._health_thread: Optional[threading.Thread] = None
        self._stop_health = False

        self._server_log_thread: Optional[threading.Thread] = None
        self._server_log_stop = False
        self.last_server_lines: List[str] = []

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        url = (url or "").strip()
        if not url:
            raise ValueError("Base URL cannot be empty")
        if url.endswith("/"):
            url = url[:-1]
        return url

    @staticmethod
    def _port_from_base_url(base_url: str) -> int:
        parsed = urlparse(base_url)
        if parsed.port:
            return int(parsed.port)
        if parsed.scheme == "https":
            return 443
        return 80

    def set_base_url(self, base_url: str) -> None:
        self.base_url = self._normalize_base_url(base_url)

    def check_health(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/config", timeout=2)
            healthy = resp.status_code == 200
            self.is_online = healthy
            return healthy
        except Exception:
            self.is_online = False
            return False

    def start_health_monitoring(self, interval: int, callback: Optional[callable] = None) -> None:
        if self._health_thread and self._health_thread.is_alive():
            return

        self._stop_health = False

        def _loop():
            while not self._stop_health:
                online = self.check_health()
                if callback:
                    try:
                        callback(online)
                    except Exception:
                        pass
                time.sleep(max(1, int(interval)))

        self._health_thread = threading.Thread(target=_loop, daemon=True)
        self._health_thread.start()
        logger.info(f"Health monitoring started (interval: {interval}s)")

    def stop_health_monitoring(self) -> None:
        self._stop_health = True
        if self._health_thread:
            self._health_thread.join(timeout=2)

    def _start_server_output_capture(self) -> None:
        if not self.process or not self.process.stdout:
            return

        self._server_log_stop = False
        self.last_server_lines = []

        def _reader():
            try:
                while not self._server_log_stop:
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    line = line.rstrip("\r\n")
                    if not line:
                        continue
                    self.last_server_lines.append(line)
                    if len(self.last_server_lines) > 50:
                        self.last_server_lines.pop(0)
                    logger.info(f"[fabric --serve] {line}")
            except Exception as e:
                logger.error(f"Server output capture error: {e}")

        self._server_log_thread = threading.Thread(target=_reader, daemon=True)
        self._server_log_thread.start()

    def start_server(self) -> bool:
        if self.process and self.process.poll() is None:
            logger.warning("Server is already running")
            return False

        # Safety: if somehow still set to --port, auto-correct at runtime
        if self.port_flag.strip() == "--port":
            self.port_flag = "--address"

        port = self._port_from_base_url(self.base_url)

        try:
            fabric_path = shutil.which(self.fabric_command)
            if not fabric_path:
                logger.error(f"Fabric command not found: {self.fabric_command}")
                return False

            # Fabric expects --address ':PORT' (leading colon)
            address_value = f":{port}"
            cmd = [fabric_path, "--serve", self.port_flag, address_value]
            logger.info(f"Starting Fabric server: {' '.join(cmd)} (base_url={self.base_url})")

            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )

            logger.info(f"Server process started with PID: {self.process.pid}")
            self._start_server_output_capture()

            time.sleep(2)
            if self.process.poll() is not None:
                logger.error("Server process terminated immediately")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False

    def stop_server(self, timeout: int = 5) -> bool:
        if not self.process or self.process.poll() is not None:
            self.process = None
            self.is_online = False
            return True

        try:
            pid = self.process.pid
            logger.info(f"Stopping server (PID: {pid})")

            self._server_log_stop = True

            if os.name == "nt":
                self.process.terminate()
            else:
                self.process.terminate()

            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Server did not stop gracefully, forcing kill")
                self.process.kill()
                self.process.wait()

            self.process = None
            self.is_online = False
            return True

        except Exception as e:
            logger.error(f"Failed to stop server: {e}")
            return False

    def get_patterns(self) -> Optional[List[str]]:
        try:
            resp = requests.get(f"{self.base_url}/patterns/names", timeout=5)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if isinstance(data, list):
                return sorted(data)
            if isinstance(data, dict):
                patterns = data.get("patterns", [])
                if isinstance(patterns, list):
                    return sorted(patterns)
            return []
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return None

    def get_models(self) -> Dict[str, List[str]]:
        try:
            fabric_path = shutil.which(self.fabric_command)
            if not fabric_path:
                return {}

            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [fabric_path, "--listmodels"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            if result.returncode != 0:
                logger.error(f"Failed to list models: {result.stderr.strip()}")
                return {}

            models_by_provider: Dict[str, List[str]] = {}
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^\[\d+\]\s*(.*)$", line)
                if not m:
                    continue
                content = m.group(1).strip()

                if "|" in content:
                    provider, model = content.split("|", 1)
                    provider = provider.strip() or "Other"
                    model = model.strip()
                else:
                    provider = "Other"
                    model = content.strip()

                if not model:
                    continue
                models_by_provider.setdefault(provider, []).append(model)

            for k in list(models_by_provider.keys()):
                models_by_provider[k] = sorted(list(dict.fromkeys(models_by_provider[k])))

            return dict(sorted(models_by_provider.items(), key=lambda kv: kv[0].lower()))

        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return {}

    def get_default_model(self) -> Optional[str]:
        try:
            config_path = Path.home() / ".config" / "fabric" / ".env"
            if not config_path.exists():
                return None
            content = config_path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^DEFAULT_MODEL=(.+)$", content, re.MULTILINE)
            if m:
                return m.group(1).strip()
            return None
        except Exception as e:
            logger.error(f"Error getting default model: {e}")
            return None

    def is_running(self) -> bool:
        return self.is_online


# -----------------------------
# Context Menu
# -----------------------------

class ContextMenu:
    def __init__(self, widget: tk.Widget):
        self.widget = widget
        self.menu = tk.Menu(widget, tearoff=0)
        self.menu.add_command(label="Cut", command=lambda: self._gen("<<Cut>>"))
        self.menu.add_command(label="Copy", command=lambda: self._gen("<<Copy>>"))
        self.menu.add_command(label="Paste", command=lambda: self._gen("<<Paste>>"))
        self.menu.add_separator()
        self.menu.add_command(label="Select All", command=self._select_all)
        widget.bind("<Button-3>", self._show)

    def _gen(self, ev: str) -> None:
        try:
            self.widget.event_generate(ev)
        except Exception:
            pass

    def _select_all(self) -> None:
        try:
            self.widget.focus_force()
            if isinstance(self.widget, tk.Text):
                self.widget.tag_add("sel", "1.0", "end")
            elif isinstance(self.widget, tk.Entry):
                self.widget.select_range(0, "end")
        except Exception:
            pass

    def _show(self, event) -> None:
        try:
            state = str(self.widget.cget("state"))
        except Exception:
            state = "normal"

        readonly = state in ("disabled", "readonly")
        self.menu.entryconfig("Cut", state="disabled" if readonly else "normal")
        self.menu.entryconfig("Paste", state="disabled" if readonly else "normal")

        try:
            _ = self.widget.selection_get()
            has_sel = True
        except Exception:
            has_sel = False

        self.menu.entryconfig("Copy", state="normal" if has_sel else "disabled")
        if not readonly:
            self.menu.entryconfig("Cut", state="normal" if has_sel else "disabled")

        self.menu.tk_popup(event.x_root, event.y_root)


# -----------------------------
# GUI
# -----------------------------

class FabricGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.app_config = ConfigManager.load()
        self.history = OutputHistory()

        # ttk combobox styling
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "TCombobox",
            fieldbackground="#333333",
            background="#333333",
            foreground="white",
            arrowcolor="white",
            bordercolor="#333333",
            font=("Roboto", 12),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#333333")],
            selectbackground=[("readonly", "#1f538d")],
            selectforeground=[("readonly", "white")],
        )
        self.option_add("*TCombobox*Listbox.background", "#333333")
        self.option_add("*TCombobox*Listbox.foreground", "white")
        self.option_add("*TCombobox*Listbox.selectBackground", "#1f538d")
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 14))

        self.server_manager = ServerManager(
            fabric_command=self.app_config["fabric_command"],
            base_url=self.app_config["base_url"],
            port_flag=self.app_config.get("port_flag", "--address"),
        )

        # runtime state
        self.cancel_request = False
        self.current_request_thread: Optional[threading.Thread] = None
        self.current_process: Optional[subprocess.Popen] = None
        
        # Progress animation state
        self._progress_animation_id: Optional[str] = None
        self._progress_dot_count = 0
        self._progress_colors = ["#FFD700", "#FFA500", "#FF8C00", "#FFA500"]  # Gold pulsing
        self._progress_color_index = 0

        # tk vars
        self.base_url_var = tk.StringVar(value=self.app_config["base_url"])
        self.pattern_var = tk.StringVar(value=self.app_config["last_pattern"])
        self.pattern_search_var = tk.StringVar(value="")
        self.model_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.command_var = tk.StringVar(value="")

        self.all_patterns: List[str] = []
        self.last_valid_model = ""

        self.pattern_var.trace_add("write", self._update_command_preview)
        self.model_var.trace_add("write", self._update_command_preview)
        self.pattern_search_var.trace_add("write", self._filter_patterns)

        self.title("Fabric GUI")
        self.geometry(self.app_config.get("window_geometry", DEFAULT_WINDOW_SIZE))
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._build_menu()
        self._build_server_frame()
        self._build_pattern_frame()
        self._build_info_frame()
        self._build_io_frame()
        self._setup_shortcuts()

        self.server_manager.start_health_monitoring(
            interval=int(self.app_config.get("server_health_check_interval", SERVER_HEALTH_CHECK_INTERVAL)),
            callback=self._on_server_status_change,
        )

        if self.app_config.get("auto_start_server", False):
            self.after(600, self.on_start_server)

        self.after(800, self.load_patterns)
        self.after(1200, self.load_models)

        self._update_command_preview()
        logger.info("Fabric GUI started")

    # -----------------------------
    # UI Building
    # -----------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Output...", command=self.save_output, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Copy Output", command=self.copy_output, accelerator="Ctrl+C")
        edit_menu.add_command(label="Clear Output", command=self.clear_output)
        edit_menu.add_separator()
        edit_menu.add_command(label="Paste Input", command=self.paste_input)
        edit_menu.add_command(label="Clear Input", command=self.clear_input)

        history_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="History", menu=history_menu)
        history_menu.add_command(label="Previous", command=self.history_previous, accelerator="Alt+Left")
        history_menu.add_command(label="Next", command=self.history_next, accelerator="Alt+Right")

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="View Logs", command=self.view_logs)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)

    def _build_server_frame(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=5)

        title = ctk.CTkLabel(frame, text="Server Configuration", font=FONT_HEADING)
        title.grid(row=0, column=0, columnspan=10, sticky="w", padx=10, pady=(6, 0))

        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.grid(row=1, column=0, columnspan=10, sticky="ew", padx=5, pady=6)

        led_frame = ctk.CTkFrame(content, fg_color="transparent")
        led_frame.pack(side="left", padx=5)

        ctk.CTkLabel(led_frame, text="Status:").pack(side="left", padx=(0, 5))
        self.status_led = tk.Canvas(led_frame, width=20, height=20, highlightthickness=0, bg="black")
        self.status_led.pack(side="left")
        self.led_indicator = self.status_led.create_oval(2, 2, 18, 18, fill="red", outline="darkred")
        self._create_tooltip(self.status_led, "Server: Offline")

        ctk.CTkLabel(content, text="Base URL:").pack(side="left", padx=5)
        self.entry_url = ctk.CTkEntry(content, textvariable=self.base_url_var, width=280)
        self.entry_url.pack(side="left", padx=5)
        ContextMenu(self.entry_url)

        btn_test = ctk.CTkButton(content, text="Test", command=self.on_test_server, width=70)
        btn_test.pack(side="left", padx=5)

        self.btn_start_server = ctk.CTkButton(content, text="Start", command=self.on_start_server, width=70)
        self.btn_start_server.pack(side="left", padx=5)

        self.btn_stop_server = ctk.CTkButton(content, text="Stop", command=self.on_stop_server, width=70, state="disabled")
        self.btn_stop_server.pack(side="left", padx=5)

    def _build_pattern_frame(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frame, text="Pattern Selection", font=FONT_HEADING).grid(
            row=0, column=0, columnspan=6, sticky="w", padx=10, pady=(6, 0)
        )

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.grid(row=1, column=0, columnspan=6, sticky="ew", padx=5, pady=(6, 0))

        ctk.CTkLabel(search_frame, text="Search:", width=60, anchor="e").pack(side="left", padx=5)
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.pattern_search_var, placeholder_text="Filter patterns...", height=36, font=("Segoe UI", 14))
        search_entry.pack(side="left", padx=5, fill="x", expand=True)

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.grid(row=2, column=0, columnspan=6, sticky="ew", padx=5, pady=6)

        ctk.CTkLabel(row2, text="Pattern:", width=60, anchor="e").pack(side="left", padx=5)

        self.pattern_combo = ttk.Combobox(row2, textvariable=self.pattern_var, width=45, state="readonly", height=20, font=("Segoe UI", 14))
        self.pattern_combo.pack(side="left", padx=5, fill="x", expand=True, ipady=6)

        btn_refresh = ctk.CTkButton(row2, text="Refresh Patterns", command=self.load_patterns)
        btn_refresh.pack(side="left", padx=5)

        model_row = ctk.CTkFrame(frame, fg_color="transparent")
        model_row.grid(row=3, column=0, columnspan=6, sticky="ew", padx=5, pady=(0, 8))

        ctk.CTkLabel(model_row, text="Model:", width=60, anchor="e").pack(side="left", padx=5)

        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var, width=45, state="readonly", height=20, font=("Segoe UI", 14))
        self.model_combo.pack(side="left", padx=5, fill="x", expand=True, ipady=6)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_selected)

        self.default_model_label = ctk.CTkLabel(model_row, text="Default: (loading...)", text_color="gray", cursor="hand2")
        self.default_model_label.pack(side="left", padx=8)
        self.default_model_label.bind("<Button-1>", lambda e: self.reset_model_selection())

        frame.columnconfigure(0, weight=1)

    def _build_info_frame(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=5)

        left = ctk.CTkFrame(frame, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=5, pady=6)

        ctk.CTkLabel(left, text="Status", font=FONT_HEADING).pack(anchor="w")
        self.status_label = ctk.CTkLabel(left, textvariable=self.status_var, font=("Segoe UI", 14, "bold"))
        self.status_label.pack(fill="x", pady=(2, 0))

        mid = ctk.CTkFrame(frame, fg_color="transparent")
        mid.pack(side="left", fill="x", expand=True, padx=5, pady=6)

        ctk.CTkLabel(mid, text="Command Preview", font=FONT_HEADING).pack(anchor="w")
        cmd_entry = ctk.CTkEntry(mid, textvariable=self.command_var, state="readonly", font=FONT_CODE, height=36)
        cmd_entry.pack(fill="x", pady=(2, 0))

        right = ctk.CTkFrame(frame, fg_color="transparent")
        right.pack(side="left", padx=5, pady=6)

        ctk.CTkLabel(right, text="Actions", font=FONT_HEADING).pack(anchor="w")

        btns = ctk.CTkFrame(right, fg_color="transparent")
        btns.pack(fill="x", pady=(2, 0))

        self.btn_cancel = ctk.CTkButton(btns, text="Cancel", command=self.on_cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=2)

        self.btn_send = ctk.CTkButton(btns, text="Send", command=self.on_send, width=110, fg_color="green", hover_color="darkgreen")
        self.btn_send.pack(side="left", padx=2)

    def _build_io_frame(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ctk.CTkLabel(input_frame, text="Input", font=FONT_HEADING).pack(anchor="w")

        input_toolbar = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_toolbar.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(input_toolbar, text="Import", command=self.import_file, width=70).pack(side="left", padx=2)
        ctk.CTkButton(input_toolbar, text="Paste", command=self.paste_input, width=70).pack(side="left", padx=2)
        ctk.CTkButton(input_toolbar, text="Clear", command=self.clear_input, width=70).pack(side="left", padx=2)

        self.input_text = ctk.CTkTextbox(input_frame, wrap="word", font=("Consolas", 14))
        self.input_text.pack(fill="both", expand=True, padx=2, pady=2)
        ContextMenu(self.input_text._textbox)

        output_frame = ctk.CTkFrame(frame, fg_color="transparent")
        output_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        ctk.CTkLabel(output_frame, text="Output", font=FONT_HEADING).pack(anchor="w")

        output_toolbar = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_toolbar.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(output_toolbar, text="Copy", command=self.copy_output, width=70).pack(side="left", padx=2)
        ctk.CTkButton(output_toolbar, text="Save", command=self.save_output, width=70).pack(side="left", padx=2)
        ctk.CTkButton(output_toolbar, text="Clear", command=self.clear_output, width=70).pack(side="left", padx=2)

        sep = ctk.CTkFrame(output_toolbar, width=2, height=20, fg_color="gray50")
        sep.pack(side="left", padx=8)

        self.btn_history_prev = ctk.CTkButton(output_toolbar, text="<", command=self.history_previous, width=36)
        self.btn_history_prev.pack(side="left", padx=2)

        self.btn_history_next = ctk.CTkButton(output_toolbar, text=">", command=self.history_next, width=36)
        self.btn_history_next.pack(side="left", padx=2)

        self.output_text = ctk.CTkTextbox(output_frame, wrap="word", font=("Consolas", 14))
        self.output_text.pack(fill="both", expand=True, padx=2, pady=2)
        self.output_text.configure(state="disabled")
        ContextMenu(self.output_text._textbox)

        self._update_history_buttons()

    def _setup_shortcuts(self) -> None:
        self.bind("<Control-s>", lambda e: self.save_output())
        self.bind("<Control-c>", lambda e: self.copy_output())
        self.bind("<Alt-Left>", lambda e: self.history_previous())
        self.bind("<Alt-Right>", lambda e: self.history_next())
        self.bind("<Control-Return>", lambda e: self.on_send())

    # -----------------------------
    # Tooltip
    # -----------------------------

    def _create_tooltip(self, widget, text: str) -> None:
        widget.tooltip_text = text

        def on_enter(event):
            t = getattr(widget, "tooltip_text", "")
            if not t:
                return
            tip = tk.Toplevel()
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tip, text=t, background="lightyellow", relief="solid", borderwidth=1)
            label.pack()
            widget._tooltip = tip

        def on_leave(event):
            tip = getattr(widget, "_tooltip", None)
            if tip:
                try:
                    tip.destroy()
                except Exception:
                    pass
                widget._tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _update_tooltip_text(self, widget, text: str) -> None:
        widget.tooltip_text = text

    # -----------------------------
    # Core Helpers
    # -----------------------------

    def _normalize_base_url_from_entry(self) -> str:
        url = (self.base_url_var.get() or "").strip()
        if not url:
            raise ValueError("Base URL cannot be empty")
        if not url.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        if any(c in url for c in [" ", "\n", "\r", "\t"]):
            raise ValueError("Base URL cannot contain whitespace")
        if url.endswith("/"):
            url = url[:-1]
        self.base_url_var.set(url)
        return url

    def _sync_server_manager_from_ui(self) -> None:
        base_url = self._normalize_base_url_from_entry()
        self.server_manager.set_base_url(base_url)

    def _save_config_from_ui(self) -> None:
        # Always persist corrected flag
        if self.app_config.get("port_flag", "").strip() == "--port":
            self.app_config["port_flag"] = "--address"

        self.app_config["base_url"] = self.base_url_var.get().strip()
        self.app_config["last_pattern"] = self.pattern_var.get()
        self.app_config["last_model"] = (self.model_var.get().strip() if self.model_var.get().startswith("  ") else "")
        self.app_config["window_geometry"] = self.geometry()
        self.app_config["fabric_command"] = self.app_config.get("fabric_command", "fabric")
        self.app_config["port_flag"] = self.app_config.get("port_flag", "--address")
        ConfigManager.save(self.app_config)

        # Keep runtime manager in sync with persisted flag too
        self.server_manager.port_flag = self.app_config["port_flag"]

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.update_idletasks()
        logger.info(f"Status: {text}")

    def _set_output_text(self, text: str) -> None:
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")

    def _append_output_text(self, text: str) -> None:
        self.output_text.configure(state="normal")
        self.output_text.insert("end", text)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def _set_ui_processing(self, processing: bool) -> None:
        self.btn_send.configure(state="disabled" if processing else "normal")
        self.btn_cancel.configure(state="normal" if processing else "disabled")
        
        if processing:
            self._start_progress_animation()
        else:
            self._stop_progress_animation()

    def _start_progress_animation(self) -> None:
        """Start the animated processing indicator."""
        self._progress_dot_count = 0
        self._progress_color_index = 0
        self._animate_progress()

    def _stop_progress_animation(self) -> None:
        """Stop the animated processing indicator."""
        if self._progress_animation_id:
            self.after_cancel(self._progress_animation_id)
            self._progress_animation_id = None
        # Reset status label color to default
        try:
            self.status_label.configure(text_color=("gray10", "gray90"))
        except Exception:
            pass

    def _animate_progress(self) -> None:
        """Animate the processing status with pulsing dots and color."""
        if not hasattr(self, 'status_label'):
            return
            
        # Update dots: Processing. -> Processing.. -> Processing... -> Processing
        self._progress_dot_count = (self._progress_dot_count + 1) % 4
        dots = "." * self._progress_dot_count if self._progress_dot_count > 0 else ""
        self.status_var.set(f"Processing{dots}")
        
        # Pulse color
        self._progress_color_index = (self._progress_color_index + 1) % len(self._progress_colors)
        color = self._progress_colors[self._progress_color_index]
        try:
            self.status_label.configure(text_color=color)
        except Exception:
            pass
        
        # Schedule next animation frame (300ms for smooth but not too fast)
        self._progress_animation_id = self.after(300, self._animate_progress)

    def _update_history_buttons(self) -> None:
        self.btn_history_prev.configure(state="normal" if self.history.has_previous() else "disabled")
        self.btn_history_next.configure(state="normal" if self.history.has_next() else "disabled")

    # -----------------------------
    # Server UI Actions
    # -----------------------------

    def on_test_server(self) -> None:
        try:
            self._sync_server_manager_from_ui()
            self._save_config_from_ui()

            ok = self.server_manager.check_health()
            if ok:
                messagebox.showinfo("Success", "Connected to Fabric server successfully.")
                self._on_server_status_change(True)
            else:
                messagebox.showerror("Error", "Could not connect to Fabric server.\nCheck Base URL and whether the server is running.")
                self._on_server_status_change(False)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_start_server(self) -> None:
        try:
            self.btn_start_server.configure(state="disabled")
            self._sync_server_manager_from_ui()
            self._save_config_from_ui()

            self._set_status("Starting server...")
            success = self.server_manager.start_server()
            if not success:
                self._set_status("Failed to start server")

                tail = "\n".join(self.server_manager.last_server_lines[-20:])
                if tail.strip():
                    messagebox.showerror("Fabric server failed to start", f"Fabric exited immediately.\n\nLast output:\n{tail}")
                else:
                    messagebox.showerror("Fabric server failed to start", "Fabric exited immediately.\n\nNo output captured. Check logs.")
                self.btn_start_server.configure(state="normal")
                return

            self.after(800, self.load_patterns)
            self._set_status("Server started")
            self.btn_stop_server.configure(state="normal")

        except Exception as e:
            logger.error(f"Start server error: {e}")
            self._set_status("Error starting server")
            messagebox.showerror("Error", str(e))
            self.btn_start_server.configure(state="normal")

    def on_stop_server(self) -> None:
        if not messagebox.askyesno("Confirm", "Stop the Fabric server?"):
            return
        self._set_status("Stopping server...")
        ok = self.server_manager.stop_server()
        if ok:
            self._set_status("Server stopped")
            self._on_server_status_change(False)
        else:
            self._set_status("Failed to stop server")
            messagebox.showerror("Error", "Failed to stop server. Check logs.")
            self.btn_stop_server.configure(state="normal")

    def _on_server_status_change(self, is_online: bool) -> None:
        self.after(0, lambda: self._update_led_status(is_online))

    def _update_led_status(self, is_online: bool) -> None:
        if is_online:
            self.status_led.itemconfig(self.led_indicator, fill="green", outline="darkgreen")
            self._update_tooltip_text(self.status_led, f"Server: Online ({self.server_manager.base_url})")
            self.btn_start_server.configure(state="disabled")
            self.btn_stop_server.configure(state="normal")
        else:
            self.status_led.itemconfig(self.led_indicator, fill="red", outline="darkred")
            self._update_tooltip_text(self.status_led, f"Server: Offline ({self.server_manager.base_url})")
            self.btn_start_server.configure(state="normal")
            self.btn_stop_server.configure(state="disabled")

    # -----------------------------
    # Patterns / Models
    # -----------------------------

    def _filter_patterns(self, *args) -> None:
        if not self.all_patterns:
            return
        needle = (self.pattern_search_var.get() or "").strip().lower()
        if not needle:
            self.pattern_combo.configure(values=self.all_patterns)
            return
        filtered = [p for p in self.all_patterns if needle in p.lower()]
        self.pattern_combo.configure(values=filtered if filtered else ["No matches found"])

    def load_patterns(self) -> None:
        try:
            self._sync_server_manager_from_ui()
            patterns = self.server_manager.get_patterns()
            if patterns is None:
                self.all_patterns = []
                self.pattern_combo.configure(values=["Server Offline / Error"])
                return

            if not patterns:
                self.all_patterns = []
                self.pattern_combo.configure(values=["No patterns found"])
                return

            self.all_patterns = patterns
            self._filter_patterns()

            last = self.app_config.get("last_pattern", "")
            values = list(self.pattern_combo.cget("values") or [])
            if last and last in values:
                self.pattern_var.set(last)
            elif values and values[0] not in ("No matches found", "No patterns found", "Server Offline / Error"):
                if not self.pattern_var.get():
                    self.pattern_var.set(values[0])

        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
            self.pattern_combo.configure(values=["Error loading patterns"])

    def load_models(self) -> None:
        try:
            models_by_provider = self.server_manager.get_models()
            if not models_by_provider:
                self.model_combo.configure(values=["Error loading models"])
                return

            display: List[str] = []
            for provider, models in models_by_provider.items():
                display.append(provider)
                for m in models:
                    display.append(f"  {m}")

            self.model_combo.configure(values=display)

            default_model = self.server_manager.get_default_model()
            if default_model:
                self.default_model_label.configure(text=f"Default: {default_model}")
            else:
                self.default_model_label.configure(text="Default: (System Default)")

            last_model = self.app_config.get("last_model", "")
            if last_model and f"  {last_model}" in display:
                self.model_var.set(f"  {last_model}")
                self.last_valid_model = f"  {last_model}"

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            self.model_combo.configure(values=["Error loading models"])

    def _on_model_selected(self, event) -> None:
        sel = self.model_var.get()
        if sel and not sel.startswith("  "):
            self.model_var.set(self.last_valid_model)
            return
        self.last_valid_model = sel
        self._update_command_preview()

    def reset_model_selection(self) -> None:
        self.model_var.set("")
        self.last_valid_model = ""
        self._update_command_preview()
        self._set_status("Model reset to default")

    def _update_command_preview(self, *args) -> None:
        cmd = self.app_config.get("fabric_command", "fabric")
        pattern = self.pattern_var.get().strip()
        if pattern:
            cmd += f" -p {pattern}"
        model_sel = self.model_var.get()
        if model_sel and model_sel.startswith("  "):
            cmd += f" -m {model_sel.strip()}"
        self.command_var.set(cmd)

    # -----------------------------
    # Request Execution (Fabric CLI)
    # -----------------------------

    def on_send(self, event=None) -> None:
        input_text = self.input_text.get("1.0", "end-1c")
        if not input_text.strip():
            messagebox.showwarning("Warning", "Please enter some text to process.")
            return

        try:
            self._sync_server_manager_from_ui()
            self._save_config_from_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        if not self.server_manager.is_running():
            if messagebox.askyesno("Server Offline", "Fabric server appears offline. Start it now?"):
                self.on_start_server()
                self.after(1500, lambda: self.on_send(event))
            return

        self._set_ui_processing(True)
        self.status_var.set("Processing...")
        self._set_output_text("")

        self.history.add(self.pattern_var.get(), input_text, "")

        self.cancel_request = False
        self.current_request_thread = threading.Thread(target=self._process_request, args=(input_text,), daemon=True)
        self.current_request_thread.start()

    def on_cancel(self) -> None:
        if self.current_request_thread and self.current_request_thread.is_alive():
            self.cancel_request = True
            self.status_var.set("Cancelling...")
            self.btn_cancel.configure(state="disabled")
            try:
                if self.current_process and self.current_process.poll() is None:
                    self.current_process.terminate()
            except Exception:
                pass

    def _should_filter_line(self, line: str) -> bool:
        if "Ollama Get" in line and "connectex" in line:
            return True
        return False

    def _process_request(self, input_text: str) -> None:
        try:
            pattern = self.pattern_var.get().strip()
            if not pattern:
                self.after(0, lambda: messagebox.showwarning("Warning", "Please select a pattern."))
                self.after(0, lambda: self._set_ui_processing(False))
                return

            self.app_config["last_pattern"] = pattern
            model_selection = self.model_var.get()
            if model_selection and model_selection.startswith("  "):
                self.app_config["last_model"] = model_selection.strip()
            else:
                self.app_config["last_model"] = ""

            self._save_config_from_ui()

            fabric_cmd = self.app_config.get("fabric_command", "fabric")
            cmd = [fabric_cmd, "-p", pattern]
            if model_selection and model_selection.startswith("  "):
                cmd.extend(["-m", model_selection.strip()])

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=0,
                env=env,
                creationflags=creationflags,
            )
            self.current_process = process

            def _write_input():
                try:
                    if process.stdin:
                        process.stdin.write(input_text.encode("utf-8"))
                        process.stdin.flush()
                        process.stdin.close()
                except Exception as e:
                    logger.error(f"Error writing stdin: {e}")

            threading.Thread(target=_write_input, daemon=True).start()

            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

            full_output = ""
            line_buffer = ""

            while True:
                if self.cancel_request:
                    break

                chunk = b""
                try:
                    if process.stdout:
                        chunk = process.stdout.read(CHUNK_SIZE)
                except Exception:
                    chunk = b""

                if not chunk and process.poll() is not None:
                    break

                if chunk:
                    text = decoder.decode(chunk, final=False)
                    if not text:
                        continue

                    line_buffer += text
                    while "\n" in line_buffer:
                        line, line_buffer = line_buffer.split("\n", 1)
                        line = line + "\n"
                        if self._should_filter_line(line):
                            continue
                        full_output += line
                        self.after(0, self._append_output_text, line)

            remaining = decoder.decode(b"", final=True)
            if remaining:
                line_buffer += remaining

            if line_buffer and not self._should_filter_line(line_buffer):
                full_output += line_buffer
                self.after(0, self._append_output_text, line_buffer)

            if self.cancel_request:
                self.after(0, lambda: self.status_var.set("Cancelled"))
            else:
                rc = process.poll()
                if rc and rc != 0:
                    self.after(0, lambda: self.status_var.set(f"Completed (error code {rc})"))
                else:
                    self.after(0, lambda: self.status_var.set("Completed"))

            self.history.update_current_output(full_output)

        except Exception as e:
            logger.error(f"Processing error: {e}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.status_var.set("Error"))
        finally:
            try:
                if self.current_process and self.current_process.poll() is None:
                    self.current_process.terminate()
                    try:
                        self.current_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.current_process.kill()
                        self.current_process.wait(timeout=2)
            except Exception:
                pass

            try:
                if self.current_process and self.current_process.stdout:
                    self.current_process.stdout.close()
            except Exception:
                pass
            try:
                if self.current_process and self.current_process.stdin:
                    self.current_process.stdin.close()
            except Exception:
                pass

            self.current_process = None
            self.after(0, lambda: self._set_ui_processing(False))

    # -----------------------------
    # Output/Input Utilities
    # -----------------------------

    def save_output(self) -> None:
        text = self.output_text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Info", "No output to save.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(text, encoding="utf-8")
            self.status_var.set(f"Saved to {Path(file_path).name}")
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            messagebox.showerror("Error", str(e))

    def copy_output(self) -> None:
        text = self.output_text.get("1.0", "end-1c")
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Copied to clipboard")

    def clear_output(self) -> None:
        self._set_output_text("")
        self.status_var.set("Output cleared")

    def paste_input(self) -> None:
        try:
            text = self.clipboard_get()
            self.input_text.insert("end", text)
        except Exception:
            pass

    def clear_input(self) -> None:
        self.input_text.delete("1.0", "end")

    def import_file(self) -> None:
        """Import text from a .txt or .md file into the input box."""
        file_path = filedialog.askopenfilename(
            title="Import Text File",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All supported", "*.txt;*.md"),
            ],
            defaultextension=".txt",
        )
        if not file_path:
            return
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            # Clear existing content and insert new
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", content)
            
            # Show filename in status
            filename = Path(file_path).name
            self._set_status(f"Imported: {filename}")
            logger.info(f"Imported file: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to import file: {e}")
            messagebox.showerror("Import Error", f"Failed to import file:\n{e}")

    # -----------------------------
    # History Navigation
    # -----------------------------

    def _load_history_entry(self, entry: Optional[Dict[str, str]]) -> None:
        """Load a history entry into the UI."""
        if not entry:
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", entry.get("input", ""))
        self._set_output_text(entry.get("output", ""))
        pat = entry.get("pattern", "")
        if pat and pat in (self.pattern_combo.cget("values") or []):
            self.pattern_var.set(pat)
        self._update_history_buttons()

    def history_previous(self) -> None:
        self._load_history_entry(self.history.previous())

    def history_next(self) -> None:
        self._load_history_entry(self.history.next())

    # -----------------------------
    # Help / About
    # -----------------------------

    def view_logs(self) -> None:
        if LOG_FILE.exists():
            try:
                os.startfile(str(LOG_FILE))
            except Exception:
                messagebox.showinfo("Logs", str(LOG_FILE))
        else:
            messagebox.showinfo("Info", "No log file found.")

    def show_about(self) -> None:
        messagebox.showinfo("About", "Fabric GUI v3.2\n\nA desktop client for the Fabric AI framework.\n\nBuilt with Python and CustomTkinter.")

    def show_help(self) -> None:
        """Display the comprehensive help dialog."""
        help_window = ctk.CTkToplevel(self)
        help_window.title("Fabric GUI - User Guide")
        help_window.geometry("700x600")
        help_window.transient(self)
        help_window.grab_set()
        
        # Center the window
        help_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 350
        y = self.winfo_y() + (self.winfo_height() // 2) - 300
        help_window.geometry(f"+{x}+{y}")
        
        # Create scrollable text area
        help_text = ctk.CTkTextbox(
            help_window,
            wrap="word",
            font=("Consolas", 12),
            fg_color=("gray95", "gray10"),
        )
        help_text.pack(fill="both", expand=True, padx=10, pady=10)
        help_text.insert("1.0", HELP_TEXT)
        help_text.configure(state="disabled")
        
        # Close button
        close_btn = ctk.CTkButton(
            help_window,
            text="Close",
            command=help_window.destroy,
            width=100,
        )
        close_btn.pack(pady=(0, 10))

    # -----------------------------
    # Closing
    # -----------------------------

    def on_closing(self) -> None:
        try:
            self._save_config_from_ui()
        except Exception:
            pass

        try:
            if self.app_config.get("stop_server_on_exit", True):
                self.server_manager.stop_server()
        except Exception:
            pass

        try:
            self.server_manager.stop_health_monitoring()
        except Exception:
            pass

        logger.info("Fabric GUI closed")
        self.destroy()


if __name__ == "__main__":
    app = FabricGUI()
    app.mainloop()
