import threading
import time
import random
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui

def random_point(edge_margin):
    w, h = pyautogui.size()
    return (
        random.randint(edge_margin, max(edge_margin, w - edge_margin)),
        random.randint(edge_margin, max(edge_margin, h - edge_margin))
    )

def smooth_travel(path_points_min, path_points_max, total_travel_time, edge_margin, show_positions, log_fn):
    n_min = int(max(1, path_points_min))
    n_max = int(max(n_min, path_points_max))
    n_points = random.randint(n_min, n_max)
    waypoints = [random_point(edge_margin) for _ in range(n_points)]
    per_segment = max(0.1, float(total_travel_time) / n_points)
    for i, (x, y) in enumerate(waypoints, start=1):
        pyautogui.moveTo(x, y, duration=per_segment, tween=pyautogui.easeInOutQuad)
        if show_positions:
            now = datetime.datetime.now().strftime('%H:%M:%S')
            log_fn(f"[{now}] Segment {i}/{n_points}: moved to ({x}, {y})")

class JiggleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MousePresence Settings")
        self.geometry("1200x800")
        self.minsize(850, 650)
        self.option_add("*Font", "Arial 12")
        pyautogui.FAILSAFE = True
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.interval_s = tk.DoubleVar(value=60.0)
        self.points_min = tk.IntVar(value=3)
        self.points_max = tk.IntVar(value=5)
        self.travel_time_s = tk.DoubleVar(value=1.8)
        self.edge_margin = tk.IntVar(value=100)
        self.show_positions = tk.BooleanVar(value=True)
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(main, text="Settings", padding=10)
        controls.pack(side="top", fill="x")

        self._add_scale_with_spin(
            controls, "Interval (seconds)", self.interval_s,
            frm=5.0, to=120.0, step=1.0, row=0, is_int=False
        )
        self._add_scale_with_spin(
            controls, "Total travel time (seconds)", self.travel_time_s,
            frm=0.2, to=10.0, step=0.1, row=1, is_int=False
        )
        self._add_scale_with_spin(
            controls, "Waypoints MIN", self.points_min,
            frm=1, to=20, step=1, row=2, is_int=True
        )
        self._add_scale_with_spin(
            controls, "Waypoints MAX", self.points_max,
            frm=1, to=30, step=1, row=3, is_int=True
        )
        self._add_scale_with_spin(
            controls, "Edge margin (px)", self.edge_margin,
            frm=0, to=500, step=1, row=4, is_int=True
        )

        show_frame = ttk.Frame(controls)
        show_frame.grid(row=5, column=1, sticky="w", padx=6, pady=6)
        show_cb = ttk.Checkbutton(show_frame, text="Show positions in log", variable=self.show_positions)
        show_cb.pack(side="left")

        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=(8, 4))
        self.start_btn = ttk.Button(btns, text="Start", command=self.start_worker)
        self.pause_btn = ttk.Button(btns, text="Pause", command=self.pause_worker, state="disabled")
        self.stop_btn = ttk.Button(btns, text="Stop", command=self.stop_worker, state="disabled")
        self.move_now_btn = ttk.Button(btns, text="Move Now", command=self.move_once)
        self.start_btn.pack(side="left", padx=4)
        self.pause_btn.pack(side="left", padx=4)
        self.stop_btn.pack(side="left", padx=4)
        self.move_now_btn.pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="Idle")
        status = ttk.Label(main, textvariable=self.status_var, anchor="center")
        status.pack(fill="x", pady=(4, 4))

        log_frame = ttk.LabelFrame(main, text="Log", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=20, wrap="none", font=("Arial", 12))
        self.log.pack(fill="both", expand=True)
        self._log("Press Start to begin.\nMove mouse to a screen corner to abort pyautogui")

        self.points_min.trace_add("write", self._sync_waypoint_bounds)
        self.points_max.trace_add("write", self._sync_waypoint_bounds)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _add_scale_with_spin(self, parent, label, var, frm, to, step, row, is_int):
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", padx=6, pady=6)

        scl = tk.Scale(
            parent, from_=frm, to=to, orient="horizontal",
            showvalue=False, resolution=step, length=520,
            sliderlength=28, width=16, troughcolor="#e7f2ff",
            activebackground="#1976d2", highlightthickness=0,
            command=lambda v: (var.set(float(v)), self._update_status_values(), self._enforce_min_le_max())
        )
        scl.grid(row=row, column=1, sticky="ew", padx=6, pady=6)
        parent.grid_columnconfigure(1, weight=1)

        def sync_var_to_scale(*_):
            try:
                scl.set(float(var.get()))
            except Exception:
                pass

        var.trace_add("write", lambda *_: sync_var_to_scale())

        if is_int:
            spin = ttk.Spinbox(parent, from_=int(frm), to=int(to), increment=int(step),
                               textvariable=var, width=8, justify="center")
        else:
            spin = ttk.Spinbox(parent, from_=float(frm), to=float(to), increment=float(step),
                               textvariable=var, width=8, justify="center")
        spin.grid(row=row, column=2, sticky="e", padx=6)

        spin.bind("<Return>", lambda e, v=var, mn=frm, mx=to, i=is_int: self._normalize_entry(v, mn, mx, i))
        spin.bind("<FocusOut>", lambda e, v=var, mn=frm, mx=to, i=is_int: self._normalize_entry(v, mn, mx, i))

    def _normalize_entry(self, var, mn, mx, is_int):
        try:
            val = float(var.get())
        except Exception:
            val = mn
        if val < mn:
            val = mn
        if val > mx:
            val = mx
        if is_int:
            val = int(round(val))
        var.set(val)
        self._update_status_values()
        self._enforce_min_le_max()

    def _update_status_values(self):
        self.status_var.set(
            f"Interval={self.interval_s.get():.1f}s | Travel={self.travel_time_s.get():.1f}s | "
            f"Waypoints={int(self.points_min.get())}-{int(self.points_max.get())} | Edge={int(self.edge_margin.get())} px"
        )

    def _enforce_min_le_max(self):
        try:
            mn = int(self.points_min.get())
            mx = int(self.points_max.get())
        except tk.TclError:
            return
        if mx < mn:
            self.points_max.set(mn)

    def _sync_waypoint_bounds(self, *args):
        self._enforce_min_le_max()

    def _log(self, msg):
        self.log.insert("end", msg + "\n", ("center",))
        self.log.see("end")

    def start_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.pause_event.clear()
            self.status_var.set("Running")
            self._log("Resumed.")
            self._set_buttons_running()
            return
        self.stop_event.clear()
        self.pause_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self._log("Started.")
        self.status_var.set("Running")
        self._set_buttons_running()

    def pause_worker(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            return
        if not self.pause_event.is_set():
            self.pause_event.set()
            self._log("Paused.")
            self.status_var.set("Paused")
            self.pause_btn.config(text="Resume")
        else:
            self.pause_event.clear()
            self._log("Resumed.")
            self.status_var.set("Running")
            self.pause_btn.config(text="Pause")

    def stop_worker(self):
        self.stop_event.set()
        self.pause_event.clear()
        if self.worker_thread and self.worker_thread.is_alive():
            self._log("Stopping…")
            self.worker_thread.join(timeout=2.0)
        self._log("Stopped.")
        self.status_var.set("Idle")
        self._set_buttons_idle()

    def move_once(self):
        try:
            smooth_travel(
                path_points_min=self.points_min.get(),
                path_points_max=self.points_max.get(),
                total_travel_time=self.travel_time_s.get(),
                edge_margin=int(self.edge_margin.get()),
                show_positions=self.show_positions.get(),
                log_fn=self._log
            )
            self._log("Move Now: completed.")
        except pyautogui.FailSafeException:
            self._log("PyAutoGUI failsafe triggered (mouse hit a corner).")
            messagebox.showwarning("Failsafe", "Failsafe triggered: mouse moved to screen corner.")
        except Exception as e:
            self._log(f"Error during Move Now: {e}")

    def _worker_loop(self):
        try:
            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                try:
                    smooth_travel(
                        path_points_min=self.points_min.get(),
                        path_points_max=self.points_max.get(),
                        total_travel_time=self.travel_time_s.get(),
                        edge_margin=int(self.edge_margin.get()),
                        show_positions=self.show_positions.get(),
                        log_fn=self._log
                    )
                except pyautogui.FailSafeException:
                    self._log("PyAutoGUI failsafe triggered (mouse hit a corner). Stopping.")
                    self.stop_event.set()
                    break
                except Exception as e:
                    self._log(f"Error during movement: {e}")
                remaining = float(self.interval_s.get())
                start = time.time()
                while not self.stop_event.is_set() and not self.pause_event.is_set():
                    elapsed = time.time() - start
                    if elapsed >= remaining:
                        break
                    time.sleep(0.1)
        finally:
            self.after(0, self._set_buttons_idle)
            self.after(0, lambda: self.status_var.set("Idle"))

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

    def _on_close(self):
        self.stop_worker()
        self.destroy()

if __name__ == "__main__":
    app = JiggleApp()
    app.mainloop()
