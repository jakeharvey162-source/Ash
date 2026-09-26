from __future__ import annotations

import json
import os
import pathlib
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent

class AshCompanion:
    """Always-on-top desktop companion inspired by the supplied Dexter-style overlay."""

    BG = "#010203"
    PANEL = "#0a0d12"
    CYAN = "#47e8ff"
    CYAN_2 = "#8ff4ff"
    TEXT = "#f4f7fb"
    MUTED = "#9aa7b8"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Ash Companion")
        self.root.geometry("230x250+40+50")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.BG)
        try:
            self.root.wm_attributes("-transparentcolor", self.BG)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self.root, width=230, height=250, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.events: queue.Queue[dict] = queue.Queue()
        self.proc: subprocess.Popen[str] | None = None
        self.drag_origin = None
        self.state = "idle"
        self.pulse = 0
        self.last_text = "Ash is ready."
        self.hidden_until = 0.0

        self._draw()
        self._bind()
        self._start_voice_runtime()
        self.root.after(60, self._tick)
        self.root.after(80, self._poll_events)

    def _bind(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "drag_origin", None))
        self.canvas.bind("<Double-Button-1>", lambda _e: self._open_ash())
        self.canvas.bind("<Button-3>", self._menu)

    def _drag_start(self, event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event) -> None:
        if not self.drag_origin:
            return
        ox, oy = self.drag_origin
        self.root.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def _menu(self, event) -> None:
        menu = tk.Menu(self.root, tearoff=0, bg=self.PANEL, fg=self.TEXT, activebackground="#17202a", activeforeground=self.TEXT)
        menu.add_command(label="Open Ash", command=self._open_ash)
        menu.add_command(label="Restart voice", command=self._restart_voice_runtime)
        menu.add_separator()
        menu.add_command(label="Hide 10 minutes", command=self._hide_temporarily)
        menu.add_command(label="Quit companion", command=self.close)
        menu.tk_popup(event.x_root, event.y_root)

    def _open_ash(self) -> None:
        url = os.environ.get("ASH_APP_URL", "https://meet-ash.jakeharvey162.workers.dev/")
        webbrowser.open(url)

    def _hide_temporarily(self) -> None:
        self.hidden_until = time.time() + 600
        self.root.withdraw()
        self.root.after(600_000, self._show_again)

    def _show_again(self) -> None:
        if time.time() >= self.hidden_until:
            self.root.deiconify()
            self.root.attributes("-topmost", True)

    def _start_voice_runtime(self) -> None:
        if os.environ.get("ASH_COMPANION_VOICE", "1").strip().lower() in {"0", "false", "no", "off"}:
            self.last_text = "Voice disabled. Double-click to open Ash."
            return
        self._stop_voice_runtime()
        env = os.environ.copy()
        cmd = [sys.executable, "-m", "voice_runtime.runtime"]
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self.last_text = f"Voice runtime unavailable: {exc}"
            return
        threading.Thread(target=self._read_voice_events, daemon=True).start()

    def _restart_voice_runtime(self) -> None:
        self.last_text = "Restarting voice…"
        self.state = "thinking"
        self._start_voice_runtime()

    def _stop_voice_runtime(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None

    def _read_voice_events(self) -> None:
        proc = self.proc
        if not proc or not proc.stdout:
            return
        for raw in proc.stdout:
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except Exception:
                continue
            if isinstance(event, dict):
                self.events.put(event)

    def _poll_events(self) -> None:
        changed = False
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
                changed = True
        except queue.Empty:
            pass
        if changed:
            self._draw()
        self.root.after(80, self._poll_events)

    def _handle_event(self, event: dict) -> None:
        typ = str(event.get("type") or "")
        if typ in {"boot", "warming_up"}:
            self.state = "thinking"
            self.last_text = "Warming up…"
        elif typ == "ready":
            self.state = "idle"
            self.last_text = "Ready. Say the wake word."
        elif typ == "listening":
            self.state = "listening"
            self.last_text = "Listening…"
        elif typ == "wake":
            self.state = "wake"
            self.last_text = "Yeah?"
        elif typ == "heard":
            self.state = "listening"
            self.last_text = str(event.get("text") or "I heard you.")[:110]
        elif typ == "thinking":
            self.state = "thinking"
            self.last_text = "Thinking…"
        elif typ == "narration":
            self.state = "speaking"
            text = str(event.get("text") or "")
            self.last_text = text[:110] + ("…" if len(text) > 110 else "")
        elif typ == "done":
            self.state = "idle"
            text = str(event.get("text") or "Done.")
            self.last_text = text[:110] + ("…" if len(text) > 110 else "")
        elif typ == "runtime_error":
            self.state = "error"
            self.last_text = "Voice needs attention. Right-click to restart."

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")

        # Bubble
        c.create_round_rect = getattr(c, "create_round_rect", None)
        self._rounded_rect(10, 8, 220, 94, 18, fill=self.PANEL, outline="#1f2a36", width=1)
        c.create_text(24, 24, text="ASH", anchor="nw", fill=self.CYAN_2, font=("Segoe UI Semibold", 9))
        c.create_text(24, 44, text=self.last_text, anchor="nw", width=178, fill=self.TEXT, font=("Segoe UI", 9))

        # Tail
        c.create_polygon(145, 94, 170, 94, 158, 110, fill=self.PANEL, outline="#1f2a36")

        # Orb / mascot
        cx, cy = 158, 165
        pulse = self.pulse
        halo = 41 + pulse
        c.create_oval(cx-halo, cy-halo, cx+halo, cy+halo, outline="#173745", width=2)
        c.create_oval(cx-34, cy-34, cx+34, cy+34, fill="#071117", outline=self.CYAN, width=2)
        c.create_oval(cx-25, cy-25, cx+25, cy+25, fill="#0b1d27", outline="#2a90a3", width=1)
        c.create_arc(cx-24, cy-24, cx+24, cy+24, start=30, extent=120, style="arc", outline=self.CYAN_2, width=3)
        c.create_text(cx, cy+2, text="A", fill=self.TEXT, font=("Segoe UI Semibold", 18))

        # Tiny status LED
        state_color = {
            "listening": "#52ffa8",
            "wake": "#52ffa8",
            "thinking": "#ffd76a",
            "speaking": self.CYAN,
            "error": "#ff667d",
        }.get(self.state, "#6f7d8c")
        c.create_oval(cx+22, cy-29, cx+31, cy-20, fill=state_color, outline="")

        # Small instruction
        c.create_text(158, 224, text="drag · double-click · right-click", fill=self.MUTED, font=("Segoe UI", 7))

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
            x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
            x1,y2, x1,y2-r, x1,y1+r, x1,y1
        ]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _tick(self) -> None:
        self.pulse = (self.pulse + 1) % 8
        self._draw()
        self.root.after(85 if self.state in {"listening", "speaking"} else 130, self._tick)

    def close(self) -> None:
        self._stop_voice_runtime()
        self.root.destroy()

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()

if __name__ == "__main__":
    AshCompanion().run()
