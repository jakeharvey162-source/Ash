"""Local-first Ash task management. The paired worker executes enabled schedules.

This CLI edits only local JSON schedule metadata. It NEVER executes prompts,
runs shell commands, sends messages or changes external accounts by itself.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from local_scheduler import LocalScheduler

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=None,
                        help="Optional local Ash schedule directory (default: ~/.ash)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Show scheduled tasks and their next run times")
    create = sub.add_parser("create", help="Create a recurring task, enabled after explicit CLI action")
    create.add_argument("--name", required=True)
    create.add_argument("--prompt", required=True)
    create.add_argument("--every-minutes", type=int, required=True)
    for action in ("pause", "resume", "cancel"):
        command = sub.add_parser(action)
        command.add_argument("task_id")
    hist = sub.add_parser("history")
    hist.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    scheduler = LocalScheduler(args.home)
    try:
        if args.command == "list":
            data = {"tasks": scheduler.list()}
        elif args.command == "create":
            data = {"created": scheduler.create(args.name, args.prompt, args.every_minutes)}
        elif args.command == "pause":
            data = {"paused": scheduler.pause(args.task_id)}
        elif args.command == "resume":
            data = {"resumed": scheduler.resume(args.task_id)}
        elif args.command == "cancel":
            data = {"cancelled": scheduler.cancel(args.task_id)}
        else:
            if not 1 <= args.limit <= 100:
                parser.error("History limit must be between 1 and 100.")
            try:
                lines = scheduler.results_path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                lines = []
            data = {"runs": [json.loads(line) for line in lines[-args.limit:] if line.strip()]}
        print(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, "Ash task management failed: " + type(exc).__name__ + "\n")

if __name__ == "__main__":
    raise SystemExit(main())
