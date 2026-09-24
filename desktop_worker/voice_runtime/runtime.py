from __future__ import annotations

import sys
import time
import traceback
from ash_agent import AshPythonAgent
from voice_runtime.events import emit
from voice_runtime.listener import LocalWhisperListener

class AshVoiceRuntime:
    def __init__(self) -> None:
        self.agent = AshPythonAgent()
        self.listener = LocalWhisperListener()

    def run_text(self, command: str) -> str:
        emit("command", text=command)
        emit("thinking")
        reply = self.agent.think_stream(
            command, mode="high",
            on_narration=lambda text: emit("narration", text=text),
        )
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
