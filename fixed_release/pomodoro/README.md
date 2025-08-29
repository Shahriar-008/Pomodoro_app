# Pomodoro — Focus Timer (Modern Tkinter)

A clean, modern Pomodoro timer with a circular progress ring, dark/light theme, tray support, desktop notifications, and simple history export. Built with Tkinter and packaged for Windows.

## Features
- Circular progress ring with subtle pulse while running
- Dark/Light theme toggle (Ctrl+D)
- System tray support with quick actions (Show, Start/Pause, Stretch)
- Desktop notifications (via Plyer)
- Stretch reminder popup with animation after each focus session
- Auto-repeat option and configurable Focus/Break durations
- History view with export/clear
- Keyboard shortcuts: Space (Start/Pause), R (Reset), Ctrl+D (Theme)

## Run (without IDE)
```powershell
cd "D:\Programming\PY Code\pomodoro_app\new_repo"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python pomodoro.py
```

No console window:
```powershell
.\.venv\Scripts\pythonw.exe .\pomodoro.py
```

## Build Windows EXE
```powershell
cd "D:\Programming\PY Code\pomodoro_app\new_repo"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconsole --onefile --name pomodro --icon .\assets\pomodro.ico .\pomodoro.py
```
The EXE will be created at `dist\pomodro.exe`. When run, config/history are stored next to the EXE.

## Files
- `pomodoro.py` — app source
- `requirements.txt` — optional dependencies
- `assets/pomodro.ico` — app icon
- `assets/generate_icon.py` — helper to (re)generate the icon

## Notes
- On first run, `pomodoro_config.json` and `pomodoro_history.json` will be created next to the script/EXE.
- If tray/notifications aren’t available, the app falls back gracefully.
