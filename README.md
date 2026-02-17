<p align="center">
  <h1 align="center">🧵 Fabric Mini GUI</h1>
  <p align="center">
    A modern desktop client for interacting with <a href="https://github.com/danielmiessler/fabric">Fabric</a> AI patterns
    <br />
    Built with <strong>CustomTkinter</strong> for a sleek, dark-mode friendly experience
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/gui-CustomTkinter-green" />
  <img src="https://img.shields.io/badge/version-3.2-orange" />
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" />
</p>

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [System Architecture](#system-architecture)
  - [Class Diagram](#class-diagram)
  - [Request Processing Flow](#request-processing-flow)
  - [Server Lifecycle](#server-lifecycle)
  - [Application Startup Sequence](#application-startup-sequence)
  - [GUI Layout Structure](#gui-layout-structure)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [First Time Setup](#first-time-setup)
  - [Sending Requests](#sending-requests)
  - [Managing Output](#managing-output)
  - [Managing the Server](#managing-the-server)
  - [Cancelling Requests](#cancelling-requests)
- [Configuration](#configuration)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Menu Reference](#menu-reference)
- [Project Structure](#project-structure)
- [Logging](#logging)
- [Troubleshooting](#troubleshooting)
- [Version History](#version-history)
- [Contributing](#contributing)
- [Credits](#credits)

---

## Overview

**Fabric Mini GUI** provides a graphical desktop interface for the [Fabric](https://github.com/danielmiessler/fabric) AI framework by Daniel Miessler. Instead of using the Fabric CLI directly, you get a modern dark-mode window where you can:

- Browse and search AI patterns visually
- Select from all your configured AI models (Claude, GPT-4, Ollama, etc.)
- Stream AI responses in real-time
- Manage the Fabric server with start/stop controls and live health monitoring
- Navigate through your response history

The entire application is a single Python file (`fabricgui.py`) with only two dependencies: `requests` and `customtkinter`.

---

## Architecture

### System Architecture

High-level view of how Fabric GUI interacts with the Fabric ecosystem:

```mermaid
graph TB
    subgraph FabricGUI["🖥️ Fabric GUI Application"]
        GUI["FabricGUI<br/>(Main Window)"]
        CM["ConfigManager"]
        OH["OutputHistory"]
        SM["ServerManager"]
        PD["PreferencesDialog"]
        CTX["ContextMenu"]
    end

    subgraph FabricCLI["⚙️ Fabric CLI"]
        SERVE["fabric --serve"]
        PATTERN["fabric -p pattern"]
    end

    subgraph Providers["☁️ AI Providers"]
        CLAUDE["Claude"]
        GPT["GPT-4"]
        OLLAMA["Ollama"]
        OTHER["Other LLMs"]
    end

    subgraph Storage["💾 Local Storage"]
        CFG["~/.fabric_gui/config.json"]
        HIST["~/.fabric_gui/history.json"]
        LOG["~/.fabric_gui/fabric_gui.log"]
        FENV["~/.config/fabric/.env"]
    end

    GUI -->|"Manages"| SM
    GUI -->|"Reads/Writes"| CM
    GUI -->|"Navigates"| OH
    GUI -->|"Opens"| PD
    GUI -->|"Attaches to text widgets"| CTX

    SM -->|"Starts/Stops"| SERVE
    SM -->|"GET /patterns/names"| SERVE
    SM -->|"GET /models/names"| SERVE
    SM -->|"Health checks"| SERVE

    GUI -->|"Spawns subprocess"| PATTERN
    PATTERN -->|"stdin: user text"| PATTERN
    PATTERN -->|"stdout: AI response"| GUI

    SERVE -->|"Routes to"| CLAUDE
    SERVE -->|"Routes to"| GPT
    SERVE -->|"Routes to"| OLLAMA
    SERVE -->|"Routes to"| OTHER

    CM -->|"Persists"| CFG
    OH -->|"Persists"| HIST
    GUI -->|"Logs to"| LOG
    SM -->|"Reads default model"| FENV

    style FabricGUI fill:#1a1a2e,stroke:#16213e,color:#e94560
    style FabricCLI fill:#0f3460,stroke:#16213e,color:#e94560
    style Providers fill:#533483,stroke:#16213e,color:#e94560
    style Storage fill:#2b2b2b,stroke:#444,color:#ccc
```

### Class Diagram

Detailed view of all classes, their fields, and relationships:

```mermaid
classDiagram
    class ConfigManager {
        <<static>>
        +Path CONFIG_FILE
        +dict DEFAULT_CONFIG
        +load() Dict~str, Any~
        +save(config: Dict) void
    }

    class OutputHistory {
        +Path HISTORY_FILE
        -List~Dict~ history
        -int max_size
        -int current_index
        +__init__(max_size: int)
        +add(pattern, input_text, output_text)
        +update_current_output(output_text)
        +previous() Optional~Dict~
        +next() Optional~Dict~
        +has_previous() bool
        +has_next() bool
        +load() void
        +save() void
    }

    class ServerManager {
        -str fabric_command
        -str base_url
        -str port_flag
        -Popen process
        -bool is_online
        -bool _monitoring
        -Thread _health_thread
        +__init__(fabric_command, base_url, port_flag)
        +check_health() bool
        +start_health_monitoring(interval, callback)
        +stop_health_monitoring()
        +start_server() bool
        +stop_server(timeout) bool
        +get_patterns() Optional~List~
        +get_models() Dict~str, List~
        +get_default_model() Optional~str~
        +is_running() bool
        -_normalize_base_url(url) str
        -_port_from_base_url(base_url) str
        -_start_server_output_capture()
    }

    class ContextMenu {
        -Widget widget
        -Menu menu
        +__init__(widget: Widget)
        -_gen(ev: str) void
        -_select_all() void
        -_show(event) void
    }

    class PreferencesDialog {
        -CTk parent
        -Dict config
        -Optional~Dict~ result
        -StringVar base_url_var
        -BooleanVar auto_start_var
        -BooleanVar stop_on_exit_var
        -StringVar health_interval_var
        -StringVar fabric_cmd_var
        -StringVar timeout_var
        +__init__(parent, config)
        -_build_ui()
        -_build_server_tab()
        -_build_advanced_tab()
        -_validate_and_collect() Optional~Dict~
        -_on_save()
        -_on_cancel()
    }

    class FabricGUI {
        -Dict app_config
        -OutputHistory history
        -ServerManager server_manager
        -bool cancel_request
        -Thread current_request_thread
        -Popen current_process
        -StringVar base_url_var
        -StringVar pattern_var
        -StringVar model_var
        -StringVar status_var
        -StringVar command_var
        -List~str~ all_patterns
        +__init__()
        -_build_menu()
        -_build_server_frame()
        -_build_pattern_frame()
        -_build_info_frame()
        -_build_io_frame()
        -_setup_shortcuts()
        +on_send(event)
        +on_cancel()
        +on_start_server()
        +on_stop_server()
        +on_test_server()
        +load_patterns()
        +load_models()
        +save_output()
        +copy_output()
        +clear_output()
        +import_file()
        +show_preferences()
        +show_help()
        +on_closing()
        -_process_request(input_text)
        -_filter_patterns(*args)
        -_update_led_status(is_online)
        -_set_ui_processing(processing)
        -_animate_progress()
    }

    FabricGUI --> ConfigManager : loads/saves config
    FabricGUI --> OutputHistory : manages history
    FabricGUI --> ServerManager : controls server
    FabricGUI --> ContextMenu : attaches to text widgets
    FabricGUI --> PreferencesDialog : opens dialog
    FabricGUI --|> CTk : inherits
    PreferencesDialog --|> CTkToplevel : inherits
```

### Request Processing Flow

Step-by-step view of what happens when the user clicks **Send**:

```mermaid
flowchart TD
    A["👤 User clicks Send<br/>(or Ctrl+Enter)"] --> B{"Pattern<br/>selected?"}
    B -->|No| C["⚠️ Show warning:<br/>Please select a pattern"]
    B -->|Yes| D{"Server<br/>online?"}

    D -->|No| E["🔌 Prompt: Start server?"]
    E -->|No| F["❌ Cancel"]
    E -->|Yes| G["🚀 Start server<br/>Wait for health check"]
    G --> H

    D -->|Yes| H["💾 Save config<br/>(pattern, model, URL)"]
    H --> I["🔧 Build command:<br/>fabric -p pattern [-m model]"]
    I --> J["🔒 Disable Send button<br/>Enable Cancel button<br/>Start progress animation"]
    J --> K["📤 Spawn subprocess<br/>(CREATE_NO_WINDOW on Windows)"]
    K --> L["📝 Write input text to stdin<br/>(in background thread)"]
    L --> M["📖 Add history entry"]

    M --> N{"Read stdout<br/>chunk"}
    N -->|Chunk received| O{"Cancel<br/>requested?"}
    O -->|Yes| P["🛑 Terminate process"]
    O -->|No| Q{"Filter<br/>line?"}
    Q -->|Yes: Ollama noise| N
    Q -->|No| R["📺 Append to output<br/>(via self.after)"]
    R --> N

    N -->|EOF + process done| S["✅ Update status:<br/>Completed"]
    S --> T["💾 Save history"]
    T --> U["🔓 Re-enable Send<br/>Disable Cancel<br/>Stop animation"]

    P --> V["📝 Set status: Cancelled"]
    V --> U

    style A fill:#1f6aa5,color:#fff
    style C fill:#cc6600,color:#fff
    style F fill:#cc3333,color:#fff
    style P fill:#cc3333,color:#fff
    style S fill:#2d8f2d,color:#fff
```

### Server Lifecycle

How `ServerManager` controls the Fabric server process:

```mermaid
stateDiagram-v2
    [*] --> Offline : App starts

    Offline --> Starting : on_start_server()
    Starting --> Online : Health check passes
    Starting --> Offline : Process exited immediately

    Online --> Online : Health check (every 5s) ✓
    Online --> Offline : Health check fails
    Online --> Stopping : on_stop_server()

    Stopping --> Offline : Process terminated
    Stopping --> Offline : Force kill (after timeout)

    Offline --> Online : Auto-start on launch
    Offline --> Prompted : Send request while offline
    Prompted --> Starting : User says "Yes"
    Prompted --> Offline : User says "No"

    state Online {
        [*] --> Healthy
        Healthy --> Healthy : GET /readyz → 200
        Healthy --> Degraded : Request fails
        Degraded --> Healthy : Next check passes
    }

    note right of Starting
        Command: fabric --serve --address :PORT
        Creates new process group (Windows)
        Captures stdout in background thread
        Waits 2s for process stability
    end note

    note right of Online
        LED indicator: 🟢
        Patterns auto-loaded
        Models fetched
    end note

    note right of Offline
        LED indicator: 🔴
        Server buttons update
    end note
```

### Application Startup Sequence

What happens when the application launches:

```mermaid
sequenceDiagram
    participant User
    participant GUI as FabricGUI.__init__
    participant CM as ConfigManager
    participant SM as ServerManager
    participant FS as File System

    User->>GUI: python fabricgui.py

    GUI->>CM: load()
    CM->>FS: Read ~/.fabric_gui/config.json
    FS-->>CM: Config dict (or defaults)
    CM-->>GUI: app_config

    GUI->>GUI: OutputHistory()
    GUI->>FS: Read ~/.fabric_gui/history.json

    GUI->>SM: ServerManager(fabric_cmd, base_url, port_flag)

    GUI->>GUI: Build UI components
    Note over GUI: _build_menu()<br/>_build_server_frame()<br/>_build_pattern_frame()<br/>_build_info_frame()<br/>_build_io_frame()<br/>_setup_shortcuts()

    GUI->>SM: start_health_monitoring(interval=5s)
    Note over SM: Background thread begins<br/>GET /readyz every 5s

    alt auto_start_server = true
        GUI->>SM: start_server() (after 600ms)
        SM->>SM: fabric --serve --address :PORT
    end

    GUI->>SM: load_patterns() (after 800ms)
    SM->>SM: GET /patterns/names
    SM-->>GUI: Pattern list → dropdown

    GUI->>SM: load_models() (after 1200ms)
    SM->>SM: fabric --listmodels
    SM-->>GUI: Models by provider → dropdown
    SM->>FS: Read ~/.config/fabric/.env
    FS-->>SM: DEFAULT_MODEL
    SM-->>GUI: Default model label

    GUI-->>User: Window ready
```

### GUI Layout Structure

Visual map of how the UI panels are organized:

```mermaid
block-beta
    columns 1

    block:top["Server Frame"]
        columns 6
        LED["🔴 LED"] URL["Base URL Label"] Test["Test"] Start["Start"] Stop["Stop"] space
    end

    block:pattern["Pattern Selection Frame"]
        columns 4
        Search["🔍 Search Input"] space:3
        PatternLabel["Pattern:"] PatternCombo["Pattern Dropdown ▼"] Refresh["Refresh Patterns"] space
        ModelLabel["Model:"] ModelCombo["Model Dropdown ▼"] DefaultModel["Default: model-name"] space
    end

    block:info["Info / Actions Frame"]
        columns 3
        Status["Status: Ready"] CommandPreview["Command: fabric -p pattern"] Actions["Cancel | Send"]
    end

    block:io["Input / Output Frame"]
        columns 2
        block:input["Input Panel"]
            InputToolbar["Import | Paste | Clear"]
            InputText["📝 Input Textbox"]
        end
        block:output["Output Panel"]
            OutputToolbar["Copy | Save | Clear | ◀ ▶"]
            OutputText["📄 Output Textbox"]
        end
    end
```

---

## Features

### ✨ Core Functionality

- **Pattern selection and execution** via Fabric CLI subprocess
- **Real-time streaming responses** — output appears chunk-by-chunk as the AI generates it
- **Model selection** — browse all configured AI models grouped by provider
- **Command preview** — see the exact `fabric` command before executing

### 🎨 Modern User Interface

- **CustomTkinter** integration for a modern, dark-mode friendly aesthetic
- Clean, intuitive layout with organized frames
- **Animated progress indicator** with pulsing gold dots during processing
- Output toolbar (Copy, Save, Clear)
- History navigation (◀/▶ buttons)
- Status bar with visual feedback
- **Context Menus** — right-click support for Cut/Copy/Paste/Select All
- **Interactive Pattern Search** — real-time filtering with match count display

### 🖥️ Server Management

- Visual LED status indicator (🔴 offline / 🟢 online)
- Start/Stop server controls directly from the GUI
- Automatic health monitoring (configurable interval, default 5s)
- **Auto-Load Patterns** — patterns and models load automatically when server comes online
- Pre-request server validation with auto-start prompt
- Graceful shutdown handling with force-kill fallback

### ⚙️ Configuration

- Persistent settings via JSON (auto-saved)
- Tabbed Preferences dialog (Server + Advanced)
- Configurable server URL, health check interval, and request timeout
- Window geometry persistence across sessions

### 📝 Output Management

- Copy output to clipboard
- Save output to file (TXT/MD)
- Clear output display
- Navigate through response history (up to 50 entries, persisted to disk)

### 📁 File Import

- Import `.txt` or `.md` files directly into the input box via the Import button

---

## Installation

### Requirements

- Python 3.11+
- [Fabric](https://github.com/danielmiessler/fabric) CLI installed and on PATH
- `requests` library
- `customtkinter` library

### Quick Start (Windows)

1. Clone or download this repository
2. Double-click `start.bat`
   - First run: creates a virtual environment, installs dependencies, and launches the app
   - Subsequent runs: activates the venv and launches immediately

### Manual Setup

```bash
# Clone the repository
git clone https://github.com/Digitalgods2/FabricGui.git
cd FabricGui

# Install dependencies
pip install -r requirements.txt

# Run the application
python fabricgui.py
```

### Build Standalone Executable

```bash
pip install pyinstaller
pyinstaller fabricgui.spec
```

The standalone `FabricGUI.exe` will be created in the `dist/` folder (no console window).

---

## Usage

### First Time Setup

1. **Configure Server**
   - The default server URL is `http://localhost:8083`
   - Open **Edit → Preferences** to change the URL or other settings
   - Click **Test** to verify connectivity

2. **Start the Server**
   - Click **Start** to launch Fabric's built-in server
   - Wait for the LED indicator to turn 🟢 green
   - Patterns and models load automatically

3. **Select Your Model**
   - The Model dropdown shows all available AI models grouped by provider
   - Click the "Default: ..." label to reset to your configured default model

### Sending Requests

1. Select a pattern from the dropdown (use the search box to filter)
2. Enter your input text (or click **Import** to load a file)
3. Review the command preview
4. Click **Send** or press `Ctrl+Enter`
5. Watch the response stream in the output panel

### Managing Output

| Action | Button | Shortcut |
|---|---|---|
| Copy to clipboard | **Copy** | `Ctrl+C` |
| Save to file | **Save** | `Ctrl+S` |
| Clear display | **Clear** | — |
| Previous history | **◀** | `Alt+Left` |
| Next history | **▶** | `Alt+Right` |

### Managing the Server

**Status Indicators:**

| LED | Meaning |
|---|---|
| 🔴 Red | Server offline |
| 🟢 Green | Server online |

**Auto-Start:** Enable in Preferences to start the server automatically on app launch.

**Pre-Request Validation:** If the server is offline when you send a request, the app prompts: *"Would you like to start it now?"*

### Cancelling Requests

Click the **Cancel** button during processing. The subprocess will be terminated gracefully (or force-killed after a timeout).

---

## Configuration

Settings are stored at `~/.fabric_gui/config.json` and auto-saved:

```json
{
  "base_url": "http://localhost:8083",
  "last_pattern": "",
  "last_model": "",
  "window_geometry": "1200x800",
  "auto_start_server": false,
  "stop_server_on_exit": true,
  "server_health_check_interval": 5,
  "request_timeout": 300,
  "fabric_command": "fabric",
  "port_flag": "--address"
}
```

| Setting | Default | Description |
|---|---|---|
| `base_url` | `http://localhost:8083` | Fabric server address |
| `auto_start_server` | `false` | Launch server on app start |
| `stop_server_on_exit` | `true` | Prompt to stop server on close |
| `server_health_check_interval` | `5` | Health check frequency (seconds) |
| `request_timeout` | `300` | Max processing time (seconds) |
| `fabric_command` | `fabric` | Path to Fabric executable |
| `port_flag` | `--address` | Server bind flag (auto-corrected from `--port`) |

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Enter` | Send request |
| `Ctrl+S` | Save output to file |
| `Ctrl+C` | Copy output to clipboard |
| `Ctrl+,` | Open Preferences |
| `Alt+Left` | Previous history entry |
| `Alt+Right` | Next history entry |
| Right-click | Context menu (Cut/Copy/Paste/Select All) |

---

## Menu Reference

| Menu | Item | Shortcut | Action |
|---|---|---|---|
| **File** | Save Output... | `Ctrl+S` | Save output to file |
| | Exit | — | Close application |
| **Edit** | Preferences... | `Ctrl+,` | Open settings dialog |
| | Copy Output | `Ctrl+C` | Copy to clipboard |
| | Clear Output | — | Clear output display |
| | Paste Input | — | Paste from clipboard |
| | Clear Input | — | Clear input text |
| **History** | Previous | `Alt+Left` | Previous response |
| | Next | `Alt+Right` | Next response |
| **Help** | User Guide | — | Comprehensive help window |
| | View Logs | — | Open log file |
| | About | — | Application info |

---

## Project Structure

```
FabricGui/
├── fabricgui.py          # Entire application (1,930 lines)
├── fabricgui.spec        # PyInstaller build configuration
├── requirements.txt      # Python dependencies
├── start.bat             # Windows quick-start launcher
├── README.md             # This file
├── .gitignore
└── build/                # PyInstaller build artifacts

Runtime files (created automatically):
~/.fabric_gui/
├── config.json           # Persistent configuration
├── history.json          # Response history (up to 50 entries)
└── fabric_gui.log        # Rotating log files (5 MB × 3 backups)
```

### Key Classes

| Class | Lines | Responsibility |
|---|---|---|
| `ConfigManager` | 248–314 | Loads/saves JSON config with defaults and migration |
| `OutputHistory` | 321–387 | Manages response history with persistence |
| `ServerManager` | 394–660 | Controls Fabric server process, health checks, pattern/model fetching |
| `ContextMenu` | 667–714 | Right-click Cut/Copy/Paste/Select All for any text widget |
| `PreferencesDialog` | 721–898 | Tabbed settings dialog with validation |
| `FabricGUI` | 905–1924 | Main window — all UI building, event handling, and request processing |

---

## Logging

Application logs are saved to `~/.fabric_gui/fabric_gui.log`

- **Max file size:** 5 MB per file
- **Backup files:** 3 rotated backups
- **Total max:** ~20 MB
- **View logs:** Help → View Logs

---

## Troubleshooting

### "Failed to reach server"

- Verify the Fabric server is running (LED should be 🟢)
- Check the base URL in Preferences
- Click **Test** to diagnose connectivity

### "Error loading patterns"

- Ensure the server is accessible and responding
- Check API key if required
- Review logs (**Help → View Logs**) for detailed error messages

### Request Timeout

- Increase timeout in **Edit → Preferences → Advanced**
- Check network connection
- Verify the server is responding (click **Test**)

### "Ollama Get ... connection refused"

- **This is normal** if you are not running a local Ollama instance
- The Fabric CLI automatically checks for local models on startup
- The GUI filters this message to keep output clean
- It does not affect cloud models (Claude, GPT-4, etc.)

### Server Won't Start

- Ensure `fabric` is installed and on your system PATH
- Try running `fabric --serve` in a terminal to see errors directly
- Check that the port (default 8083) is not already in use

---

## Version History

### Version 3.2 (Latest) 🚀

- ✅ **Interactive Pattern Search**: Real-time filtering with auto-selection of first match
- ✅ **Improved Readability**: Enhanced dropdown styling with better contrast, taller dropdowns (25 items)
- ✅ **UI Polish**: Consistent font sizing, status bar shows match count while searching

### Version 3.1

- ✅ **Reliable AI Processing**: Switched to direct subprocess execution for guaranteed correct output
- ✅ **Enhanced UI**: Vertical scrollbar on pattern dropdown, expanded list (40 items), increased fonts
- ✅ **Smarter Server Management**: Improved stop logic, better error handling
- ✅ **Bug Fixes**: Output buffering/hanging, encoding issues with emojis, filtered startup errors

### Version 3.0 ⭐ Major Update

- ✅ **CustomTkinter Migration**: Complete UI overhaul with modern look and dark mode
- ✅ **Context Menus**: Right-click support for text widgets
- ✅ **Bug Fixes**: Infinite pattern loading loop, endpoint fix, TypeError, startup crashes

### Version 2.1

- ✅ Server management with Start/Stop controls and LED indicator
- ✅ Automatic health monitoring and pre-request validation
- ✅ Auto-start server option and graceful shutdown
- ✅ Cross-platform process management

### Version 2.0

- ✅ Complete refactoring with improved architecture
- ✅ Configuration persistence, output history, request cancellation
- ✅ Progress indicators, menu system, keyboard shortcuts
- ✅ Comprehensive logging

### Version 1.0

- Basic Fabric pattern execution with input/output interface

---

## Contributing

Suggestions and improvements are welcome! Please ensure:

- Code follows existing style
- All features are tested
- Documentation is updated

---

## Credits

**Fabric GUI** designed and developed by [DigitalGods.ai](https://digitalgods.ai)

Built for the [Fabric](https://github.com/danielmiessler/fabric) AI framework by Daniel Miessler.

---

**Happy pattern processing! 🚀**
