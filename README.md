# MousePresence

MousePresence is a Windows-focused Python application that prevents a workstation from registering as idle or AFK (away from keyboard).  
It simulates realistic user activity by moving the mouse pointer at configurable intervals along smooth, natural paths.

<img width="256" height="256" alt="logo" src="https://github.com/user-attachments/assets/3523259d-f2ed-4594-b74b-122d32936c5c" />

---

## Features

- Graphical user interface built with Tkinter
- Smooth, human-like mouse movement using multiple waypoints
- Real-time configurable settings:
  - Interval between movement cycles (5 to 120 seconds)
  - Total travel time per movement (0.2 to 10 seconds)
  - Waypoint count with variance
  - Edge margin to avoid screen edges
  - Corner stop safety zone
  - Minimum movement distance
  - Movement tick rate (responsiveness versus CPU usage)
- Start, Pause, Stop, and Move Now controls
- Global stop-on-input:
  - Any key press or mouse button click stops movement
  - Mouse movement alone is ignored
- UI-safe input suppression so buttons do not self-trigger a stop
- Escape key instantly stops while the app window is focused
- Status indicator and live log panel
- Thread-safe logging with automatic size limits
- Designed to stop cleanly without forcing system-level failsafes

<img width="1096" height="787" alt="image" src="https://github.com/user-attachments/assets/dbc41157-aa68-469a-9669-ac9f6042cbaa" />

---

## Use Cases

- Prevents systems from sleeping or locking during long-running tasks
- Keeps collaboration tools from marking the user as AFK
- Useful for monitoring dashboards, training sessions, or kiosk-style setups
- Safer alternative to hardware mouse jigglers

---

## Installation (Source Code)

### Requirements
- Python 3.10 or newer
- Windows operating system

### Install dependencies

```bash
pip install pyautogui pynput
```

### Run the application

```bash
python MousePresence.py
```

---

## Controls Overview

- Start: Begin periodic mouse movement
- Pause or Resume: Temporarily halt movement
- Stop: Stop all activity and reset to idle
- Move Now: Perform a single movement cycle immediately
- Escape: Immediate stop while the window is focused
- Any key press or mouse click: Stops movement globally while active

---

## Settings Overview

| Setting | Range | Description |
|------|------|------------|
| Interval (seconds) | 5 to 120 | Time between movement cycles |
| Travel time (seconds) | 0.2 to 10 | Duration of each movement cycle |
| Waypoints (base and variance) | 1 to 30 | Randomized path complexity |
| Edge margin (px) | 0 to 500 | Distance to keep away from screen edges |
| Corner stop zone (px) | 5 to 250 | Emergency soft stop region |
| Min step distance (px) | 0 to 800 | Prevents tiny jitter movements |
| Move tick (ms) | 5 to 50 | Movement responsiveness |

---

## Windows Executable

A standalone Windows executable is available in the Releases section.

### Run the EXE
- No Python installation required
- Download and run MousePresence.exe directly

---

## Building Your Own Executable

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build single-file executable with icon

```bash
pyinstaller --onefile --noconsole --name MousePresence --icon MousePresence.ico MousePresence.py
```

The executable will be created in the dist directory.

### If input hooks fail in the EXE

```bash
pyinstaller --onefile --noconsole ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  --name MousePresence ^
  MousePresence.py
```

---

## Notes on Safety and Behavior

- PyAutoGUI hard corner FAILSAFE is intentionally disabled
- All stopping is handled in controlled software logic
- Stop-on-input only triggers while movement is active
- UI interactions are protected from accidental stops
- Designed to shut down cleanly without abrupt cursor jumps

---

## License

This project is licensed under the MIT License.

---

## Disclaimer

This tool simulates user input.  
Ensure usage complies with your organization’s policies and applicable terms of service.
