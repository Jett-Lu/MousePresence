import threading
import time
import random
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui

from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse


def clamp(n, lo, hi):
    return max(lo, min(hi, n))


def ease_in_out_quad(t):
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2


def in_corner_zone(x, y, w, h, corner_px):
    c = int(max(0, corner_px))
    return (
        (x <= c and y <= c) or
        (x >= (w - 1 - c) and y <= c) or
        (x <= c and y >= (h - 1 - c)) or
        (x >= (w - 1 - c) and y >= (h - 1 - c))
    )


def safe_random_point(edge_margin, corner_safe_px):
    w, h = pyautogui.size()
    safe = max(0, int(edge_margin)) + max(0, int(corner_safe_px))

    min_x = clamp(safe, 0, w - 1)
    max_x = clamp(w - 1 - safe, 0, w - 1)
    min_y = clamp(safe, 0, h - 1)
    max_y = clamp(h - 1 - safe, 0, h - 1)

    if max_x <= min_x or max_y <= min_y:
        return (w // 2, h // 2)

    return (random.randint(min_x, max_x), random.randint(min_y, max_y))


def distance(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def pick_waypoints(n_points, edge_margin, corner_safe_px, min_step_px):
    pts = []
    tries = 0
    max_tries = max(50, n_points * 20)

    cur = pyautogui.position()
    while len(pts) < n_points and tries < max_tries:
        tries += 1
        p = safe_random_point(edge_margin, corner_safe_px)
        ref = pts[-1] if pts else cur
        if distance(p, ref) >= float(min_step_px):
            pts.append(p)

    while len(pts) < n_points:
        pts.append(safe_random_point(edge_margin, corner_safe_px))

    return pts


def smooth_move_to(x, y, duration_s, tick_s, corner_safe_px, should_stop_fn):
    w, h = pyautogui.size()
    start = pyautogui.position()
    end = (int(x), int(y))

    if duration_s <= 0:
        if should_stop_fn():
            return
        cx, cy = pyautogui.position()
        if in_corner_zone(cx, cy, w, h, corner_safe_px):
            raise RuntimeError("Soft failsafe triggered: mouse in corner stop zone")
        pyautogui.moveTo(end[0], end[1], _pause=False)
        return

    steps = max(1, int(duration_s / max(0.005, tick_s)))
    for i in range(steps):
        if should_stop_fn():
            return

        cx, cy = pyautogui.position()
        if in_corner_zone(cx, cy, w, h, corner_safe_px):
            raise RuntimeError("Soft failsafe triggered: mouse in corner stop zone")

        t = (i + 1) / steps
        et = ease_in_out_quad(t)
        nx = int(round(start[0] + (end[0] - start[0]) * et))
        ny = int(round(start[1] + (end[1] - start[1]) * et))
        pyautogui.moveTo(nx, ny, _pause=False)
        time.sleep(max(0.0, tick_s))


def run_one_cycle(settings, log_fn, should_stop_fn):
    w, h = pyautogui.size()

    n_base = int(max(1, settings["waypoints_base"]))
    n_var = int(max(0, settings["waypoints_var"]))
    n_min = max(1, n_base - n_var)
    n_max = max(n_min, n_base + n_var)
    n_points = random.randint(n_min, n_max)

    edge_margin = int(settings["edge_margin"])
    corner_safe_px = int(settings["corner_safe_px"])
    total_travel = float(settings["travel_time_s"])
    min_step_px = float(settings["min_step_px"])
    tick_s = float(settings["tick_s"])
    log_level = settings["log_level"]  # Off, Cycle, Segments

    waypoints = pick_waypoints(n_points, edge_margin, corner_safe_px, min_step_px)
    per_segment = max(0.02, total_travel / max(1, n_points))

    if log_level != "Off":
        now = datetime.datetime.now().strftime("%H:%M:%S")
        log_fn(f"[{now}] Cycle: {n_points} waypoints, travel={total_travel:.2f}s")

    for i, (x, y) in enumerate(waypoints, start=1):
        if should_stop_fn():
            return

        cx, cy = pyautogui.position()
        if in_corner_zone(cx, cy, w, h, corner_safe_px):
            raise RuntimeError("Soft failsafe triggered: mouse in corner stop zone")

        smooth_move_to(x, y, per_segment, tick_s, corner_safe_px, should_stop_fn)

        if log_level == "Segments":
            now = datetime.datetime.now().strftime("%H:%M:%S")
            log_fn(f"[{now}] Segment {i}/{n_points}: moved to ({x}, {y})")


class JiggleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MousePresence Settings")
        self.geometry("1100x760")
        self.minsize(900, 640)
        self.option_add("*Font", "Arial 11")

        pyautogui.FAILSAFE = False

        self.worker_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

        # movement_active gates stop-on-input so it only triggers while the mouse is being controlled
        self.movement_active = threading.Event()

        self.interval_s = tk.DoubleVar(value=60.0)
        self.travel_time_s = tk.DoubleVar(value=1.8)

        self.waypoints_base = tk.IntVar(value=5)
        self.waypoints_var = tk.IntVar(value=2)

        self.edge_margin = tk.IntVar(value=120)
        self.corner_safe_px = tk.IntVar(value=70)

        self.min_step_px = tk.IntVar(value=120)
        self.tick_ms = tk.IntVar(value=15)

        self.log_level = tk.StringVar(value="Cycle")  # Off, Cycle, Segments

        self._settings_lock = threading.Lock()
        self._settings = {}

        # Stop-on-input controls
        self.stop_on_input = tk.BooleanVar(value=True)
        self._last_input_stop_ts = 0.0
        self._suppress_input_stop_until = 0.0
        self._input_listeners = []
        self._start_user_input_listeners()

        self._build_ui()
        self._install_traces()
        self._refresh_settings_snapshot()
        self._update_safe_area_preview()
        self._set_status("Idle")
        self._update_status_line()

        # Local immediate stop for focused window
        self.bind_all("<Escape>", lambda e: self._stop_from_ui("Escape pressed"))

    # -----------------------
    # Global input stop logic
    # -----------------------
    def _start_user_input_listeners(self):
        try:
            kb_listener = pynput_keyboard.Listener(on_press=self._on_any_key)
            kb_listener.daemon = True
            kb_listener.start()

            ms_listener = pynput_mouse.Listener(on_click=self._on_any_click)
            ms_listener.daemon = True
            ms_listener.start()

            self._input_listeners = [kb_listener, ms_listener]
        except Exception as e:
            self._input_listeners = []
            self.after(0, lambda: messagebox.showwarning(
                "Input listeners",
                f"Could not start input listeners. Stop-on-input disabled.\n\nError: {e}"
            ))

    def _stop_user_input_listeners(self):
        for l in getattr(self, "_input_listeners", []):
            try:
                l.stop()
            except Exception:
                pass
        self._input_listeners = []

    def _on_any_key(self, key):
        self._user_input_stop("Key press detected")

    def _on_any_click(self, x, y, button, pressed):
        if pressed:
            self._user_input_stop(f"Mouse click detected ({button})")

    def _user_input_stop(self, reason):
        # Runs in pynput thread
        if not self.stop_on_input.get():
            return

        # Only stop-on-input while movement is happening
        if not self.movement_active.is_set():
            return

        now = time.time()

        # Suppress stop-on-input briefly after UI actions (Start, Move Now, etc.)
        if now < self._suppress_input_stop_until:
            return

        # Very small debounce to avoid double firing from hardware chatter
        if (now - self._last_input_stop_ts) < 0.05:
            return
        self._last_input_stop_ts = now

        if self.stop_event.is_set():
            return

        self.stop_event.set()
        self.pause_event.clear()

        self.after(0, lambda: self._set_status("StoppedByFailsafe"))
        self.after(0, self._set_buttons_idle)
        self._log(f"Stopped by user input: {reason}")

    def _suppress_input_stop(self, seconds=0.35):
        # Called on UI thread
        self._suppress_input_stop_until = time.time() + float(seconds)

    def _stop_from_ui(self, reason):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.pause_event.clear()
        self._set_status("StoppedByFailsafe")
        self._set_buttons_idle()
        self._log(f"Stopped by UI: {reason}")

    # ----
    # UI
    # ----
    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        self.nb = ttk.Notebook(outer)
        self.nb.pack(fill="both", expand=True)

        self.tab_controls = ttk.Frame(self.nb, padding=10)
        self.tab_log = ttk.Frame(self.nb, padding=10)
        self.nb.add(self.tab_controls, text="Controls")
        self.nb.add(self.tab_log, text="Log")

        top = ttk.Frame(self.tab_controls)
        top.pack(fill="x")

        self.status_badge = tk.Label(
            top, text="Idle", fg="white", bg="#6b7280",
            padx=10, pady=6, font=("Arial", 11, "bold")
        )
        self.status_badge.pack(side="left")

        self.status_text = ttk.Label(top, text="Ready", padding=(10, 0))
        self.status_text.pack(side="left", fill="x", expand=True)

        btns = ttk.Frame(self.tab_controls)
        btns.pack(fill="x", pady=(10, 6))

        self.start_btn = ttk.Button(btns, text="Start", command=self.start_worker)
        self.pause_btn = ttk.Button(btns, text="Pause", command=self.pause_worker, state="disabled")
        self.stop_btn = ttk.Button(btns, text="Stop", command=self.stop_worker, state="disabled")
        self.move_now_btn = ttk.Button(btns, text="Move Now", command=self.move_once)

        self.start_btn.pack(side="left", padx=4, ipadx=8, ipady=3)
        self.pause_btn.pack(side="left", padx=4, ipadx=8, ipady=3)
        self.stop_btn.pack(side="left", padx=4, ipadx=8, ipady=3)
        self.move_now_btn.pack(side="left", padx=14, ipadx=6, ipady=3)

        grid = ttk.Frame(self.tab_controls)
        grid.pack(fill="both", expand=True, pady=(6, 0))

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        timing = ttk.LabelFrame(grid, text="Timing", padding=10)
        timing.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        timing.columnconfigure(1, weight=1)

        self._add_scale_row(timing, "Interval (seconds)", self.interval_s, 5.0, 120.0, 1.0, 0, is_int=False)
        self._add_scale_row(timing, "Total travel time (seconds)", self.travel_time_s, 0.2, 10.0, 0.1, 1, is_int=False)

        path = ttk.LabelFrame(grid, text="Path", padding=10)
        path.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        path.columnconfigure(1, weight=1)

        self._add_scale_row(path, "Waypoints (base)", self.waypoints_base, 1, 30, 1, 0, is_int=True)
        self._add_scale_row(path, "Variance (+/-)", self.waypoints_var, 0, 15, 1, 1, is_int=True)
        self._add_scale_row(path, "Min step distance (px)", self.min_step_px, 0, 800, 5, 2, is_int=True)

        self.safety = ttk.LabelFrame(grid, text="Safety", padding=10)
        self.safety.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(8, 0))
        self.safety.columnconfigure(1, weight=1)

        self._add_scale_row(self.safety, "Edge margin avoidance (px)", self.edge_margin, 0, 500, 1, 0, is_int=True)
        self._add_scale_row(self.safety, "Corner stop zone (px)", self.corner_safe_px, 5, 250, 1, 1, is_int=True)

        self.safe_preview = ttk.Label(self.safety, text="Safe area: calculating...", padding=(0, 6))
        self.safe_preview.grid(row=2, column=0, columnspan=3, sticky="w")

        # Stop on input checkbox
        self.stop_on_input_cb = ttk.Checkbutton(
            self.safety, text="Stop on any key press or mouse click (mouse movement ignored)",
            variable=self.stop_on_input
        )
        self.stop_on_input_cb.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        help_txt = (
            "Stop on input only triggers while movement is active.\n"
            "Press Escape in this window to stop immediately.\n"
            "Note: UI actions suppress stop-on-input briefly so Start and Move Now work normally."
        )
        self.safety_help = ttk.Label(self.safety, text=help_txt, foreground="#374151", padding=(0, 6), justify="left")
        self.safety_help.grid(row=4, column=0, columnspan=3, sticky="ew")
        self.safety.bind("<Configure>", self._on_safety_resize)

        logging = ttk.LabelFrame(grid, text="Logging", padding=10)
        logging.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(8, 0))
        logging.columnconfigure(1, weight=1)

        ttk.Label(logging, text="Log detail").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        self.log_combo = ttk.Combobox(
            logging, textvariable=self.log_level, values=["Off", "Cycle", "Segments"],
            state="readonly", width=12
        )
        self.log_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(logging, text="Move tick (ms)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        self._add_spin(logging, self.tick_ms, 5, 50, 1, row=1, col=1)

        note = "Lower tick improves stop responsiveness but uses more CPU. 10 to 20 ms is typical."
        self.logging_note = ttk.Label(logging, text=note, foreground="#374151", padding=(0, 6), justify="left")
        self.logging_note.grid(row=2, column=0, columnspan=2, sticky="ew")
        logging.bind("<Configure>", self._on_logging_resize)

        log_top = ttk.Frame(self.tab_log)
        log_top.pack(fill="x")

        self.clear_log_btn = ttk.Button(log_top, text="Clear", command=self.clear_log)
        self.copy_log_btn = ttk.Button(log_top, text="Copy", command=self.copy_log)
        self.clear_log_btn.pack(side="left", padx=(0, 6))
        self.copy_log_btn.pack(side="left")

        self.log_lines_var = ttk.Label(log_top, text="0 lines", padding=(12, 0))
        self.log_lines_var.pack(side="left")

        log_box = ttk.Frame(self.tab_log)
        log_box.pack(fill="both", expand=True, pady=(10, 0))

        self.log = tk.Text(log_box, height=18, wrap="none", font=("Consolas", 11))
        self.v_scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.h_scroll = ttk.Scrollbar(log_box, orient="horizontal", command=self.log.xview)
        self.log.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.log.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)

        self._log("Ready. Stop on input works anywhere while movement is active.")
        self._log("Any key press or mouse click stops movement. Mouse movement is ignored.")
        self._log("Press Escape in this window to stop immediately.")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_safety_resize(self, event):
        w = max(200, int(event.width) - 30)
        self.safety_help.configure(wraplength=w)

    def _on_logging_resize(self, event):
        w = max(200, int(event.width) - 30)
        self.logging_note.configure(wraplength=w)

    def _add_spin(self, parent, var, frm, to, step, row, col):
        sp = ttk.Spinbox(parent, from_=frm, to=to, increment=step, textvariable=var, width=10, justify="center")
        sp.grid(row=row, column=col, sticky="w", pady=6)
        sp.bind("<Return>", lambda e: self._normalize_int(var, frm, to))
        sp.bind("<FocusOut>", lambda e: self._normalize_int(var, frm, to))
        return sp

    def _add_scale_row(self, parent, label, var, frm, to, step, row, is_int):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=6)

        def on_scale(v):
            try:
                if is_int:
                    var.set(int(round(float(v))))
                else:
                    var.set(float(v))
            except Exception:
                return

        scale = tk.Scale(
            parent, from_=frm, to=to, orient="horizontal",
            showvalue=False, resolution=step, length=360,
            sliderlength=26, width=14, highlightthickness=0,
            command=on_scale
        )
        scale.grid(row=row, column=1, sticky="ew", pady=6)
        parent.columnconfigure(1, weight=1)

        def sync_to_scale(*_):
            try:
                scale.set(float(var.get()))
            except Exception:
                pass

        var.trace_add("write", sync_to_scale)
        sync_to_scale()

        if is_int:
            sp = ttk.Spinbox(parent, from_=int(frm), to=int(to), increment=int(step),
                             textvariable=var, width=10, justify="center")
            sp.bind("<Return>", lambda e: self._normalize_int(var, int(frm), int(to)))
            sp.bind("<FocusOut>", lambda e: self._normalize_int(var, int(frm), int(to)))
        else:
            sp = ttk.Spinbox(parent, from_=float(frm), to=float(to), increment=float(step),
                             textvariable=var, width=10, justify="center")
            sp.bind("<Return>", lambda e: self._normalize_float(var, float(frm), float(to)))
            sp.bind("<FocusOut>", lambda e: self._normalize_float(var, float(frm), float(to)))

        sp.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=6)

    def _normalize_int(self, var, mn, mx):
        try:
            v = int(round(float(var.get())))
        except Exception:
            v = mn
        var.set(clamp(v, mn, mx))

    def _normalize_float(self, var, mn, mx):
        try:
            v = float(var.get())
        except Exception:
            v = mn
        var.set(clamp(v, mn, mx))

    def _install_traces(self):
        for v in [
            self.interval_s, self.travel_time_s,
            self.waypoints_base, self.waypoints_var,
            self.edge_margin, self.corner_safe_px,
            self.min_step_px, self.tick_ms,
            self.log_level
        ]:
            v.trace_add("write", lambda *_: self._on_settings_changed())

    def _on_settings_changed(self):
        self._refresh_settings_snapshot()
        self._update_safe_area_preview()
        self._update_status_line()

    def _refresh_settings_snapshot(self):
        tick_s = max(0.005, int(self.tick_ms.get()) / 1000.0)
        snap = {
            "interval_s": float(self.interval_s.get()),
            "travel_time_s": float(self.travel_time_s.get()),
            "waypoints_base": int(self.waypoints_base.get()),
            "waypoints_var": int(self.waypoints_var.get()),
            "edge_margin": int(self.edge_margin.get()),
            "corner_safe_px": int(self.corner_safe_px.get()),
            "min_step_px": int(self.min_step_px.get()),
            "tick_s": tick_s,
            "log_level": str(self.log_level.get()),
        }
        with self._settings_lock:
            self._settings = snap

    def _get_settings_snapshot(self):
        with self._settings_lock:
            return dict(self._settings)

    def _update_safe_area_preview(self):
        w, h = pyautogui.size()
        edge = max(0, int(self.edge_margin.get()))
        corner = max(0, int(self.corner_safe_px.get()))
        safe = edge + corner

        min_x = clamp(safe, 0, w - 1)
        max_x = clamp(w - 1 - safe, 0, w - 1)
        min_y = clamp(safe, 0, h - 1)
        max_y = clamp(h - 1 - safe, 0, h - 1)

        if max_x <= min_x or max_y <= min_y:
            txt = f"Safe area collapsed. Screen {w}x{h}. Reduce Edge or Corner values."
        else:
            txt = f"Safe area X: {min_x} to {max_x}, Y: {min_y} to {max_y} (screen {w}x{h})"
        self.safe_preview.config(text=txt)

    def _update_status_line(self):
        s = self._get_settings_snapshot()
        n_base = s["waypoints_base"]
        n_var = s["waypoints_var"]
        n_min = max(1, n_base - n_var)
        n_max = max(n_min, n_base + n_var)
        self.status_text.config(
            text=f"Interval {s['interval_s']:.1f}s, Travel {s['travel_time_s']:.1f}s, "
                 f"Waypoints {n_min} to {n_max}, Edge {s['edge_margin']}px, "
                 f"CornerStop {s['corner_safe_px']}px, MinStep {s['min_step_px']}px"
        )

    def _set_status(self, state):
        if state == "Running":
            self.status_badge.config(text="Running", bg="#16a34a")
        elif state == "Paused":
            self.status_badge.config(text="Paused", bg="#d97706")
        elif state == "StoppedByFailsafe":
            self.status_badge.config(text="Stopped", bg="#dc2626")
        else:
            self.status_badge.config(text="Idle", bg="#6b7280")

    def _log(self, msg):
        def append():
            self.log.insert("end", msg + "\n")
            self._trim_log_lines(max_lines=500)
            self.log.see("end")
            self._update_log_line_count()
        self.after(0, append)

    def _trim_log_lines(self, max_lines=500):
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > max_lines:
            cut = lines - max_lines
            self.log.delete("1.0", f"{cut + 1}.0")

    def _update_log_line_count(self):
        lines = int(self.log.index("end-1c").split(".")[0])
        self.log_lines_var.config(text=f"{lines} lines")

    def clear_log(self):
        self.log.delete("1.0", "end")
        self._update_log_line_count()

    def copy_log(self):
        txt = self.log.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(txt)
        self._log("Log copied to clipboard.")

    def _set_buttons_running(self):
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text="Pause")
        self.stop_btn.config(state="normal")
        self.move_now_btn.config(state="normal")

    def _set_buttons_idle(self):
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="Pause")
        self.stop_btn.config(state="disabled")
        self.move_now_btn.config(state="normal")

    def start_worker(self):
        self._suppress_input_stop(0.45)

        if self.worker_thread and self.worker_thread.is_alive():
            self.pause_event.clear()
            self._set_status("Running")
            self._log("Resumed.")
            self._set_buttons_running()
            return

        self.stop_event.clear()
        self.pause_event.clear()
        self._refresh_settings_snapshot()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self._set_status("Running")
        self._log("Started.")
        self._set_buttons_running()

    def pause_worker(self):
        self._suppress_input_stop(0.45)

        if not self.worker_thread or not self.worker_thread.is_alive():
            return

        if not self.pause_event.is_set():
            self.pause_event.set()
            self._set_status("Paused")
            self._log("Paused.")
            self.pause_btn.config(text="Resume")
        else:
            self.pause_event.clear()
            self._set_status("Running")
            self._log("Resumed.")
            self.pause_btn.config(text="Pause")

    def stop_worker(self):
        self._suppress_input_stop(0.45)

        self.stop_event.set()
        self.pause_event.clear()

        if self.worker_thread and self.worker_thread.is_alive():
            self._log("Stopping...")
            self.worker_thread.join(timeout=2.0)

        self._set_status("Idle")
        self._log("Stopped.")
        self._set_buttons_idle()

    def move_once(self):
        self._suppress_input_stop(0.45)

        # ensure Move Now always runs even if previously stopped
        self.stop_event.clear()
        self.pause_event.clear()

        self.movement_active.set()
        try:
            self._refresh_settings_snapshot()
            settings = self._get_settings_snapshot()
            run_one_cycle(
                settings=settings,
                log_fn=self._log,
                should_stop_fn=lambda: self.stop_event.is_set() or self.pause_event.is_set()
            )
            self._log("Move Now: completed.")
        except RuntimeError as e:
            self._set_status("StoppedByFailsafe")
            self._log(str(e))
            messagebox.showwarning("Stopped", str(e))
        except Exception as e:
            self._log(f"Error: {e}")
        finally:
            self.movement_active.clear()

    def _worker_loop(self):
        self.movement_active.set()
        try:
            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue

                settings = self._get_settings_snapshot()

                try:
                    run_one_cycle(
                        settings=settings,
                        log_fn=self._log,
                        should_stop_fn=lambda: self.stop_event.is_set() or self.pause_event.is_set()
                    )
                except RuntimeError as e:
                    self._log(str(e))
                    self.stop_event.set()
                    self.after(0, lambda: self._set_status("StoppedByFailsafe"))
                    break
                except Exception as e:
                    self._log(f"Error during movement: {e}")

                interval = float(settings["interval_s"])
                start = time.time()
                while not self.stop_event.is_set() and not self.pause_event.is_set():
                    if (time.time() - start) >= interval:
                        break
                    time.sleep(0.05)
        finally:
            self.movement_active.clear()
            self.after(0, self._set_buttons_idle)
            if not self.stop_event.is_set():
                self.after(0, lambda: self._set_status("Idle"))

    def _on_close(self):
        self.stop_worker()
        self._stop_user_input_listeners()
        self.destroy()


if __name__ == "__main__":
    app = JiggleApp()
    app.mainloop()
