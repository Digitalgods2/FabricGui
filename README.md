# Fabric Mini GUI

A modern desktop client for interacting with [Fabric](https://github.com/danielmiessler/fabric) AI patterns, built with **CustomTkinter** for a sleek, modern look.

## Features

✨ **Core Functionality**

- Pattern selection and execution
- Real-time streaming responses (SSE support)
- JSON and plain text response handling

🎨 **Modern User Interface**

- **CustomTkinter** integration for a modern, dark-mode friendly aesthetic
- Clean, intuitive layout with collapsible frames
- Progress indicators for long-running requests
- Output toolbar (Copy, Save, Clear)
- History navigation (◀/▶ buttons)
- Status bar with visual feedback
- **Context Menus**: Right-click support for Cut/Copy/Paste/Select All

🖥️ **Server Management**

- Visual LED status indicator (🔴 offline / 🟢 online)
- Start/Stop server controls directly from the GUI
- Automatic health monitoring (5-second intervals)
- **Auto-Load Patterns**: Patterns load automatically when server comes online
- Pre-request server validation
- Auto-start server option
- Graceful shutdown handling

⚙️ **Configuration**

- Persistent settings (auto-saved)
- Configurable server URL and API key
- Request timeout configuration
- Window geometry persistence
- Server management preferences

📝 **Output Management**

- Copy output to clipboard
- Save output to file (TXT/MD)
- Clear output display
- Navigate through response history (up to 50 entries)

⌨️ **Keyboard Shortcuts**

- `Ctrl+Return` - Send request
- `Ctrl+S` - Save output
- `Ctrl+C` - Copy output
- `Alt+Left` - Previous history
- `Alt+Right` - Next history

🔧 **Advanced Features**

- Request cancellation
- Comprehensive logging
- Error handling with detailed messages
- HTTPS security warnings

## Installation

### Requirements

- Python 3.11+
- `requests` library
- `customtkinter` library

### Setup

1. Clone or download this repository
2. Install dependencies:

```bash
pip install requests customtkinter
```

1. Run the application:

```bash
python fabricgui.py
```

## Usage

### First Time Setup

1. **Configure Server**
   - Enter your Fabric server URL (default: `http://localhost:8080`)
   - Optionally add an API key
   - Click "Test Connection" to verify

2. **Load Patterns**
   - Patterns load automatically when the server starts
   - Click "Refresh Patterns" to reload manually if needed

### Sending Requests

1. Select a pattern from the dropdown
2. Enter your input text
3. Click "Send" or press `Ctrl+Return`
4. View the response in the output panel

### Managing Output

- **Copy**: Click "Copy" button or press `Ctrl+C`
- **Save**: Click "Save" button or press `Ctrl+S`
- **Clear**: Click "Clear" button
- **History**: Use ◀/▶ buttons or `Alt+Left`/`Alt+Right`

### Managing the Server

**Visual Status**:

- 🔴 Red LED = Server offline
- 🟢 Green LED = Server online
- Hover over LED for status tooltip

**Starting the Server**:

1. Click "Start" button
2. Wait for LED to turn green (automatic health check)
3. Server runs in background

**Stopping the Server**:

1. Click "Stop" button
2. Server shuts down gracefully
3. LED turns red

**Auto-Start** (Optional):

- Edit config: `"auto_start_server": true`
- Server starts automatically on app launch

**Pre-Request Validation**:

- If server is offline when sending a request
- Dialog prompts: "Would you like to start it now?"
- Server starts automatically if you choose "Yes"

### Cancelling Requests

If a request is taking too long:

1. Click the "Cancel" button
2. The request will stop gracefully

## Configuration

Settings are automatically saved to `~/.fabric_gui/config.json`:

```json
{
  "base_url": "http://localhost:8080",
  "api_key": "",
  "clear_input_after_send": false,
  "request_timeout": 300,
  "last_pattern": "",
  "window_geometry": "900x600",
  "auto_start_server": false,
  "stop_server_on_exit": true,
  "server_health_check_interval": 5,
  "fabric_command": "fabric"
}
```

**Server Management Options**:

- `auto_start_server`: Automatically start server on app launch
- `stop_server_on_exit`: Prompt to stop server when closing app
- `server_health_check_interval`: Health check frequency in seconds
- `fabric_command`: Path to Fabric executable (customize if needed)

## Logging

Application logs are saved to `~/.fabric_gui/fabric_gui.log`

View logs via: **Help → View Logs**

## Menu Reference

### File

- **Save Output** (`Ctrl+S`) - Save output to file
- **Exit** - Close application

### Edit

- **Copy Output** (`Ctrl+C`) - Copy to clipboard
- **Clear Output** - Clear output display
- **Clear Input** - Clear input text
- **Paste Input** - Paste from clipboard

### History

- **Previous** (`Alt+Left`) - Navigate to previous response
- **Next** (`Alt+Right`) - Navigate to next response

### Help

- **View Logs** - Open log file
- **About** - Application information

## Troubleshooting

### "Failed to reach server"

- Verify the Fabric server is running
- Check the base URL is correct
- Test connection with "Test Connection" button

### "Error loading patterns"

- Ensure server is accessible
- Check API key if required
- Review logs for detailed error messages

### Request Timeout

- Increase timeout in config file
- Check network connection
- Verify server is responding

### "Ollama Get ... connection refused"

- **This is normal** if you are not running a local Ollama instance.
- The Fabric CLI automatically checks for local models on startup.
- The GUI filters this message to keep the output clean, but you might see it briefly or in logs.
- It does not affect cloud models (Claude, GPT-4, etc.).

## Development

### Project Structure

```
fabricgui.py          # Main application
~/.fabric_gui/
├── config.json       # Configuration
└── fabric_gui.log    # Application logs
```

### Key Classes

- `FabricGUI` - Main application window (inherits `ctk.CTk`)
- `ConfigManager` - Configuration persistence
- `OutputHistory` - Response history management
- `ServerManager` - Fabric server process control
- `ContextMenu` - Right-click menu implementation

## Version History

### Version 3.2 (Latest) 🚀

- ✅ **Interactive Pattern Search**: Real-time filtering with auto-selection of first match
- ✅ **Improved Readability**:
  - Enhanced dropdown styling with better contrast and fonts
  - Taller dropdowns with more visible items (25 items in list)
  - Status bar shows pattern match count while searching
- ✅ **UI Polish**: Consistent font sizing across search and dropdowns

### Version 3.1 🚀

- ✅ **Reliable AI Processing**: Switched to direct `subprocess` execution for guaranteed correct output
- ✅ **Enhanced UI**:
  - Added vertical scrollbar to pattern dropdown (ttk.Combobox)
  - **Expanded Dropdowns**: Increased list size to 40 items for easier browsing
  - Increased font sizes for better legibility
  - Added mouse wheel support
- ✅ **Smarter Server Management**:
  - Improved stop logic (won't kill externally started servers)
  - Better error handling and status reporting
- ✅ **Bug Fixes**:
  - Fixed output buffering/hanging issues
  - Fixed encoding issues with emojis/symbols
  - Filtered startup connection errors

### Version 3.0 ⭐ MAJOR UPDATE

- ✅ **CustomTkinter Migration**: Complete UI overhaul with modern look and dark mode
- ✅ **Context Menus**: Added right-click support for text widgets
- ✅ **Bug Fixes**:
  - Fixed infinite pattern loading loop
  - Fixed pattern loading endpoint (`/patterns/names`)
  - Fixed `TypeError` in send function
  - Fixed startup crashes and duplicate methods

### Version 2.1

- ✅ Server management with Start/Stop controls
- ✅ Visual LED status indicator (red/green)
- ✅ Automatic health monitoring (5-second intervals)
- ✅ Pre-request server validation with auto-start
- ✅ Auto-start server option
- ✅ Graceful shutdown handling
- ✅ Cross-platform process management

### Version 2.0

- ✅ Complete refactoring with improved architecture
- ✅ Configuration persistence
- ✅ Output history navigation
- ✅ Request cancellation
- ✅ Progress indicators
- ✅ Menu system
- ✅ Keyboard shortcuts
- ✅ Comprehensive logging
- ✅ Bug fixes (widget state, stream consumption, timeout)

### Version 1.0

- Basic Fabric pattern execution
- Input/output interface
- Pattern selection

## License

This project is provided as-is for use with Fabric AI.

## Contributing

Suggestions and improvements are welcome! Please ensure:

- Code follows existing style
- All features are tested
- Documentation is updated

## Credits

**Fabric GUI** designed and developed by [DigitalGods.ai](https://digitalgods.ai)

Built for the [Fabric](https://github.com/danielmiessler/fabric) AI framework by Daniel Miessler.

---

**Happy pattern processing! 🚀**
