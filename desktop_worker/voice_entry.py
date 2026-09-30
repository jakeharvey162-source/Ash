import json
import sys

if "--self-test" in sys.argv:
    from voice_runtime.listener import LocalWhisperListener
    from voice_runtime.wake import WakeMatcher
    matcher = WakeMatcher("Ash")
    assert matcher.extract("Hey Ash, status") == "status"
    print(json.dumps({
        "ok": True,
        "component": "voice",
        "listener": LocalWhisperListener.__name__,
    }))
    raise SystemExit(0)

from voice_runtime.runtime import main

if __name__ == "__main__":
    raise SystemExit(main())
