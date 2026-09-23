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
