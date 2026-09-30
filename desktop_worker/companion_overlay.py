from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import queue
import random
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import webbrowser
import urllib.request
from build_version import BUILD_VERSION, LATEST_RELEASE_API, RELEASES_URL

ROOT = pathlib.Path(__file__).resolve().parent
APP_DIR = pathlib.Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
ASH_URL = os.environ.get("ASH_APP_URL", "https://meet-ash.jakeharvey162.workers.dev/")


class AshScreenAura:
    """Click-through full-screen ambient glow tied to Ash's real runtime state."""

    def __init__(self, master: tk.Tk, state_getter, color_getter, transparent: str) -> None:
        self.master = master
        self.state_getter = state_getter
        self.color_getter = color_getter
        self.transparent = transparent
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=transparent)
        try:
            self.window.wm_attributes("-transparentcolor", transparent)
        except tk.TclError:
            pass
        sw, sh = master.winfo_screenwidth(), master.winfo_screenheight()
        self.window.geometry(f"{sw}x{sh}+0+0")
        self.canvas = tk.Canvas(
            self.window, width=sw, height=sh, bg=transparent,
            highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.phase = 0.0
        self._click_through_ready = False
        self.window.after(100, self._make_click_through)
        self.window.after(70, self._tick)

    @staticmethod
    def _hex_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

    @classmethod
    def _blend(cls, a: str, b: str, t: float) -> str:
        ar, ag, ab = cls._hex_rgb(a)
        br, bg, bb = cls._hex_rgb(b)
        t = max(0.0, min(1.0, t))
        return "#%02x%02x%02x" % (
            int(ar + (br-ar)*t), int(ag + (bg-ag)*t), int(ab + (bb-ab)*t)
        )

    def _make_click_through(self) -> None:
        if os.name != "nt":
            return
        try:
            import ctypes
            hwnd = self.window.winfo_id()
            get_style = ctypes.windll.user32.GetWindowLongW
            set_style = ctypes.windll.user32.SetWindowLongW
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            style = get_style(hwnd, GWL_EXSTYLE)
            set_style(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            self._click_through_ready = True
        except Exception:
            self._click_through_ready = False

    def _tick(self) -> None:
        try:
            state = str(self.state_getter() or "idle")
            accent = str(self.color_getter() or "#57e6ff")
            self.phase += 0.11
            self._draw(state, accent)
            self.window.after(70, self._tick)
        except tk.TclError:
            return

    def _draw(self, state: str, accent: str) -> None:
        self.canvas.delete("all")
        if state == "idle":
            return
        strength = {
            "listening": 0.68, "wake": 0.92, "thinking": 0.78, "speaking": 0.72,
            "building": 0.76, "acting": 0.86, "offline": 0.38, "error": 0.94,
        }.get(state, 0.48)
        pulse = 0.78 + 0.22 * abs(math.sin(self.phase * (1.8 if state == "thinking" else 1.15)))
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10 or h < 10:
            return
        thickness = 54 if state in {"wake", "acting", "error"} else 40
        layers = 11
        for i in range(layers, 0, -1):
            d = max(1, int(thickness * i / layers))
            fade = 0.90 - (i / layers) * 0.43 * strength * pulse
            col = self._blend(accent, self.transparent, min(0.96, fade))
            self.canvas.create_rectangle(0, 0, w, d, fill=col, outline="")
            self.canvas.create_rectangle(0, h-d, w, h, fill=col, outline="")
            self.canvas.create_rectangle(0, 0, d, h, fill=col, outline="")
            self.canvas.create_rectangle(w-d, 0, w, h, fill=col, outline="")
        # Corner energy nodes make the aura read as a deliberate Ash HUD.
        node = self._blend(accent, "#ffffff", 0.34)
        radius = 3 + int(2 * pulse)
        for x, y in ((18, 18), (w-18, 18), (18, h-18), (w-18, h-18)):
            self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=node, outline="")

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass


class AshHologramCompanion:
    """Always-on-top holographic Ash desktop companion.

    The companion is intentionally rendered with Tkinter primitives so the
    default desktop experience has no additional UI dependency. Voice and
    worker processes remain separate and permissioned.
    """

    TRANSPARENT = "#010203"
    PANEL = "#061017"
    TEXT = "#ecfbff"
    MUTED = "#83a7b4"

    STATE = {
        "idle": ("#57e6ff", "READY"),
        "listening": ("#55ffb3", "LISTENING"),
        "wake": ("#9affd2", "AWAKE"),
        "thinking": ("#ffd66b", "THINKING"),
        "speaking": ("#59e8ff", "SPEAKING"),
        "building": ("#53f6a6", "BUILDING"),
        "acting": ("#9b8cff", "ACTING"),
        "offline": ("#b68cff", "LOCAL"),
        "error": ("#ff6f86", "ATTENTION"),
    }

    def __init__(
        self,
        *,
        pair_code: str = "",
        start_worker: bool = True,
        start_voice: bool = True,
        compact: bool = False,
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Ash Hologram")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.TRANSPARENT)
        try:
            self.root.wm_attributes("-transparentcolor", self.TRANSPARENT)
        except tk.TclError:
            pass

        self.width = 356
        self.height = 492
        self.compact = compact
        self.state = "idle"
        self.last_text = "Ash is ready."
        self.detail = "Say “Ash” or double-click to open command center."
        self.phase = 0.0
        self.blink = 0.0
        self.next_blink = time.time() + random.uniform(2.2, 5.0)
        self.drag_origin: tuple[int, int] | None = None
        self.hidden_until = 0.0
        self.events: queue.Queue[dict] = queue.Queue()
        self.worker: subprocess.Popen[str] | None = None
        self.voice: subprocess.Popen[str] | None = None
        self.worker_online = False
        self.voice_online = False
        self.hotkey_down = False
        self.update_available = ""

        self.settings_path = pathlib.Path.home() / ".ash" / "companion.json"
        self.preferences_path = pathlib.Path.home() / ".ash" / "preferences.json"
        self.assistant_name = self._assistant_name()
        x, y = self._saved_position()
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.aura = AshScreenAura(
            self.root,
            state_getter=lambda: self.state,
            color_getter=lambda: self._color()[0],
            transparent=self.TRANSPARENT,
        )
        self.particles = [
            {
                "x": random.uniform(118, 288),
                "y": random.uniform(130, 410),
                "r": random.uniform(0.7, 2.2),
                "s": random.uniform(0.25, 0.85),
                "p": random.uniform(0, math.tau),
            }
            for _ in range(36)
        ]

        self._bind()
        if start_worker:
            if pair_code or self._device_config_exists():
                self._start_worker(pair_code)
            else:
                self.worker_online = False
                self.detail = "Link this computer to unlock Ash desktop actions."
                self.root.after(850, self._first_run_setup)
        if start_voice:
            self._start_voice_runtime()

        self.root.after(60, self._poll_events)
        self.root.after(33, self._tick)
        self.root.after(3200, lambda: threading.Thread(target=self._check_for_updates, daemon=True).start())

    def _assistant_name(self) -> str:
        try:
            data = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            return str(data.get("assistant_name") or "Ash")[:24]
        except Exception:
            return "Ash"

    def _saved_position(self) -> tuple[int, int]:
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return max(0, int(data.get("x", 36))), max(0, int(data.get("y", 72)))
        except Exception:
            return 36, 72

    def _save_position(self) -> None:
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(
                    {"x": self.root.winfo_x(), "y": self.root.winfo_y(), "compact": self.compact},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _device_config_exists(self) -> bool:
        path = pathlib.Path(os.environ.get("ASH_DEVICE_CONFIG", str(pathlib.Path.home() / ".ash" / "device.json"))).expanduser()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return bool(data.get("device_id") and data.get("device_secret"))
        except Exception:
            return False

    def _first_run_setup(self) -> None:
        if self._device_config_exists() or self.worker_online:
            return
        answer = messagebox.askyesno(
            "Link Ash to this computer",
            "Ash is running. To let the hologram build projects, use local tools and control this computer when you approve it, link this desktop to your Ash account now.\n\nOpen Ash in your browser, go to Preferences → Linked computers → Link a computer, then copy the one-time code.\n\nLink now?",
            parent=self.root,
        )
        if answer:
            self._link_computer()
        else:
            self.state = "offline"
            self.last_text = "Visual + local mode."
            self.detail = "Right-click Ash and choose “Link this computer” when ready."

    def _link_computer(self) -> None:
        code = simpledialog.askstring(
            "Link this computer",
            "Paste the one-time pairing code from Ash:",
            parent=self.root,
        )
        if code is None:
            return
        clean = str(code).strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{6,32}", clean):
            messagebox.showerror("Invalid pairing code", "That pairing code does not look valid. Generate a fresh code in Ash and try again.", parent=self.root)
            return
        self.state = "thinking"
        self.last_text = "Linking this computer…"
        self.detail = "Using the one-time Ash pairing code."
        self._start_worker(clean)

    def _worker_command(self, pair_code: str = "") -> list[str]:
        if getattr(sys, "frozen", False):
            exe = APP_DIR / ("AshWorker.exe" if os.name == "nt" else "AshWorker")
            if not exe.exists():
                raise FileNotFoundError(f"Packaged Ash worker is missing: {exe}")
            args = [str(exe)]
        else:
            args = [sys.executable, str(ROOT / "remote_worker.py")]
        if pair_code:
            args += ["--pair", pair_code]
        return args

    def _voice_command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            exe = APP_DIR / ("AshVoice.exe" if os.name == "nt" else "AshVoice")
            if not exe.exists():
                raise FileNotFoundError(f"Packaged Ash voice runtime is missing: {exe}")
            return [str(exe)]
        return [sys.executable, "-m", "voice_runtime.runtime"]

    def _bind(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Double-Button-1>", lambda _event: self._open_ash())
        self.canvas.bind("<Button-2>", lambda _event: self._toggle_compact())
        self.canvas.bind("<Button-3>", self._menu)
        self.root.bind("<Escape>", lambda _event: self._toggle_compact())

    def _drag_start(self, event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event) -> None:
        if not self.drag_origin:
            return
        ox, oy = self.drag_origin
        self.root.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def _drag_end(self, _event) -> None:
        self.drag_origin = None
        self._save_position()

    def _open_ash(self) -> None:
        webbrowser.open(ASH_URL)

    def _poll_global_hotkey(self) -> None:
        """Ctrl+Alt+A summons Ash on Windows without an extra dependency."""
        if os.name != "nt":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            down = all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x41))
            if down and not self.hotkey_down:
                self.root.deiconify()
                self.root.lift()
                self.root.attributes("-topmost", True)
                self.state = "wake"
                self.last_text = "I'm here."
                self.detail = "Ctrl+Alt+A summoned Ash. Double-click for the command center."
            self.hotkey_down = bool(down)
        except Exception:
            self.hotkey_down = False

    def _toggle_compact(self) -> None:
        self.compact = not self.compact
        self._save_position()
        self._draw()

    def _hide_temporarily(self, seconds: int = 600) -> None:
        self.hidden_until = time.time() + seconds
        self.root.withdraw()
        self.root.after(seconds * 1000, self._show_again)

    def _show_again(self) -> None:
        if time.time() >= self.hidden_until:
            self.root.deiconify()
            self.root.attributes("-topmost", True)

    def _menu(self, event) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#071016",
            fg=self.TEXT,
            activebackground="#12232d",
            activeforeground=self.TEXT,
            bd=0,
        )
        menu.add_command(label="Open Ash command center", command=self._open_ash)
        menu.add_command(label="Link this computer", command=self._link_computer)
        menu.add_command(label="Compact / expand", command=self._toggle_compact)
        menu.add_command(label="Restart voice", command=self._restart_voice_runtime)
        menu.add_command(label="Restart desktop worker", command=self._restart_worker)
        menu.add_command(label="Check for updates", command=lambda: threading.Thread(target=self._check_for_updates, kwargs={"manual": True}, daemon=True).start())
        if self.update_available:
            menu.add_command(label=f"Install update {self.update_available}", command=lambda: webbrowser.open(RELEASES_URL))
        menu.add_separator()
        menu.add_command(label="Hide 10 minutes", command=self._hide_temporarily)
        menu.add_command(label="Quit Ash companion", command=self.close)
        menu.tk_popup(event.x_root, event.y_root)

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, int, int]:
        match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
        return tuple(int(x) for x in match.groups()) if match else (0, 0, 0)

    def _check_for_updates(self, manual: bool = False) -> None:
        try:
            request = urllib.request.Request(
                LATEST_RELEASE_API,
                headers={"User-Agent": f"AshDesktop/{BUILD_VERSION}", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(request, timeout=7) as response:
                payload = json.loads(response.read(512_000).decode("utf-8"))
            latest = str(payload.get("tag_name") or "").strip().lstrip("v")
            url = str(payload.get("html_url") or RELEASES_URL)
            if latest and self._version_tuple(latest) > self._version_tuple(BUILD_VERSION):
                self.events.put({"type": "update_available", "version": latest, "url": url, "source": "updater"})
            elif manual:
                self.events.put({"type": "update_current", "version": BUILD_VERSION, "source": "updater"})
        except Exception as exc:
            if manual:
                self.events.put({"type": "update_error", "message": str(exc)[:120], "source": "updater"})

    def _start_worker(self, pair_code: str = "") -> None:
        self._stop_worker()
        try:
            args = self._worker_command(pair_code)
        except Exception as exc:
            self.worker = None
            self.worker_online = False
            self.state = "error"
            self.last_text = "Desktop worker is unavailable."
            self.detail = str(exc)[:92]
            return
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.worker = subprocess.Popen(
                args,
                cwd=str(APP_DIR),
                creationflags=flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            self.worker_online = True
            threading.Thread(target=self._read_worker_events, daemon=True).start()
        except Exception:
            self.worker = None
            self.worker_online = False

    def _read_worker_events(self) -> None:
        proc = self.worker
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
                event.setdefault("source", "worker")
                self.events.put(event)

    def _restart_worker(self) -> None:
        self.last_text = "Restarting desktop worker…"
        self.state = "thinking"
        self._start_worker()

    def _stop_worker(self) -> None:
        proc = self.worker
        self.worker = None
        self.worker_online = False
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _start_voice_runtime(self) -> None:
        if os.environ.get("ASH_COMPANION_VOICE", "1").strip().lower() in {"0", "false", "no", "off"}:
            self.voice_online = False
            self.detail = "Voice disabled. Double-click to open Ash."
            return
        self._stop_voice_runtime()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.voice = subprocess.Popen(
                self._voice_command(),
                cwd=str(APP_DIR),
                env=os.environ.copy(),
                creationflags=flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            self.voice_online = True
            threading.Thread(target=self._read_voice_events, daemon=True).start()
        except Exception:
            self.voice = None
            self.voice_online = False
            self.state = "error"
            self.detail = "Voice runtime could not start."

    def _restart_voice_runtime(self) -> None:
        self.state = "thinking"
        self.last_text = "Restarting voice…"
        self._start_voice_runtime()

    def _stop_voice_runtime(self) -> None:
        proc = self.voice
        self.voice = None
        self.voice_online = False
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _read_voice_events(self) -> None:
        proc = self.voice
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
                self._handle_event(self.events.get_nowait())
                changed = True
        except queue.Empty:
            pass
        if changed:
            self._draw()
        self.root.after(70, self._poll_events)

    def _handle_event(self, event: dict) -> None:
        typ = str(event.get("type") or "")
        source = str(event.get("source") or "voice")
        if source == "updater":
            if typ == "update_available":
                self.update_available = str(event.get("version") or "")
                self.state = "wake"
                self.last_text = f"Ash {self.update_available} is ready."
                self.detail = "Right-click the hologram to open the verified release."
                return
            if typ == "update_current":
                self.state = "idle"
                self.last_text = "Ash is up to date."
                self.detail = f"Installed version {event.get('version') or BUILD_VERSION}."
                return
            if typ == "update_error":
                self.state = "error"
                self.last_text = "Update check failed."
                self.detail = "Ash can keep running. Try again from the right-click menu."
                return
        if source == "worker":
            if typ == "worker_ready":
                self.worker_online = True
                self.state = "idle"
                self.last_text = "Desktop agent online."
                caps = event.get("capabilities") if isinstance(event.get("capabilities"), dict) else {}
                active = [k.replace("_", " ") for k, v in caps.items() if v is True]
                self.detail = (" · ".join(active[:4]) or "Local tools are ready.")[:96]
                return
            if typ == "worker_task":
                state = str(event.get("state") or "thinking")
                self.state = state if state in self.STATE else "thinking"
                label = str(event.get("label") or "").strip()
                self.last_text = label[:96] or "Working on it."
                self.detail = "Ash desktop agent is executing this task."
                return
            if typ == "worker_done":
                self.state = "idle"
                self.last_text = "Desktop task finished."
                self.detail = "Ready for your next command."
                return
            if typ == "worker_error":
                self.state = "error"
                self.last_text = "Desktop task needs attention."
                self.detail = str(event.get("message") or "A local task failed.")[:96]
                return
            if typ == "schedule_task":
                self.state = "thinking"
                self.last_text = str(event.get("label") or "Scheduled task")[:96]
                self.detail = "Running a local Ash automation."
                return
            if typ == "schedule_done":
                self.state = "idle" if event.get("ok") else "error"
                self.last_text = "Scheduled task complete." if event.get("ok") else "Scheduled task needs attention."
                self.detail = "Ash local scheduler finished this run."
                return
        if typ in {"boot", "warming_up"}:
            self.state = "thinking"
            self.last_text = "Warming up local systems…"
            self.detail = "Voice, memory and intelligence are coming online."
        elif typ == "ready":
            self.state = "idle"
            self.last_text = "I'm here."
            self.detail = "Say the wake word whenever you need me."
            self.voice_online = True
        elif typ == "listening":
            self.state = "listening"
            self.last_text = "Listening…"
            self.detail = "Waiting for your wake word."
        elif typ == "wake":
            self.state = "wake"
            self.last_text = "Yeah?"
            self.detail = "Go ahead."
        elif typ == "heard":
            text = str(event.get("text") or "").strip()
            self.state = "listening"
            self.last_text = text[:96] or "I heard you."
            self.detail = "Got it."
        elif typ == "thinking":
            self.state = "thinking"
            self.last_text = "On it."
            self.detail = "Reasoning across Ash's available specialists."
        elif typ == "narration":
            text = str(event.get("text") or "").strip()
            self.state = "speaking"
            self.last_text = text[:128] + ("…" if len(text) > 128 else "")
            self.detail = "Speaking"
        elif typ == "done":
            text = str(event.get("text") or "").strip()
            self.state = "idle"
            self.last_text = text[:128] + ("…" if len(text) > 128 else "") if text else "Done."
            self.detail = "Ready for your next command."
        elif typ == "runtime_error":
            self.state = "error"
            self.last_text = "Voice needs attention."
            self.detail = str(event.get("message") or "Right-click to restart voice.")[:92]
            self.voice_online = False

    @staticmethod
    def _hex_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _blend(a: str, b: str, t: float) -> str:
        ar, ag, ab = AshHologramCompanion._hex_rgb(a)
        br, bg, bb = AshHologramCompanion._hex_rgb(b)
        t = max(0.0, min(1.0, t))
        return "#%02x%02x%02x" % (
            int(ar + (br - ar) * t),
            int(ag + (bg - ag) * t),
            int(ab + (bb - ab) * t),
        )

    def _color(self) -> tuple[str, str]:
        return self.STATE.get(self.state, self.STATE["idle"])

    def _glow_oval(self, x1, y1, x2, y2, color: str, layers: int = 5, width: int = 1) -> None:
        for i in range(layers, 0, -1):
            d = i * 3
            shade = self._blend(color, self.TRANSPARENT, min(0.86, 0.58 + i * 0.055))
            self.canvas.create_oval(x1 - d, y1 - d, x2 + d, y2 + d, outline=shade, width=width)
        self.canvas.create_oval(x1, y1, x2, y2, outline=color, width=max(1, width + 1))

    def _line(self, *coords: float, fill: str, width: int = 2, smooth: bool = False) -> None:
        self.canvas.create_line(*coords, fill=fill, width=width, smooth=smooth, capstyle=tk.ROUND)

    def _draw_panel(self, accent: str) -> None:
        if self.compact:
            return
        self.canvas.create_polygon(
            17, 16, 332, 16, 344, 28, 344, 111, 332, 123, 17, 123, 5, 111, 5, 28,
            fill="#061018",
            outline=self._blend(accent, "#0a1720", 0.68),
            width=1,
        )
        self.canvas.create_line(22, 35, 64, 35, fill=accent, width=2)
        self.canvas.create_text(
            22, 48, anchor="nw", text=self.assistant_name.upper(), fill=accent,
            font=("Segoe UI Semibold", 9),
        )
        self.canvas.create_text(
            22, 70, anchor="nw", text=self.last_text, width=292, fill=self.TEXT,
            font=("Segoe UI", 10),
        )
        self.canvas.create_text(
            22, 104, anchor="sw", text=self.detail, width=292, fill=self.MUTED,
            font=("Segoe UI", 7),
        )

    def _draw_hologram(self, accent: str, label: str) -> None:
        c = self.canvas
        bob = math.sin(self.phase * 0.78) * 3.2
        sway = math.sin(self.phase * 0.41) * 2.4
        cx = 178 + sway
        base_y = 444 if not self.compact else 378
        head_y = base_y - 245 + bob
        shoulder_y = head_y + 83
        waist_y = shoulder_y + 91

        # projection cone and base
        for i in range(8):
            y = base_y - i * 4
            spread = 70 - i * 4
            col = self._blend(accent, self.TRANSPARENT, 0.66 + i * 0.03)
            c.create_line(cx - spread, y, cx + spread, y, fill=col, width=1)
        c.create_polygon(
            cx - 74, base_y - 10, cx + 74, base_y - 10, cx + 35, head_y + 48, cx - 35, head_y + 48,
            fill=self._blend(accent, self.TRANSPARENT, 0.90),
            outline="",
        )
        for rx, ry, mix in ((76, 18, .42), (56, 12, .25), (36, 7, .05)):
            col = self._blend(accent, "#ffffff", mix)
            self._glow_oval(cx-rx, base_y-ry, cx+rx, base_y+ry, col, layers=2)

        # floating telemetry particles
        for p in self.particles:
            p["y"] -= p["s"]
            p["x"] += math.sin(self.phase + p["p"]) * 0.22
            if p["y"] < head_y - 10:
                p["y"] = base_y - random.uniform(15, 80)
                p["x"] = random.uniform(cx - 78, cx + 78)
            alpha_col = self._blend(accent, self.TRANSPARENT, 0.45 + 0.25 * abs(math.sin(self.phase + p["p"])))
            c.create_oval(p["x"]-p["r"], p["y"]-p["r"], p["x"]+p["r"], p["y"]+p["r"], fill=alpha_col, outline="")

        # torso wireframe
        body = self._blend(accent, "#dfffff", 0.20)
        dim = self._blend(accent, self.TRANSPARENT, 0.55)
        c.create_polygon(
            cx-43, shoulder_y, cx-26, waist_y, cx, waist_y+18, cx+26, waist_y, cx+43, shoulder_y,
            cx+24, shoulder_y-18, cx-24, shoulder_y-18,
            fill=self._blend(accent, self.TRANSPARENT, 0.86),
            outline=body,
            width=2,
        )
        self._line(cx-24, shoulder_y-18, cx, waist_y+18, cx+24, shoulder_y-18, fill=dim, width=1)
        self._line(cx-43, shoulder_y, cx-72, shoulder_y+45, cx-61, waist_y+32, fill=body, width=3, smooth=True)
        self._line(cx+43, shoulder_y, cx+72, shoulder_y+45, cx+61, waist_y+32, fill=body, width=3, smooth=True)
        self._line(cx-25, waist_y+4, cx-33, base_y-42, fill=body, width=3)
        self._line(cx+25, waist_y+4, cx+33, base_y-42, fill=body, width=3)

        # shoulder and joint nodes
        for x, y, r in (
            (cx-43, shoulder_y, 4), (cx+43, shoulder_y, 4),
            (cx-72, shoulder_y+45, 3), (cx+72, shoulder_y+45, 3),
            (cx-25, waist_y+5, 4), (cx+25, waist_y+5, 4),
        ):
            c.create_oval(x-r, y-r, x+r, y+r, fill=self._blend(accent, "#ffffff", .35), outline="")

        # neck
        self._line(cx-12, head_y+66, cx-13, shoulder_y-18, fill=body, width=2)
        self._line(cx+12, head_y+66, cx+13, shoulder_y-18, fill=body, width=2)

        # head shell
        self._glow_oval(cx-38, head_y, cx+38, head_y+72, accent, layers=4)
        c.create_oval(
            cx-35, head_y+3, cx+35, head_y+69,
            fill=self._blend(accent, self.TRANSPARENT, 0.88),
            outline=body, width=2,
        )
        c.create_arc(cx-33, head_y+5, cx+33, head_y+65, start=20, extent=140, style=tk.ARC, outline=dim, width=1)
        c.create_arc(cx-33, head_y+5, cx+33, head_y+65, start=200, extent=120, style=tk.ARC, outline=dim, width=1)

        # face and blink
        now = time.time()
        if now >= self.next_blink and self.blink <= 0:
            self.blink = 1.0
            self.next_blink = now + random.uniform(2.5, 5.6)
        if self.blink > 0:
            eye_h = max(1.0, 4.5 * abs(0.5 - self.blink) * 2)
            self.blink -= 0.14
        else:
            eye_h = 4.5
        eye_col = self._blend(accent, "#ffffff", .58)
        for ex in (cx-15, cx+15):
            c.create_oval(ex-6, head_y+31-eye_h, ex+6, head_y+31+eye_h, fill=eye_col, outline="")
            c.create_oval(ex-2, head_y+29, ex+2, head_y+33, fill="#06202a", outline="")

        mouth_y = head_y + 52
        if self.state == "speaking":
            amp = 3 + 4 * abs(math.sin(self.phase * 4.0))
            c.create_arc(cx-12, mouth_y-amp, cx+12, mouth_y+amp, start=190, extent=160, style=tk.ARC, outline=eye_col, width=2)
        elif self.state == "listening":
            c.create_arc(cx-11, mouth_y-2, cx+11, mouth_y+7, start=200, extent=140, style=tk.ARC, outline=eye_col, width=2)
        else:
            self._line(cx-9, mouth_y, cx+9, mouth_y, fill=eye_col, width=1)

        # chest core
        core_y = shoulder_y + 38
        core_r = 12 + 2.5 * abs(math.sin(self.phase * (2.2 if self.state in {"speaking", "listening"} else 1.2)))
        self._glow_oval(cx-core_r, core_y-core_r, cx+core_r, core_y+core_r, accent, layers=5)
        c.create_oval(cx-5, core_y-5, cx+5, core_y+5, fill="#eaffff", outline="")

        # scanlines on the body area
        scan_offset = int((self.phase * 13) % 10)
        for y in range(int(head_y)+scan_offset, int(base_y)-18, 10):
            half = 43 if y < waist_y else 32
            c.create_line(cx-half, y, cx+half, y, fill=self._blend(accent, self.TRANSPARENT, .78), width=1)

        # floating state halo
        ring_y = head_y + 36
        c.create_arc(cx-58, ring_y-18, cx+58, ring_y+18, start=(self.phase*28)%360, extent=118, style=tk.ARC, outline=accent, width=2)
        c.create_arc(cx-58, ring_y-18, cx+58, ring_y+18, start=(self.phase*28+180)%360, extent=88, style=tk.ARC, outline=dim, width=1)

        # status tag
        tag_y = base_y + 25
        c.create_rectangle(cx-60, tag_y-12, cx+60, tag_y+12, fill="#061018", outline=dim, width=1)
        c.create_oval(cx-49, tag_y-3, cx-43, tag_y+3, fill=accent, outline="")
        c.create_text(cx-35, tag_y, anchor="w", text=label, fill=accent, font=("Segoe UI Semibold", 8))

    def _draw_footer(self, accent: str) -> None:
        if self.compact:
            return
        worker = "DESKTOP ✓" if self.worker_online else "DESKTOP —"
        voice = "VOICE ✓" if self.voice_online else "VOICE —"
        self.canvas.create_text(
            178, 474, text=f"{worker}   {voice}   CTRL+ALT+A: SUMMON",
            fill=self._blend(accent, self.MUTED, .56),
            font=("Consolas", 7),
        )

    def _draw_telemetry(self, accent: str) -> None:
        if self.compact:
            return
        # Small truthful runtime telemetry orbiting the hologram.
        items = [
            ("VOICE", "LIVE" if self.voice_online else "OFF"),
            ("AGENT", "LIVE" if self.worker_online else "OFF"),
            ("MODE", self.state.upper()[:9]),
        ]
        y = 150
        for title, value in items:
            x1, x2 = 14, 86
            self.canvas.create_rectangle(
                x1, y, x2, y+28,
                fill="#061018",
                outline=self._blend(accent, self.TRANSPARENT, .62),
                width=1,
            )
            self.canvas.create_text(x1+7, y+7, anchor="nw", text=title, fill=self.MUTED, font=("Consolas", 6))
            self.canvas.create_text(x1+7, y+17, anchor="nw", text=value, fill=accent, font=("Segoe UI Semibold", 7))
            y += 36

        # Animated signal rail on the opposite side.
        base_x = 321
        for i in range(7):
            amp = 4 + int(12 * abs(math.sin(self.phase * 1.7 + i * .72)))
            self.canvas.create_line(
                base_x - amp, 174 + i*14, base_x, 174 + i*14,
                fill=self._blend(accent, self.TRANSPARENT, .35 + i*.045), width=2,
            )

    def _draw(self) -> None:
        self.canvas.delete("all")
        self.assistant_name = self._assistant_name()
        accent, label = self._color()
        self._draw_panel(accent)
        self._draw_hologram(accent, label)
        self._draw_telemetry(accent)
        self._draw_footer(accent)

    def _tick(self) -> None:
        self._poll_global_hotkey()
        self.phase += 0.055 if self.state in {"idle", "offline"} else 0.09
        if self.worker and self.worker.poll() is not None:
            self.worker_online = False
        if self.voice and self.voice.poll() is not None:
            self.voice_online = False
        self._draw()
        self.root.after(33 if self.state in {"listening", "thinking", "speaking", "acting", "building"} else 48, self._tick)

    def close(self) -> None:
        self._save_position()
        self._stop_voice_runtime()
        self._stop_worker()
        try:
            self.aura.close()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ash holographic desktop companion")
    parser.add_argument("--pair", default="", help="Optional one-time Ash pairing code")
    parser.add_argument("--no-worker", action="store_true", help="Do not start the paired desktop worker")
    parser.add_argument("--no-voice", action="store_true", help="Do not start the always-on voice runtime")
    parser.add_argument("--compact", action="store_true", help="Start in compact hologram-only mode")
    parser.add_argument("--self-test", action="store_true", help="Validate packaged companion imports and exit")
    args = parser.parse_args()
    if args.self_test:
        assert "idle" in AshHologramCompanion.STATE
        assert callable(getattr(AshHologramCompanion, "_worker_command", None))
        assert callable(getattr(AshHologramCompanion, "_voice_command", None))
        return 0
    AshHologramCompanion(
        pair_code=args.pair,
        start_worker=not args.no_worker,
        start_voice=not args.no_voice,
        compact=args.compact,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
