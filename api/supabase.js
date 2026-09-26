const ALLOWED_PREFIXES = [
  "/auth/v1/",
  "/rest/v1/",
  "/functions/v1/jarvis-ai-gateway",
  "/functions/v1/ash-device-link",
  "/functions/v1/ash-integrations"
];

function allowed(path) {
  return ALLOWED_PREFIXES.some(prefix => path === prefix.replace(/\/$/, "") || path.startsWith(prefix));
}

export default async function handler(req, res) {
  const origin = String(process.env.ASH_SUPABASE_ORIGIN || "").replace(/\/$/, "");
  const publishable = String(process.env.ASH_SUPABASE_PUBLISHABLE_KEY || "");
  const forwardedPath = "/" + String(req.query?.path || "").replace(/^\/+/, "");
  if (!origin || !publishable) {
    res.status(503).json({ error: "Ash secure API proxy is not configured." });
    return;
  }
  if (!allowed(forwardedPath)) {
    res.status(404).json({ error: "Unknown Ash API route." });
    return;
  }

  const incoming = new URL(req.url, "https://ash.invalid");
  incoming.searchParams.delete("path");
  const target = new URL(origin + forwardedPath);
  for (const [key, value] of incoming.searchParams) target.searchParams.append(key, value);

  const headers = {
    "apikey": publishable,
    "content-type": req.headers["content-type"] || "application/json",
    "accept": req.headers["accept"] || "*/*"
  };
  for (const name of ["authorization", "x-ash-device-id", "x-ash-device-secret"]) {
    if (req.headers[name]) headers[name] = req.headers[name];
  }

  let body;
  if (!["GET","HEAD"].includes(req.method)) {
    if (Buffer.isBuffer(req.body)) body = req.body;
    else if (typeof req.body === "string") body = req.body;
    else if (req.body !== undefined) body = JSON.stringify(req.body);
  }

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body,
    redirect: "manual"
  });

  res.status(upstream.status);
  const type = upstream.headers.get("content-type");
  if (type) res.setHeader("content-type", type);
  res.setHeader("cache-control", "no-store");
  const bytes = Buffer.from(await upstream.arrayBuffer());
  res.send(bytes);
}
