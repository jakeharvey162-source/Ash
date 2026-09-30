from __future__ import annotations

import base64
import os
import platform
import subprocess
import threading
from .wake import WakeMatcher


class WindowsSystemSpeechListener:
    """Lightweight Windows wake-word listener using the OS speech stack.

    This avoids bundling Whisper/CTranslate2 into the default installer.
    Recognition quality depends on the Windows speech language pack.
    """

    def __init__(self) -> None:
        self.wake = WakeMatcher()
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    @staticmethod
    def supported() -> bool:
        return platform.system().lower() == "windows"

    @staticmethod
    def _encoded_command(script: str) -> list[str]:
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        return [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded,
        ]

    def preload(self) -> None:
        if not self.supported():
            raise RuntimeError("Windows lightweight voice is only available on Windows.")
        # Check System.Speech without touching the microphone.
        script = (
            "try { Add-Type -AssemblyName System.Speech; "
            "[Console]::Out.WriteLine('ok') } catch { exit 2 }"
        )
        completed = subprocess.run(
            self._encoded_command(script),
            capture_output=True,
            text=True,
            timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0 or "ok" not in completed.stdout.lower():
            raise RuntimeError(
                "Windows speech components are unavailable. Install a Windows speech language pack "
                "or use the optional Ash offline voice pack."
            )

    def _ensure_process(self) -> subprocess.Popen[str]:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return self._proc
            culture = os.environ.get("ASH_WINDOWS_SPEECH_CULTURE", "").strip()
            culture_line = ""
            if culture:
                safe = culture.replace("'", "''")[:32]
                culture_line = (
                    "$culture=[System.Globalization.CultureInfo]::GetCultureInfo('" + safe + "');"
                    "$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture);"
                )
            else:
                culture_line = "$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine;"
            script = (
                "$ErrorActionPreference='Stop';"
                "Add-Type -AssemblyName System.Speech;"
                + culture_line +
                "$g=New-Object System.Speech.Recognition.DictationGrammar;"
                "$r.LoadGrammar($g);"
                "$r.SetInputToDefaultAudioDevice();"
                "while($true){"
                "try{$x=$r.Recognize();if($null -ne $x -and $x.Text){"
                "$t=$x.Text.Replace([Environment]::NewLine,' ').Trim();"
                "if($t){[Console]::Out.WriteLine($t);[Console]::Out.Flush()}"
                "}}catch{Start-Sleep -Milliseconds 350}"
                "}"
            )
            self._proc = subprocess.Popen(
                self._encoded_command(script),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return self._proc

    def listen_for_command(self, on_wake=None, on_heard=None) -> str:
        proc = self._ensure_process()
        if not proc.stdout:
            raise RuntimeError("Windows speech listener did not expose audio results.")
        pending_wake = False
        while True:
            line = proc.stdout.readline()
            if line == "" and proc.poll() is not None:
                raise RuntimeError("Windows speech recognition stopped unexpectedly.")
            text = str(line or "").strip()
            if not text:
                continue
            if on_heard:
                on_heard(text)
            if pending_wake:
                return text
            match = self.wake.find(text)
            if not match:
                continue
            if on_wake:
                on_wake()
            command = self.wake.command_after(text, match)
            if command:
                return command
            pending_wake = True

    def close(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def speak_windows(text: str) -> None:
    if platform.system().lower() != "windows":
        return
    clean = str(text or "").strip()
    if not clean:
        return
    # Pass user/model text as base64 data rather than interpolating it into code.
    payload = base64.b64encode(clean.encode("utf-8")).decode("ascii")
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$bytes=[Convert]::FromBase64String('" + payload + "');"
        "$text=[Text.Encoding]::UTF8.GetString($bytes);"
        "$s.Rate=1;"
        "$s.Speak($text);"
        "$s.Dispose();"
    )
    try:
        subprocess.run(
            WindowsSystemSpeechListener._encoded_command(script),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=max(15, min(120, len(clean) // 12 + 15)),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass
