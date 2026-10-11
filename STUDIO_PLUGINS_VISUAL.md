# Ash Studio — premium UI, public plugins, and visual planning

Updated 2026-10-11. This document describes **implemented source code**, not proof that external services are installed on a user's computer.

## Premium Builder (implemented)

Web Builder now sends a `design_preset` in its authenticated desktop build job. The paired desktop worker selects one of four vetted original art directions:

| Preset | Intended look |
| --- | --- |
| `editorial-luxe` | Editorial, asymmetrical, luxury typography |
| `midnight-studio` | Dark modern product studio with restrained accents |
| `warm-commerce` | Warm photographic commerce and storefronts |
| `clean-enterprise` | Accessible professional SaaS and dashboards |

The instruction enters the actual `AshRemoteWorker._builder_prompt`, which then calls the existing full-stack build/repair pipeline. The verified fallback site generator also applies preset-specific CSS tokens so the experience doesn't collapse into a single hardcoded appearance when cloud generation degrades. Each preset enforces responsiveness, focus states, realistic copy, form behavior, accessible motion, and real build verification.

Design references:
- [shadcn/ui](https://github.com/shadcn-ui/ui) — MIT components and distribution registry.
- [Magic UI](https://github.com/magicuidesign/magicui) — MIT animated UI components.
- [Magic UI MCP](https://github.com/magicuidesign/mcp) — discover/install components via an AI editor, **not installed in Ash**.
- [Motion](https://github.com/motiondivision/motion) — MIT animation library.
- [Aceternity UI](https://ui.aceternity.com/licence) — separate product/component license; do not redistribute paid source.

**No upstream UI source code is copied, and no library import is fabricated.** Installing dependencies or components into a user project remains a separate reviewed builder action, followed by a build.

## Actual public data plugins (implemented locally)

The **read-only**, fixed-host `desktop_worker/trusted_sources.py` provides:
- `plugins.catalog`: names, permissions, and real status of approved public sources.
- `plugins.github.repository`: public GitHub repository metadata for an exact allowlisted project ID (e.g., `gods-eye-view`, `strix`, `wazuh`, `magicui`).
- `world.usgs.earthquakes`: real USGS public M2.5+ earthquake reports from the daily GeoJSON feed.

Every request uses a predefined HTTPS endpoint, GET only, an 8-second timeout, bounded JSON size, and no user account secrets. Redirects are refused. AI prompts cannot supply arbitrary URLs, install programs, or make external changes.

The Ash **Intelligence** web page includes an on-demand *public* USGS feed with clear status and graceful failure, without treating it as emergency-response data. This is a small working public mapping source, **not God's Eye View itself**.

Existing local Ash support:
- Wazuh: explicit configured authenticated read-only agent inventory, not independently connected to a real user manager.
- SpiderFoot / Strix: summarize an authorized JSON export from Ash's own workspace; no auto-scanning.
- God's Eye View and ShadowBroker: catalog and setup references; neither engine is embedded or running by default.

## Visual / Visio-style features (implemented locally)

`visual.diagram` produces validated Mermaid **source** for a directed flowchart of up to 18 labeled nodes and 30 connections. It is available to the bounded Ash agent. Its output declares `rendered:false` until a compatible viewer processes the graph. It is not a Microsoft Visio integration or a native `.vsdx` generator.

## Platform plugin expansion (still pending)

Ash already contains some named OAuth and native-device connectors. A completely arbitrary marketplace of third-party agent tools is not enabled, because unrestricted MCP stdio launch gives plugins process-level access. The official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) is a possible future extension only with trusted server allowlists, user-granted scopes, process sandboxing, OAuth session boundaries and approval/audit logs. Use a current supported SDK release; consult its recent security advisories.

## Legitimate academic help

`desktop_worker/skills/assessment_practice.md` adds SAM/Cengage assignment-instruction understanding, rubric feedback, error spotting, student practice and safe local file review. It does **not** evade login, alter official grades, bypass proctoring or submit fake results.

## Verification and remaining gaps

On each PR, the feature workflow runs Python desktop tests, Node voice and USGS UI tests, and `npm run build`. The full end-to-end Ash release gate, physical device voice/hologram, real Wazuh service, Magic UI registry installation, God's Eye View running Node 24.14+/26, and Strix report export compatibility require separate manual or integration acceptance. A green web build is not a benchmark proving GPT-Astra-equivalent model reasoning.

To validate on a paired desktop:

```powershell
pip install -r desktop_worker/requirements.txt
$env:PYTHONPATH = "desktop_worker"
python -m unittest discover -s desktop_worker -p "test_*.py"
node --test tests/exact-reply.test.mjs tests/intelligence-view.test.mjs
npm install
npm run build
```

Security: never enter your school credentials into an untrusted plugin or use Ash to bypass a learning provider's controls.
