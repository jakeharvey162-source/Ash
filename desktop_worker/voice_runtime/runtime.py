from __future__ import annotations

import sys
import time
import traceback
from ash_agent import AshPythonAgent
from voice_runtime.events import emit
from voice_runtime.listener import LocalWhisperListener
from companion_presence import presence_command, launch_command

class AshVoiceRuntime:
    def __init__(self) -> None:
        self.agent = AshPythonAgent()
        self.listener = LocalWhisperListener()
        self.recent_turns = []

    def run_text(self, command: str) -> str:
        emit("command", text=command)
        gesture = presence_command(command)
        if gesture:
            action, reply = gesture
            emit("narration", text=reply)
            emit("companion", action=action)
            emit("done", text=reply)
            return reply
        try:
            launch = launch_command(command)
        except (OSError, RuntimeError) as exc:
            launch = f"I couldn't open that app: {exc}"
        if launch:
            emit("narration", text=launch)
            emit("done", text=launch)
            return launch
        emit("thinking")
        context = "\n".join(self.recent_turns[-6:])
        prompt = f"Recent conversation (context only):\n{context}\nCurrent request: {command}" if context else command
        reply = self.agent.think_stream(
            prompt, mode="high",
            on_narration=lambda text: emit("narration", text=text),
        )
        self.recent_turns.extend(["User: " + command[:2000], "Ash: " + reply[:4000]])
        self.recent_turns = self.recent_turns[-6:]
        emit("done", text=reply)
        return reply

    def run_forever(self) -> None:
        emit(
            "boot",
            wake_word=self.listener.wake.wake_word,
            cloud=bool(self.agent.gateway_url and self.agent.access_token),
            claude_cli=self.agent.claude_cli_enabled,
            local_model=self.agent.ollama_model,
            offline_brain=self.agent.offline.status().__dict__,
        )
        emit("warming_up")
        self.listener.preload()
        emit("ready")
        while True:
            emit("listening")
            try:
                command = self.listener.listen_for_command(
                    on_wake=lambda: emit("wake"),
                    on_heard=lambda text: emit("heard", text=text),
                )
                self.run_text(command)
            except KeyboardInterrupt:
                emit("shutdown")
                return
            except Exception as exc:
                emit("runtime_error", message=str(exc))
                traceback.print_exc()
                time.sleep(1)

def main() -> int:
    runtime = AshVoiceRuntime()
    if len(sys.argv) > 1:
        runtime.run_text(" ".join(sys.argv[1:]))
        return 0
    runtime.run_forever()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
