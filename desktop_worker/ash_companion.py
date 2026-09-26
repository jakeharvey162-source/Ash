from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import webbrowser
import tkinter as tk

ASH_URL = "https://meet-ash.jakeharvey162.workers.dev/"


class AshCompanion:
    """Small always-on-top Ash presence inspired by the user's desktop-companion reference."""

    def __init__(self, pair_code: str = "", start_worker: bool = True) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.94)
        except Exception:
            pass
        self.root.configure(bg="#050608")
        self.root.geometry("196x88+32+120")
        self.drag_x = 0
        self.drag_y = 0
        self.phase = 0
        self.preferences_path = pathlib.Path.home() / ".ash" / "preferences.json"
        self.name = self._assistant_name()

        frame = tk.Frame(self.root, bg="#050608", highlightbackground="#313743", highlightthickness=1)
        frame.pack(fill="both", expand=True)

        self.orb = tk.Canvas(frame, width=58, height=58, bg="#050608", highlightthickness=0)
        self.orb.place(x=12, y=14)
        self.ring = self.orb.create_oval(8, 8, 50, 50, outline="#d8dde8", width=2)
        self.core = self.orb.create_oval(18, 18, 40, 40, fill="#f5f7fb", outline="")
        self.letter = self.orb.create_text(29, 29, text="A", fill="#07090d", font=("Segoe UI", 12, "bold"))

        self.title = tk.Label(frame, text=self.name, fg="#f5f7fb", bg="#050608", font=("Segoe UI", 11, "bold"))
        self.title.place(x=78, y=17)
        self.state = tk.Label(frame, text="desktop companion", fg="#89909e", bg="#050608", font=("Segoe UI", 8))
        self.state.place(x=78, y=40)
        self.hint = tk.Label(frame, text="double-click to open Ash", fg="#646b78", bg="#050608", font=("Segoe UI", 7))
        self.hint.place(x=78, y=59)

        for widget in (frame, self.orb, self.title, self.state, self.hint):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<Double-Button-1>", lambda _event: webbrowser.open(ASH_URL))

        frame.bind("<Button-3>", self._menu)
        self.worker = None
        if start_worker:
            self._start_worker(pair_code)
        self._animate()

    def _assistant_name(self) -> str:
        try:
            data = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            return str(data.get("assistant_name") or "Ash")
        except Exception:
            return "Ash"

    def _start_worker(self, pair_code: str) -> None:
        script = pathlib.Path(__file__).with_name("remote_worker.py")
        args = [sys.executable, str(script)]
        if pair_code:
            args += ["--pair", pair_code]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.worker = subprocess.Popen(
                args,
                cwd=str(script.parent),
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.state.config(text="worker online · ready")
        except Exception:
            self.state.config(text="worker could not start")

    def _drag_start(self, event) -> None:
        self.drag_x = event.x_root - self.root.winfo_x()
        self.drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event) -> None:
        self.root.geometry(f"+{event.x_root-self.drag_x}+{event.y_root-self.drag_y}")

    def _menu(self, event) -> None:
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Open Ash", command=lambda: webbrowser.open(ASH_URL))
        menu.add_command(label="Hide companion", command=self.root.withdraw)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.close)
        menu.tk_popup(event.x_root, event.y_root)

    def _animate(self) -> None:
        self.phase = (self.phase + 1) % 40
        pulse = abs(20 - self.phase) / 20
        inset = int(5 + pulse * 3)
        self.orb.coords(self.ring, inset, inset, 58 - inset, 58 - inset)
        name = self._assistant_name()
        if name != self.name:
            self.name = name
            self.title.config(text=name)
        self.root.after(70, self._animate)

    def close(self) -> None:
        if self.worker and self.worker.poll() is None:
            try:
                self.worker.terminate()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ash always-on-top desktop companion")
    parser.add_argument("--pair", default="", help="Optional one-time pairing code from Ash")
    parser.add_argument("--no-worker", action="store_true", help="Show the companion without starting the remote worker")
    args = parser.parse_args()
    AshCompanion(pair_code=args.pair, start_worker=not args.no_worker).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
