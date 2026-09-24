# Ash Python Specialist

This worker gives desktop Ash a Python orchestration layer for software-building jobs.

It can:
- use the authenticated Ash cloud gateway
- optionally fall back to a local Ollama-compatible runtime
- plan a full-stack application
- generate files only inside an approved workspace
- run a limited allowlist of local build/test commands
- report command exit codes instead of pretending a build succeeded

It does **not** train a new foundation model. It adds an independent specialist/executor layer around Ash's model routes.

## Environment

```
ASH_SUPABASE_URL=
ASH_SUPABASE_PUBLISHABLE_KEY=
ASH_GATEWAY_URL=
ASH_ACCESS_TOKEN=
ASH_OLLAMA_URL=http://127.0.0.1:11434
ASH_OLLAMA_MODEL=qwen3-coder
```

Ollama is optional. The public Ash product should not require users to manually install it; a future packaged desktop runtime can manage a local model automatically.


## Optional local voice runtime

Ash now includes a desktop-only local voice runtime adapted from the MIT-licensed `ronitparikh/jarvis` architecture.

It adds:
- local always-on microphone capture
- adaptive room-noise calibration
- local faster-whisper transcription
- configurable "Ash" wake word and aliases
- NDJSON lifecycle events for the desktop HUD
- optional Claude Code CLI routing through the user's own local login
- cloud Ash gateway remains first; Claude Code and the local model are fallbacks
- Claude Code tool access is disabled by default

Text-only runtime test:

```bash
cd desktop_worker
ASH_CLAUDE_CLI_ENABLED=1 python -m voice_runtime.runtime "Explain this project"
```

Always-on local voice:

```bash
pip install -r desktop_worker/requirements-voice.optional.txt
cd desktop_worker
python -m voice_runtime.runtime
```

Optional configuration:

```
ASH_WAKE_WORD=Ash
ASH_WAKE_ALIASES=hey ash,okay ash,ok ash
ASH_WHISPER_MODEL=small.en
ASH_CLAUDE_CLI_ENABLED=0
ASH_CLAUDE_BIN=
ASH_CLAUDE_MODEL=
ASH_CLAUDE_TOOLS_ENABLED=0
ASH_CLAUDE_ALLOWED_TOOLS=
```

The Vercel frontend does not install the heavier microphone/Whisper dependencies.
See `desktop_worker/THIRD_PARTY_NOTICES.md` for attribution.
