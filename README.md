# Ash

Ash is a customizable personal AI organization developed by Jake Harvey.

## Default identity
Ash is the default assistant name until a user chooses another name.

## Production architecture
- **Vercel:** public Ash web/PWA frontend only.
- **Supabase Auth:** accounts and sessions.
- **Supabase Database:** profiles, personalization, memory, missions, devices and realtime sync.
- **Supabase Edge Function:** private Ash AI gateway and provider routing.
- **Provider secrets:** Supabase Edge Function Secrets only; never GitHub, browser code, APK, or Vercel frontend variables.

## Deployment
Import this repository into Vercel. No private AI-provider keys are required in Vercel.

Before live AI works, configure the provider keys in Supabase **Edge Function Secrets**. The deployed gateway reads them with `Deno.env.get(...)`.

See `DEPLOY.md`.


## Desktop pairing

Ash now uses one-time pairing codes for local computers. Device status in the UI is backed by `jarvis_devices` heartbeats rather than placeholder state. Pairing credentials are revocable and the desktop can receive queued build/automation jobs through the `ash-device-link` broker.

## Voice visualization

Provider-generated audio is connected to a Web Audio analyser so the Ash waveform follows the actual output signal. Browser speech-synthesis fallback uses a clearly separate synthetic animation because browsers do not expose its raw output stream.
