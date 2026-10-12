from __future__ import annotations

import sys
import time
import traceback

from ash_agent import AshPythonAgent
from voice_runtime.events import emit
from voice_runtime.windows_speech import WindowsSystemSpeechListener, speak_windows
from companion_presence import presence_command, launch_command


class AshLiteVoiceRuntime:
    """Small Windows-native voice runtime for the compact installer."""

    def __init__(self) -> None:
        self.agent = AshPythonAgent()
        self.listener = WindowsSystemSpeechListener()
        self.recent_turns = []

    def run_text(self, command: str) -> str:
        emit("command", text=command)
        gesture = presence_command(command)
        if gesture:
            action, reply = gesture
            emit("narration", text=reply)
            speak_windows(reply)
            emit("companion", action=action)
            emit("done", text=reply)
            return reply
        try:
            launch = launch_command(command)
        except (OSError, RuntimeError) as exc:
            launch = f"I couldn't open that app: {exc}"
        if launch:
            emit("narration", text=launch)
            speak_windows(launch)
            emit("done", text=launch)
            return launch
        emit("thinking")
        spoken = {"done": False}

        def narrate(text: str) -> None:
            if not text:
                return
            emit("narration", text=text)
            if not spoken["done"]:
                spoken["done"] = True
                speak_windows(text)

        context = "\n".join(self.recent_turns[-6:])
        prompt = f"Recent conversation (context only):\n{context}\nCurrent request: {command}" if context else command
        reply = self.agent.think_stream(prompt, mode="high", on_narration=narrate)
        self.recent_turns.extend(["User: " + command[:2000], "Ash: " + reply[:4000]])
        self.recent_turns = self.recent_turns[-6:]
        emit("done", text=reply)
        if reply and not spoken["done"]:
            emit("narration", text=reply)
            speak_windows(reply)
            emit("done", text=reply)
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
