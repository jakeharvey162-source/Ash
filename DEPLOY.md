# Deploy Ash to Vercel

1. Import `jakeharvey162-source/Ash` in Vercel.
2. Framework preset: Other.
3. Build command: `npm run build`.
4. Output directory: `dist`.
5. Add the private values from `.env.example` to Vercel Project Settings > Environment Variables. Never commit their values.
6. Deploy.
7. Visit `/api/ash`. It should report `cloud_ready: true` after at least one text provider key is configured, and `voice_ready: true` after ElevenLabs is configured.
8. Sign into Ash and test Instant, Medium and High.

Supabase remains the account/memory/device backend. Provider secrets live only in Vercel's server environment.
