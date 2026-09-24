from __future__ import annotations

import glob
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable

SYSTEM_PROMPT = """You are Ash, the user's private desktop AI assistant.
Respond naturally and truthfully. Never claim an external action succeeded
without evidence. Consequential actions require Ash's confirmation layer.
Do not use shell, screen-control, messaging, purchase, install, delete,
submit, or other tools unless the user explicitly enabled those tools.
Keep spoken narration short and useful.
"""

class ClaudeCodeBackend:
    """Optional local Claude Code backend using the user's own CLI login."""

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._bin: str | None = None
        self.model = os.environ.get("ASH_CLAUDE_MODEL", "").strip()
        self.timeout_s = int(os.environ.get("ASH_CLAUDE_TIMEOUT_S", "180"))
        self.cwd = pathlib.Path(os.environ.get("ASH_CLAUDE_WORKDIR", str(pathlib.Path.home()))).expanduser()

    def _find_bin(self) -> str:
        if self._bin:
            return self._bin
        configured = os.environ.get("ASH_CLAUDE_BIN", "").strip()
        if configured:
            self._bin = configured
            return configured
        on_path = shutil.which("claude")
        if on_path:
            self._bin = on_path
            return on_path
        home = pathlib.Path.home()
        candidates = []
        candidates += glob.glob(str(home / "Library/Application Support/Claude/claude-code/*/claude.app/Contents/MacOS/claude"))
        candidates += glob.glob(str(home / ".local/bin/claude"))
        candidates += glob.glob(str(home / "AppData/Local/Programs/Claude*/**/claude.exe"), recursive=True)
        if candidates:
            self._bin = sorted(candidates)[-1]
            return self._bin
        raise RuntimeError("Claude Code CLI was not found.")

    @staticmethod
    def _text_blocks(message: dict):
        for block in message.get("content", []) or []:
            if block.get("type") == "text":
                text = str(block.get("text") or "").strip()
                if text:
                    yield text

    def process(self, prompt: str, on_narration: Callable[[str], None] | None = None) -> str:
        args = [
            self._find_bin(), "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--append-system-prompt", SYSTEM_PROMPT,
        ]
        tools_enabled = os.environ.get("ASH_CLAUDE_TOOLS_ENABLED", "0").strip().lower() in {"1","true","yes","on"}
        allowed_tools = os.environ.get("ASH_CLAUDE_ALLOWED_TOOLS", "").strip()
        if tools_enabled and allowed_tools:
            args += ["--allowedTools", allowed_tools]
        if self.model:
            args += ["--model", self.model]
        if self._session_id is None:
            self._session_id = str(uuid.uuid4())
            args += ["--session-id", self._session_id]
        else:
            args += ["--resume", self._session_id]

        last_spoken = ""
        final_text = ""
        with tempfile.TemporaryFile(mode="w+") as stderr_file:
            proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=stderr_file,
                text=True, cwd=str(self.cwd), shell=False
            )
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "assistant":
                        for text in self._text_blocks(event.get("message") or {}):
                            if text != last_spoken:
                                last_spoken = text
                                if on_narration:
                                    on_narration(text)
                    elif event.get("type") == "result":
                        final_text = str(event.get("result") or "").strip()
                proc.stdout.close()
                proc.wait(timeout=self.timeout_s)
            except subprocess.TimeoutExpired as exc:
                proc.kill()
                raise RuntimeError("Claude Code CLI timed out.") from exc

            if proc.returncode != 0:
                stderr_file.seek(0)
                stderr = stderr_file.read().strip()
                hint = " Run 'claude' in a terminal and log in first." if "login" in stderr.lower() else ""
                raise RuntimeError(f"Claude Code CLI exited with an error.{hint} {stderr[-500:]}".strip())

        if final_text and final_text != last_spoken and on_narration:
            on_narration(final_text)
        return final_text or last_spoken or "Done."
