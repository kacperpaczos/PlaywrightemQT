# 🚀 Educational Project: PlaywrightemQT

This cool project demonstrates how to build modern desktop applications with PyQt6! The graphical user interface allows you to manage and control automation processes with just a few clicks.

## 🎯 What's It For?

This application provides a sleek Qt-based interface that:

- 🖥️ Shows how to create professional desktop GUIs with PyQt6
- 🎨 Demonstrates modern UI design patterns and best practices
- 🔄 Manages automation tasks through an intuitive interface
- ⚙️ Configures parameters through user-friendly forms

## ✨ Cool Features

### 🎨 Modern Qt6 Interface
- 🎛️ Clean, responsive layout with tabs and panels
- 🔍 User-friendly forms and input validation
- 📊 Real-time progress indicators and statistics
- 🗂️ Organized file/data management with intuitive controls

### 🖼️ UI Components
- 📝 Configuration panels with smart defaults
- 🚦 Status indicators and progress bars
- 📋 Interactive data tables and lists
- 🔘 Custom buttons and controls

### 📱 Desktop Experience
- 🔔 Notification system for important events
- 🌙 Elegant design with attention to details
- ⌨️ Keyboard shortcuts for power users
- 🖱️ Intuitive drag-and-drop functionality

## 🔧 Technical Specs

### 🧪 Technologies
- **PyQt6**: Modern Qt bindings for Python
- **Qt Designer**: For visual interface design
- **QSS**: Styling sheets for customizing appearance
- **Python**: 3.10+ for modern language features

### 🏗️ Architecture
- **Model-View-Controller** pattern for UI components
- **Signal-Slot** mechanism for responsive UI
- **Resource System** for managing icons and assets
- **Multithreading** for responsive interface during operations

## 📁 Project Structure

```
PlaywrightemQT/
├── 📱 app/                      # Main application code
│   ├── 🖼️ ui/                   # User interface components
│   │   ├── main_window.py       # Main window definition
│   │   ├── dialogs/             # Dialog windows
│   │   └── widgets/             # Custom UI widgets
│   ├── 🛠️ utils/                # Utility modules
│   └── 🚀 main.py               # Application entry point
├── ⚙️ config/                   # Configuration files
├── 📜 scripts/                  # Helper scripts
├── 🧰 run.sh                    # Launcher script for Linux/macOS
├── 🧰 run.ps1                   # Launcher script for Windows
└── 📦 requirements.txt          # Python dependencies
```

## 🚀 Installation & Running

### 🔍 Prerequisites
- Python 3.10 or newer
- Git (optional, for cloning)
- Internet connection (for dependencies)

### 🔨 Quick Start with Run Scripts

#### 💻 On Windows:
Right-click on `run.ps1` and select "Run with PowerShell" or open PowerShell and run:
```powershell
.\run.ps1
```

#### 🐧 On Linux/macOS:
Open Terminal and run:
```bash
chmod +x run.sh
./run.sh
```

The script provides an interactive menu:
1. **Run in Development Mode** - Sets up environment and launches the app
2. **Build Application** - Creates a standalone executable
3. **Clean Project** - Removes temporary files and caches
4. **Exit**

### 🔨 Manual Setup
1. Clone or download the repo:
   ```bash
   git clone https://github.com/your-repo/PlaywrightemQT.git
   cd PlaywrightemQT
   ```

2. Create Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # or
   .venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the app:
   ```bash
   python -m app.main
   ```

## 🎓 Learning Qt with this Project

1. 🔰 **UI Design Fundamentals** - Layouts, widgets, and styling
2. 📊 **Data Presentation** - Tables, charts, and forms
3. 🔄 **Event-Driven Programming** - Signals, slots, and event handling
4. 🎨 **Custom Widgets** - Creating your own UI components

## ⚠️ Disclaimer

This application was created for educational purposes to demonstrate PyQt6 desktop application development and should not be used in production environments without appropriate review and adaptation.

---

*This project is developed as an educational tool for learning modern Qt GUI development with Python.*
