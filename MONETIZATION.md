# Ash monetization plan

Ash has recurring cloud/provider costs, so unlimited lifetime cloud access should not be sold as a one-time purchase.

## Recommended launch offer

### Free
- Ash web chat
- Windows hologram companion
- basic voice and wake word
- one linked desktop
- local/offline mode when the user's hardware supports it
- small daily cloud allowance
- limited browser Builder usage

Purpose: make the hologram itself shareable and give users enough value to build habit.

### Pro
Suggested launch target: **US$8.99/month** or a localized South African price around **R149/month** before taxes.

Include:
- higher cloud usage
- advanced research
- full desktop agent routing
- software Builder
- OpenJarvis specialist profiles
- more automations
- multiple linked desktops
- premium voice allowance
- priority generation routes

Use a fair-use or credit allowance internally so one heavy user cannot create unlimited provider cost.

### Creator
Suggested target: **US$19.99/month**.

Include:
- larger Builder/research allowance
- more concurrent jobs
- project backups/history
- advanced CodeAct workflows
- higher voice allowance
- early-access features

### Teams
Do not launch until organization permissions, billing ownership, audit logs and usage caps are verified.

## Fastest revenue path

1. Ship a reliable free Windows installer.
2. Put Pro behind billing only after users can complete first-run setup successfully.
3. Offer a 7-day Pro trial.
4. Add a visible upgrade path when a user reaches a cloud/Builder allowance.
5. Sell additional usage as top-up credits rather than promising unlimited expensive cloud tasks.
6. Keep local/offline inference inexpensive or free where practical.

## What should remain free

The visual hologram should not be paywalled. It is Ash's strongest viral surface.

A user should be able to install Ash, see the companion, use the wake word and experience basic assistance before paying.

Charge for scarce or expensive value: cloud reasoning, high-volume research, Builder jobs, premium speech, parallel agents, long-running automations and team controls.

## Payments

Use Stripe Checkout or Payment Links initially instead of building card handling yourself.

Minimum backend billing fields:
- user_id
- plan
- subscription_status
- stripe_customer_id
- stripe_subscription_id
- current_period_end
- monthly_usage_limit
- monthly_usage_used

Use Stripe webhooks to update entitlement state. Never trust a browser-only "is_pro" flag.

## Unit economics

For every paid plan track:

revenue per user - payment fees - model/research cost - speech cost - hosting/database cost - support cost

Set usage limits from real costs, not guesses. Review the 95th-percentile user cost before increasing allowances.

## Avoid

- unlimited lifetime cloud access
- charging before the first-run installer/pairing flow is reliable
- claiming Ash is better than another product without a matched benchmark
- hiding provider or usage failures behind fake success states
- storing payment card data yourself
