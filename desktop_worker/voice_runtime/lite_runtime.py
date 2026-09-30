from __future__ import annotations

import sys
import time
import traceback

from ash_agent import AshPythonAgent
from voice_runtime.events import emit
from voice_runtime.windows_speech import WindowsSystemSpeechListener, speak_windows


class AshLiteVoiceRuntime:
    """Small Windows-native voice runtime for the compact installer."""

    def __init__(self) -> None:
        self.agent = AshPythonAgent()
        self.listener = WindowsSystemSpeechListener()

    def run_text(self, command: str) -> str:
        emit("command", text=command)
        emit("thinking")
        spoken = {"done": False}

        def narrate(text: str) -> None:
            if not text:
                return
            emit("narration", text=text)
            if not spoken["done"]:
                spoken["done"] = True
                speak_windows(text)

        reply = self.agent.think_stream(command, mode="high", on_narration=narrate)
        emit("done", text=reply)
        if reply and not spoken["done"]:
            speak_windows(reply)
        return reply

    def run_forever(self) -> None:
        emit(
            "boot",
            wake_word=self.listener.wake.wake_word,
            cloud=bool(self.agent.gateway_url and self.agent.access_token),
            local_model=self.agent.ollama_model,
            offline_brain=self.agent.offline.status().__dict__,
            voice_backend="windows_system_speech",
        )
        emit("warming_up")
        self.listener.preload()
        emit("ready")
        try:
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
        finally:
            self.listener.close()


def main() -> int:
    runtime = AshLiteVoiceRuntime()
    if len(sys.argv) > 1:
        runtime.run_text(" ".join(sys.argv[1:]))
        return 0
    runtime.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
