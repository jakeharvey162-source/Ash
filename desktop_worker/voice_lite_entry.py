import json
import sys

if "--self-test" in sys.argv:
    from voice_runtime.wake import WakeMatcher
    from voice_runtime.windows_speech import WindowsSystemSpeechListener
    matcher = WakeMatcher("Ash")
    assert matcher.extract("Hey Ash, status") == "status"
    assert isinstance(WindowsSystemSpeechListener.supported(), bool)
    print(json.dumps({
        "ok": True,
        "component": "voice-lite",
        "listener": WindowsSystemSpeechListener.__name__,
    }))
    raise SystemExit(0)

from voice_runtime.lite_runtime import main

if __name__ == "__main__":
    raise SystemExit(main())
