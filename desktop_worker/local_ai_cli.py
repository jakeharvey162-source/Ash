from __future__ import annotations

import argparse
import json
import sys

from offline_brain import AshOfflineBrain


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ash entirely on this computer.")
    parser.add_argument("prompt", nargs="*", help="Prompt for Ash. Leave empty for interactive mode.")
    parser.add_argument("--status", action="store_true", help="Show the local AI backend status.")
    parser.add_argument("--mode", choices=["instant", "medium", "high"], default="high")
    args = parser.parse_args()

    brain = AshOfflineBrain()
    if args.status:
        print(json.dumps(brain.status().__dict__, indent=2))
        if not args.prompt:
            return 0

    if args.prompt:
        print(brain.respond(" ".join(args.prompt), mode=args.mode))
        return 0

    print("Ash Offline. Type /status, /exit, or a message.")
    history: list[dict[str, str]] = []
    while True:
        try:
            prompt = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        if prompt.lower() in {"/exit", "/quit"}:
            return 0
        if prompt.lower() == "/status":
            print(json.dumps(brain.status().__dict__, indent=2))
            continue
        answer = brain.respond(prompt, mode=args.mode, history=history)
        print("Ash >", answer)
        history.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])
        history = history[-16:]


if __name__ == "__main__":
    raise SystemExit(main())
