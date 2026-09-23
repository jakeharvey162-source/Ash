# Deploy Ash

## Part 1 — Supabase provider secrets

Open your Ash Supabase project and go to **Edge Functions → Secrets**.

Add:
- GROQ_API_KEY
- GEMINI_API_KEY
- ANTHROPIC_API_KEY
- OPENROUTER_API_KEY
- NVIDIA_API_KEY
- BYTEZ_API_KEY
- ELEVENLABS_API_KEY

Recommended optional model settings:
- GROQ_MODEL=openai/gpt-oss-120b
- GEMINI_MODEL=gemini-2.5-flash
- ANTHROPIC_MODEL=claude-sonnet-4-6
- OPENROUTER_MODEL=openrouter/free
- NVIDIA_MODEL=meta/llama-3.3-70b-instruct
- BYTEZ_MODEL=google/gemma-3-4b-it
- ELEVENLABS_VOICE_ID=cjVigY5qzO86Huf0OWal
- ELEVENLABS_MODEL=eleven_flash_v2_5
- WHISPER_MODEL=whisper-large-v3-turbo

Supabase makes production secrets available to Edge Functions immediately; setting them does not require redeploying the function.

## Part 2 — Vercel

1. Import `jakeharvey162-source/Ash`.
2. Framework preset: **Other**.
3. Build command: `npm run build`.
4. Output directory: `dist`.
5. Deploy.

No private provider keys go into Vercel with this architecture.

The frontend is preconfigured to call the authenticated Supabase Edge Function:
`https://ftsomveafuskrutqzsvs.supabase.co/functions/v1/jarvis-ai-gateway`

## Part 3 — Test

1. Open the Vercel URL.
2. Create/sign into an Ash account.
3. Test Instant mode.
4. Test Medium mode.
5. Test High mode.
6. Enable spoken responses and test voice.

Rotate all temporary provider credentials shared during development before public release.
