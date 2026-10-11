# Ash autonomous tasks and intelligence adapters

## Current scope

Ash Desktop supports local recurring **read-oriented** tasks while its paired desktop worker is running. The cloud app has its separate existing Supabase-based automations. Neither is a background task when the worker is shut down; a completed build alone does not prove the desktop is connected.

Local schedules require explicit creation/approval. Execution leases reduce duplicate runs after polling. A scheduled task that requests a confirmation-required action is paused for review rather than executed automatically. Results and errors are recorded in a local JSONL history.

## Manage offline tasks

Start the paired Ash desktop worker using the project's normal setup. From the repository root, use:

```powershell
python desktop_worker/automation_cli.py create --name "Daily status" --prompt "Summarize my local development workspace status; do not change files." --every-minutes 1440
python desktop_worker/automation_cli.py list
python desktop_worker/automation_cli.py history --limit 10
python desktop_worker/automation_cli.py pause TASK_ID
python desktop_worker/automation_cli.py resume TASK_ID
python desktop_worker/automation_cli.py cancel TASK_ID
```

A local running worker checks due jobs. Pause and resume are explicit. The create command does **not** execute the prompt immediately. A provider-backed research task still depends on configured and functioning model services, while local deterministic tasks have narrower capabilities.

## Current intelligence integration status

- Wazuh: read-only inventory adapter can authenticate to an explicitly configured manager via `ASH_WAZUH_URL`, `ASH_WAZUH_USER`, `ASH_WAZUH_PASSWORD`. Use local environment configuration; do not store credentials in frontend files. An actual manager session has not been tested in CI.
- SpiderFoot: reads an existing authorized JSON export within Ash's configured workspace through the agent tool.
- Strix: likewise imports an existing report; it does not launch scans.
- God's Eye View and ShadowBroker: external projects listed in Ash Intelligence; **not hosted or embedded** and no live feeds inside Ash.
- OpenJarvis: existing optional local specialist. Its CodeAct actions still need explicit permission.
- Superpowers: Ash coding guidance inspired by test-first workflows; not an installed standalone Superpowers runtime.

Run local tests:

```powershell
pip install -r desktop_worker/requirements.txt
$env:PYTHONPATH = "desktop_worker"
python -m unittest discover -s desktop_worker -p "test_*.py"
npm install
npm run build
```

## Acceptance requirements before broad release

A successful GitHub unit pipeline is not a user-device proof. Verify Windows setup and pairing, voice/microphone hardware, real provider fallback, repeated schedules across restarts, task cancellation, true live Wazuh data, and the end-to-end release gate. Do not advertise automated security scans, real private camera feeds or guaranteed task outcomes until implemented and independently checked.
