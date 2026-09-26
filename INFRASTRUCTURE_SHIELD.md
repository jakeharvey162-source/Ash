# Ash infrastructure shield

Ash can run in **same-origin shield mode** so the browser sees only Ash-owned `/api/supabase/...` URLs instead of the underlying data/AI infrastructure.

## Required server-side environment variables

- `ASH_PUBLIC_API_BASE=/api/supabase`
- `ASH_SUPABASE_ORIGIN` — the private upstream project origin
- `ASH_SUPABASE_PUBLISHABLE_KEY` — the upstream publishable key

The build's `prebuild` step rewrites `public/config.js` only when `ASH_PUBLIC_API_BASE` is set. Existing deployments remain in direct mode until a compatible server deployment is configured.

The proxy only forwards Ash's approved Auth, REST, AI gateway, device-link and integrations routes. Provider credentials remain server-side.

This is infrastructure **shielding**, not a claim of cryptographic invisibility: any public app necessarily exposes its own public hostname and observable traffic patterns.
