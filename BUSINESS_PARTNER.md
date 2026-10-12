# Ash Business Partner — verified capability guide (2026-10-12)

Ash is the user-facing coordinator. Specialized AI backends and tool handlers work behind Ash; the user does not have to speak to each specialist independently.

## Implemented in this change

**Business Desk** (signed-in web and mobile navigation):
1. Enter a real customer's project brief and contact email.
2. Queue an actual `builder` job in Ash's existing account-scoped `jarvis_remote_jobs` queue.
3. A paired running desktop worker picks it up, generates the website, attempts a real build, and reports evidence.
4. The Business Desk lists customer builds and distinguishes successful local builds from failed/unverified builds.
5. Customer handoff and payment are **never** automatically marked complete. The owner reviews work in Activity.

No customer email is sent simply because a build finished. A local preview is not a public deployment. A static source checklist is not a browser test or proof of customer satisfaction.

**Phone call alerts** (opt-in, desktop-only):
- `desktop_worker/call_alerts.py` can request an outbound owner alert through Twilio Programmable Voice when the local desktop worker reaches a confirmation-required task.
- Calls use a single validated, owner-configured E.164 phone number. The LLM, customers, and jobs cannot choose the destination.
- Daily attempts are limited (default 2, maximum 3); repeated alerts for the same job/day are deduplicated and marked before the paid network call.
- The voice prompt tells the owner to authenticate to Ash and review Activity. The telephone call does **not** approve the job, execute any external action, or ask for secret information.
- Without explicit carrier configuration it does not dial or incur phone charges.

To enable on a locally paired Windows desktop, provision a Twilio voice-capable caller number, complete Twilio's verification requirements, then set the following **in your machine's private environment**, not in GitHub or browser configuration:

```powershell
ASH_CALL_ALERTS_ENABLED=1
ASH_OWNER_PHONE=+27...
TWILIO_FROM_NUMBER=+27...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=<private value>
ASH_CALL_ALERT_MAX_DAILY=2
```

Restart the Ash desktop worker. The recipient should only be the account owner's own number. Country-specific availability, trial restrictions, regulatory documentation and per-minute charges depend on Twilio. **There is no automatic phone number provisioning in this release.** Make sure the owner consents to receiving automated calls. Use the in-app approval control for all consequential actions.

**BROBS read-only review**:
- Export a CSV trade statement from the actual broker with exactly the columns `symbol,side,status,realized_pnl` and place it inside `ASH_WORKSPACE_ROOT`.
- Ask Ash to use `brobs.journal.review` with that relative path.
- Ash calculates closed-trade count, win rate, gross and net realized P&L, profit factor, worst trade and open position count using Decimal arithmetic.
- Imported data are labelled **not live** and **not broker verified**. Currency is unspecified until the broker's export metadata is independently checked.
- This integration cannot move money, place orders, alter leverage, or claim predictive performance.

## Existing Ash capabilities used

- Adaptive cloud/local model routing, OpenJarvis specialist profiles and code generation/repair are already implemented in the desktop worker.
- GitHub and premium builder references were incorporated previously as bounded tools. Arbitrary third-party repos are NOT silently executed, and `git clone` access is not elevated.
- Business work uses existing account-scoped job status, the paired desktop and the protected confirmation channel.
- Authenticated app approvals remain authoritative; a spoken or AI-generated statement of consent is not sufficient for spending money, trading or sharing private client work.

## Not yet implemented or verified

- A purchased phone number or actual paid outbound call in production.
- Answering Ash on a phone call with a verified voice/PIN and resuming a paused command.
- Authorized automated customer email, quoting/invoicing, signed contracts, payment-provider webhook verification, and public deployment/handoff.
- Live BROBS account/trade monitoring via a broker read-only API.
- A production-tested release after the free-tier deployment quota resets.
- A physically tested Windows install, phone microphone/voice quality and real customer journey.

## Tests and release checks

```powershell
npm ci
node --test tests/business-desk.test.mjs
npm run build
$env:PYTHONPATH = "desktop_worker"
python -m unittest desktop_worker/test_call_alerts.py desktop_worker/test_brobs_monitor.py desktop_worker/test_agent_runtime.py
```

The broader GitHub Actions suites should be green before merging and shipping. Test a real customer's full workflow with their permission before enabling outreach or payment processing.
