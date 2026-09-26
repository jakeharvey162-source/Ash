from __future__ import annotations

import base64
import io
import os
import time
import platform
import subprocess
import webbrowser
import shutil
from dataclasses import dataclass
from typing import Any


class ComputerControlUnavailable(RuntimeError):
    pass


@dataclass
class ScreenFrame:
    jpeg_base64: str
    width: int
    height: int


class AshComputerController:
    """Permissioned screenshot -> plan -> act loop for the user's own desktop."""

    def __init__(self, agent) -> None:
        self.agent = agent
        self.enabled = os.environ.get("ASH_COMPUTER_CONTROL", "").strip().lower() in {"1", "true", "yes", "on"}
        if not self.enabled:
            raise ComputerControlUnavailable(
                "Computer control is disabled on this desktop. Set ASH_COMPUTER_CONTROL=1 after reviewing the permissions."
            )
        try:
            import pyautogui  # type: ignore
            import mss  # type: ignore
            from PIL import Image  # type: ignore
        except Exception as exc:
            raise ComputerControlUnavailable(
                "Computer-control dependencies are missing. Install desktop_worker/requirements-control.optional.txt."
            ) from exc
        self.pyautogui = pyautogui
        self.mss = mss
        self.Image = Image
        self.pyautogui.FAILSAFE = True
        self.pyautogui.PAUSE = 0.12

    def capture(self) -> ScreenFrame:
        with self.mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(monitor)
            width, height = int(shot.width), int(shot.height)
            image = self.Image.frombytes("RGB", shot.size, shot.rgb)
            max_width = 1280
            if image.width > max_width:
                ratio = max_width / image.width
                image = image.resize((max_width, max(1, int(image.height * ratio))))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=72, optimize=True)
            return ScreenFrame(
                jpeg_base64=base64.b64encode(out.getvalue()).decode("ascii"),
                width=width,
                height=height,
            )

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _point(self, action: dict[str, Any]) -> tuple[int, int]:
        screen = self.pyautogui.size()
        x = max(0, min(int(screen.width) - 1, int(self._number(action.get("x"), 0))))
        y = max(0, min(int(screen.height) - 1, int(self._number(action.get("y"), 0))))
        return x, y

    def _launch_app(self, raw_name: str) -> dict[str, Any]:
        name = str(raw_name or "").strip().lower()
        aliases = {
            "browser": "browser", "chrome": "chrome", "google chrome": "chrome",
            "edge": "edge", "microsoft edge": "edge", "firefox": "firefox",
            "notepad": "notepad", "text editor": "notepad", "calculator": "calculator",
            "calc": "calculator", "file explorer": "files", "explorer": "files", "files": "files",
            "terminal": "terminal", "command prompt": "terminal", "powershell": "terminal",
            "vscode": "vscode", "visual studio code": "vscode"
        }
        app = aliases.get(name)
        if not app:
            raise ValueError("App is not in Ash's safe launch allowlist.")
        system = platform.system().lower()
        if app == "browser":
            webbrowser.open("about:blank")
            return {"type": "launch_app", "app": app}
        candidates = {
            "windows": {
                "chrome": ["chrome.exe"], "edge": ["msedge.exe"], "firefox": ["firefox.exe"],
                "notepad": ["notepad.exe"], "calculator": ["calc.exe"], "files": ["explorer.exe"],
                "terminal": ["powershell.exe"], "vscode": ["code.cmd", "code.exe"],
            },
            "darwin": {
                "chrome": ["open", "-a", "Google Chrome"], "edge": ["open", "-a", "Microsoft Edge"],
                "firefox": ["open", "-a", "Firefox"], "notepad": ["open", "-a", "TextEdit"],
                "calculator": ["open", "-a", "Calculator"], "files": ["open", "."],
                "terminal": ["open", "-a", "Terminal"], "vscode": ["open", "-a", "Visual Studio Code"],
            },
            "linux": {
                "chrome": ["google-chrome"], "edge": ["microsoft-edge"], "firefox": ["firefox"],
                "notepad": ["gedit"], "calculator": ["gnome-calculator"], "files": ["xdg-open", "."],
                "terminal": ["x-terminal-emulator"], "vscode": ["code"],
            },
        }
        cmd = candidates.get(system, {}).get(app)
        if not cmd:
            raise ComputerControlUnavailable("Ash does not know how to launch that app on this operating system.")
        executable = cmd[0]
        if system == "linux" and executable not in {"xdg-open"} and shutil.which(executable) is None:
            raise ComputerControlUnavailable("The requested app is not installed or not on PATH.")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"type": "launch_app", "app": app}

    @staticmethod
    def _open_url(raw_url: str) -> dict[str, Any]:
        url = str(raw_url or "").strip()
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("Ash only opens http(s) URLs.")
        if len(url) > 2048:
            raise ValueError("URL is too long.")
        webbrowser.open(url)
        return {"type": "open_url", "url": url[:240]}

    def execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        kind = str(action.get("type") or "").strip().lower()
        if kind == "launch_app":
            return self._launch_app(str(action.get("app") or action.get("name") or ""))
        if kind == "open_url":
            return self._open_url(str(action.get("url") or ""))
        if kind == "move":
            x, y = self._point(action)
            self.pyautogui.moveTo(x, y, duration=0.18)
            return {"type": kind, "x": x, "y": y}
        if kind == "click":
            x, y = self._point(action)
            self.pyautogui.click(x, y)
            return {"type": kind, "x": x, "y": y}
        if kind == "double_click":
            x, y = self._point(action)
            self.pyautogui.doubleClick(x, y, interval=0.12)
            return {"type": kind, "x": x, "y": y}
        if kind == "type_text":
            text = str(action.get("text") or "")
            if len(text) > 1800:
                raise ValueError("Refusing to type more than 1800 characters in one action.")
            lowered = text.lower()
            sensitive_markers = ["password=", "otp=", "one-time password", "recovery code", "private key", "seed phrase"]
            if any(marker in lowered for marker in sensitive_markers):
                raise ValueError("Sensitive authentication text must be entered manually by the user.")
            self.pyautogui.write(text, interval=0.015)
            return {"type": kind, "chars": len(text)}
        if kind == "press":
            key = str(action.get("key") or "").strip().lower()
            if not key or len(key) > 24:
                raise ValueError("Invalid key.")
            self.pyautogui.press(key)
            return {"type": kind, "key": key}
        if kind == "hotkey":
            keys = [str(x).strip().lower() for x in (action.get("keys") or []) if str(x).strip()][:4]
            if not keys:
                raise ValueError("Hotkey contained no keys.")
            blocked = {("ctrl", "alt", "delete")}
            if tuple(keys) in blocked:
                raise ValueError("Protected system hotkey must be performed manually.")
            self.pyautogui.hotkey(*keys)
            return {"type": kind, "keys": keys}
        if kind == "scroll":
            amount = max(-12, min(12, int(self._number(action.get("amount"), 0))))
            self.pyautogui.scroll(amount)
            return {"type": kind, "amount": amount}
        if kind == "wait":
            seconds = max(0.1, min(5.0, self._number(action.get("seconds"), 0.7)))
            time.sleep(seconds)
            return {"type": kind, "seconds": seconds}
        raise ValueError("Unsupported computer action: " + kind)

    @staticmethod
    def risk_reason(goal: str) -> str:
        text = " " + str(goal or "").lower() + " "
        categories = [
            ("payment or purchase", [" payment ", " purchase ", " checkout ", " banking "]),
            ("credential or account-security change", [" password ", " otp ", " recovery code ", " two-factor "]),
            ("permanent or bulk deletion", [" permanently ", " delete all ", " wipe "]),
            ("administrator or permission change", [" administrator ", " permissions ", " privilege "]),
        ]
        for reason, markers in categories:
            if any(marker in text for marker in markers):
                return reason
        return ""

    def run_goal(self, goal: str, max_steps: int = 12) -> dict[str, Any]:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("Computer-control goal is empty.")
        risk = self.risk_reason(goal)
        if risk:
            return {
                "ok": False,
                "summary": "Ash stopped before controlling the computer because this goal includes a sensitive " + risk + " step. Complete that step manually.",
                "steps": 0,
                "trace": [],
                "manual_required": True,
            }

        trace: list[dict[str, Any]] = []
        for step in range(max(1, min(max_steps, 16))):
            frame = self.capture()
            plan = self.agent.plan_computer(
                goal,
                frame.jpeg_base64,
                frame.width,
                frame.height,
            )
            summary = str(plan.get("summary") or "")
            actions = list(plan.get("actions") or [])[:4]
            trace.append({"step": step + 1, "summary": summary, "actions": actions})
            if plan.get("done") is True:
                return {
                    "ok": True,
                    "summary": summary or "Computer task completed and visually verified.",
                    "steps": step + 1,
                    "trace": trace,
                }
            if not actions:
                return {
                    "ok": False,
                    "summary": summary or "Ash could not find a safe next computer action.",
                    "steps": step + 1,
                    "trace": trace,
                }
            for action in actions:
                self.execute_action(action)
            time.sleep(0.55)

        return {
            "ok": False,
            "summary": "Ash reached the computer-control step limit before it could visually verify completion.",
            "steps": max_steps,
            "trace": trace,
        }
