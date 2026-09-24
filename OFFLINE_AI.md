# Ash Offline Python Brain

Ash now has a local fallback that can run without any cloud AI API.

## Runtime order

1. Ash cloud gateway, when configured.
2. Optional Claude Code desktop backend.
3. Local Ollama model, when running.
4. Ash Offline Python Brain.
   - Direct in-process GGUF inference through llama-cpp-python when a model is installed.
   - Local SQLite memory.
   - Deterministic utilities and safe fallback even if no model is installed.

## Full offline generative mode

Install the optional dependency:

```
pip install -r desktop_worker/requirements-local.optional.txt
```

Put a compatible `.gguf` model in:

```
%USERPROFILE%\.ash\models
```

or set:

```
ASH_GGUF_MODEL=C:\path\to\your-model.gguf
```

Ash discovers Qwen, Gemma, Llama and Phi GGUF files automatically. No API key is required and prompts remain on the computer.

For a smaller machine, prefer a small quantized GGUF model. For stronger coding on a machine with enough RAM, the existing Ollama route can use Qwen coding models.

## Test

Windows:

```
desktop_worker\run_offline.bat
```

Any platform:

```
PYTHONPATH=desktop_worker python desktop_worker/local_ai_cli.py --status
PYTHONPATH=desktop_worker python desktop_worker/local_ai_cli.py "Explain dependency injection simply"
```

The desktop worker advertises `offline_brain: true` to the Ash UI so the command center can show local execution readiness.
