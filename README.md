# MousePresence

MousePresence is a Python application that prevents a workstation from registering as idle or AFK (away from keyboard).
It works by moving the mouse pointer at configurable intervals in smooth, natural paths, simulating realistic user activity.
A graphical user interface (Tkinter) allows settings to be adjusted in real time.

<img width="1187" height="783" alt="image" src="https://github.com/user-attachments/assets/4b398609-b9c3-4666-aa1c-fe2bcf34b4b3" />

---

## Features

* Graphical user interface built with Tkinter.
* Adjustable settings:

  * Interval between jiggle cycles (5–120 seconds).
  * Travel time for each jiggle (0.2–10 seconds).
  * Minimum and maximum number of waypoints per jiggle.
  * Edge margin to keep movements away from screen edges.
* Start, Pause, Stop, and "Move Now" controls.
* Log panel displaying jiggle events and status updates.
* Enlarged slider handles for ease of use.
* PyAutoGUI failsafe enabled (moving the mouse to a screen corner stops the program).

---

## Use Cases

* Prevents a computer from going idle, sleeping, or showing "away" status.
* Useful as an **anti-AFK tool**, as it moves the mouse in a way that resembles human movement.
* Suitable for workstations, long-running sessions, or systems that disconnect when idle.

---

## Installation (Source Code)

Clone the repository and install dependencies:

```bash
git clone https://github.com/YOUR-USERNAME/MousePresence.git
cd MousePresence
pip install pyautogui
```

Run the application:

```bash
python MousePresence.py
```

---

## Windows Executable

If you do not want to run the Python source, you can download the standalone **Windows .exe** from the
[Releases](../../releases) page.

Steps:

1. Go to the [Releases](../../releases) section of this repository.
2. Download the latest `MousePresence.exe`.
3. Run it directly, no Python installation required.

---

## Settings Overview

| Setting             | Range       | Description                           |
| ------------------- | ----------- | ------------------------------------- |
| Interval (seconds)  | 5 – 120     | Time between jiggle cycles            |
| Travel time (sec)   | 0.2 – 10    | Duration of each jiggle               |
| Waypoints (min/max) | 1 – 20 / 30 | Random intermediate points per jiggle |
| Edge margin (px)    | 0 – 500     | Distance from screen edges to avoid   |

---

## Building Your Own Executable

If you prefer to build the `.exe` yourself:

```bash
pip install pyinstaller pyautogui
pyinstaller --onefile --noconsole --icon=MousePresence.ico --name MousePresence MousePresence.py
```

The executable will be created in the `dist/` directory.

---

## License

This project is licensed under the MIT License.
