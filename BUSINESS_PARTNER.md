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

**Zero-cost owner phone notifications (ntfy push; opt-in, desktop-only)**:
- Ash sends brief fixed notifications with the open-source [ntfy](https://docs.ntfy.sh/) push service when a tool needs owner approval, or when a customer's website build is complete or failed.
- **This is a free internet push notification, not a real cellular telephone call**, and it does not support two-way conversation or give Ash a phone number.
- The notification opens Ash; sensitive actions still require a properly authenticated in-app approval. No voice response authorizes payments, trade orders, or customer delivery.
- Ash publishes no client names, balances, job IDs, personal details or secrets. The service is best-effort, not a safety-critical alerting system.
- Alerts are **off by default**. A long unguessable topic is required, and notifications have a default limit of 12 attempts per UTC day and are deduplicated by job and category.
- **Privacy warning:** free ntfy.sh topics are not access-controlled. A person who learns the topic can subscribe to the notifications or publish to it. Use a truly random secret topic, never put business details in alerts, and consider a self-hosted authenticated ntfy server if stronger privacy is needed.

One-time setup on your paired Windows desktop:
1. Install the **ntfy** app on your phone (Android/iPhone) and open it.
2. Generate a strong topic using `python -c "import secrets; print(secrets.token_urlsafe(32))"` on your own machine.
3. Subscribe to that exact topic in the ntfy app using the public `ntfy.sh` server. Do **not** use an easily guessed name like `ash-alerts`.
4. Set private environment variables in the session that launches Ash's desktop worker. Do not commit the topic to a repository or place it in browser Javascript.

```powershell
$env:ASH_PUSH_ENABLED = "1"
$env:ASH_NTFY_TOPIC = "<your own randomly generated secret topic>"
$env:ASH_PUSH_MAX_DAILY = "12"
```

5. Verify the setup and request a harmless end-to-end test using the **same terminal environment** as the desktop worker:

```powershell
python desktop_worker/owner_alert_cli.py check
python desktop_worker/owner_alert_cli.py test
```

The `check` command verifies local configuration only. The `test` command sends a fixed, non-sensitive push. **Only checking your actual phone confirms that delivery worked.** Do not put real client data or passwords into your ntfy topic.

6. Restart the Ash desktop worker. When Ash encounters a confirmation-required action or completes a Business Desk build, your phone should receive a notification while connected to the internet. Open Ash's Activity or Business Desk to act.
7. If you turn it off, set `ASH_PUSH_ENABLED=0`. The old Twilio calling module remains an unused legacy file; **the worker now uses only free push alerts**, so no paid telephone carrier is contacted.

**Known limits:** delivery still requires actual installation, a running paired desktop, internet access, topic subscription and device notification permissions. Do not claim a successful live phone alert until verified on the owner's physical device.

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

- A real mobile-number dialer or two-way phone call: neither is provided by the free ntfy service.
- Live ntfy end-to-end device notification verified on the owner's handset.
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
python -m unittest desktop_worker/test_free_owner_alerts.py desktop_worker/test_brobs_monitor.py desktop_worker/test_agent_runtime.py
```

The broader GitHub Actions suites should be green before merging and shipping. Test a real customer's full workflow with their permission before enabling outreach or payment processing.
