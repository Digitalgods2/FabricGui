# Fabric GUI (Go Edition)

A high-performance, native desktop GUI for the [Fabric](https://github.com/danielmiessler/fabric) AI tool, built with **Go (Wails)** and **Vanilla JavaScript**.

![Fabric GUI Banner](https://placehold.co/1200x600/131117/58a6ff?text=Fabric+GUI+Go)

## ✨ Features

- **🚀 Native Performance**: Built with Go and Wails for a lightweight, fast, and responsive experience.
- **🔌 Server Management**:
  - Start/Stop the `fabric` server directly from the UI.
  - Live status LED visualization.
- **💾 Session Persistence**: Automatically remembers your last used:
  - Pattern
  - AI Model
  - Theme (Dark/Light)
- **⚡ Premium UI**:
  - Modern, glassmorphic design inspired by macOS and Linear.
  - Streaming output with live Markdown rendering.
  - "Gentle Light" and "Midnight Dark" themes.
- **🛠️ Power User Tools**:
  - **History Navigation**: Step through your past queries with `Alt+←` / `Alt+→`.
  - **File I/O**: Direct Import/Export of `.txt` and `.md` files.
  - **Command Preview**: See the exact CLI command being executed.

## 📦 Prerequisites

1. **[Fabric](https://github.com/danielmiessler/fabric)** installed and configured.
   - The `fabric` binary must be in your system `PATH`.
2. **[Go](https://go.dev/dl/)** (v1.21+)
3. **[Wails CLI](https://wails.io/docs/gettingstarted/installation)** (v2.11+)

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/fabric-gui-go.git
cd fabric-gui-go/FabricGoGUI
```

### 2. Run in Development Mode

Start the app with hot-reload enabled:

```bash
wails dev
```

### 3. Build for Production

Create a standalone binary executable:

```bash
wails build
```

The binary will be located in `build/bin/FabricGoGUI.exe`.

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + Enter` | Send Request |
| `Ctrl + S` | Save Output to File |
| `Ctrl + O` | Import File to Input |
| `Alt + ←` | Previous History Item |
| `Alt + →` | Next History Item |
| `Esc` | Close Modals |

## 🛠️ Architecture

- **Backend**: Go (handling file I/O, server process management, API requests).
- **Frontend**: HTML/CSS/JavaScript (no heavy framework, pure performance).
- **Communication**: Wails runtime (events and bindings).

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---
*Not affiliated with the official Fabric project.*
