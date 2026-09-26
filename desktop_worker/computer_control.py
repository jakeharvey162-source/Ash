from __future__ import annotations

import base64
import io
import os
import time
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

    def execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        kind = str(action.get("type") or "").strip().lower()
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

    def run_goal(self, goal: str, max_steps: int = 12) -> dict[str, Any]:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("Computer-control goal is empty.")

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
