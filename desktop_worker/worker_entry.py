import json
import sys

if "--self-test" in sys.argv:
    from ash_agent import AshPythonAgent
    agent = AshPythonAgent()
    print(json.dumps({
        "ok": True,
        "component": "worker",
        "offline": agent.offline.status().__dict__,
        "openjarvis": agent.openjarvis.status(),
    }))
    raise SystemExit(0)

from remote_worker import main

if __name__ == "__main__":
    raise SystemExit(main())
