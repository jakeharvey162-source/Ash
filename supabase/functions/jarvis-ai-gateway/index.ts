import "jsr:@supabase/functions-js/edge-runtime.d.ts";

type Mode = "instant" | "medium" | "high";
type ChatMessage = { role?: string; content?: string };
type ChatBody = {
  action?: "chat" | "speech" | "research";
  message?: string;
  mode?: Mode;
  history?: ChatMessage[];
  text?: string;
  voice_id?: string;
};

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      ...cors
    }
  });
}

async function requireUser(req: Request) {
  const auth = req.headers.get("Authorization") || "";
  if (!auth.startsWith("Bearer ")) return null;

  const url = Deno.env.get("SUPABASE_URL");
  const anon = Deno.env.get("SUPABASE_ANON_KEY");
  if (!url || !anon) return null;

  const response = await fetch(`${url}/auth/v1/user`, {
    headers: { Authorization: auth, apikey: anon }
  });
  if (!response.ok) return null;

  return { user: await response.json(), auth, url, anon };
}

async function getProfile(ctx: { user: any; auth: string; url: string; anon: string }) {
  const response = await fetch(
    `${ctx.url}/rest/v1/jarvis_profiles?user_id=eq.${encodeURIComponent(ctx.user.id)}&select=*`,
    { headers: { Authorization: ctx.auth, apikey: ctx.anon } }
  );
  if (!response.ok) return null;
  const rows = await response.json();
  return rows?.[0] || null;
}

async function getStyleSignals(ctx: { user: any; auth: string; url: string; anon: string }) {
  const response = await fetch(
    `${ctx.url}/rest/v1/jarvis_style_signals?user_id=eq.${encodeURIComponent(ctx.user.id)}&select=*`,
    { headers: { Authorization: ctx.auth, apikey: ctx.anon } }
  );
  if (!response.ok) return null;
  const rows = await response.json();
  return rows?.[0] || null;
}

function countEmoji(text: string) {
  return (text.match(/[\u{1F300}-\u{1FAFF}]/gu) || []).length;
}

function slangScore(text: string) {
  const words = ["bro", "ngl", "lol", "lmao", "u", "rn", "pls", "yeah", "yep", "nah", "fr", "gonna", "wanna"];
  const lower = ` ${text.toLowerCase()} `;
  return words.reduce((score, word) => score + (lower.includes(` ${word} `) ? 1 : 0), 0);
}

async function learnStyle(ctx: { user: any; auth: string; url: string; anon: string }, message: string, profile: any) {
  if (profile?.behavior_config?.learn_style === false) return;

  const current = await getStyleSignals(ctx);
  const previousCount = Number(current?.sample_count || 0);
  const nextCount = previousCount + 1;
  const length = message.length;
  const slang = slangScore(message);
  const emoji = countEmoji(message);
  const brevity = length < 120 ? 1 : length < 300 ? 0.5 : 0;

  const blend = (oldValue: number, newValue: number) =>
    ((oldValue * previousCount) + newValue) / nextCount;

  const payload = {
    user_id: ctx.user.id,
    sample_count: nextCount,
    average_message_length: blend(Number(current?.average_message_length || 0), length),
    slang_score: blend(Number(current?.slang_score || 0), slang),
    emoji_score: blend(Number(current?.emoji_score || 0), emoji),
    brevity_score: blend(Number(current?.brevity_score || 0), brevity),
    last_updated_at: new Date().toISOString(),
    summary: {
      tone_hint: slang >= 1 ? "casual" : "neutral",
      prefers_short: length < 160
    }
  };

  await fetch(`${ctx.url}/rest/v1/jarvis_style_signals?on_conflict=user_id`, {
    method: "POST",
    headers: {
      Authorization: ctx.auth,
      apikey: ctx.anon,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates"
    },
    body: JSON.stringify(payload)
  }).catch(() => {});
}

function buildSystemPrompt(profile: any, style: any) {
  const name = String(profile?.assistant_name || "Ash").slice(0, 40);
  const preset = String(profile?.personality_preset || "adaptive");
  const behavior = profile?.behavior_config || {};
  const custom = String(profile?.custom_instructions || "").slice(0, 4000);
  const verbosity = String(behavior.verbosity || "balanced");
  const proactivity = String(behavior.proactivity || "balanced");
  const humor = Math.max(0, Math.min(100, Number(behavior.humor ?? 25)));

  const personalities: Record<string, string> = {
    adaptive: "Adapt naturally to the user's tone while remaining grounded, capable and respectful.",
    executive: "Be calm, concise, organized and decisive. Lead with the answer and next action.",
    companion: "Be warm, conversational and emotionally aware without becoming overly familiar.",
    builder: "Be highly practical and implementation-focused. Prefer concrete steps, working code and tests.",
    analyst: "Be structured, evidence-first and precise. Separate facts, assumptions and conclusions.",
    coach: "Be patient, motivating and clear. Teach through manageable steps and useful feedback."
  };

  const styleHint = style
    ? `Observed user style: average message length ${Math.round(Number(style.average_message_length || 0))}; casual-language score ${Number(style.slang_score || 0).toFixed(1)}; brevity preference ${Number(style.brevity_score || 0).toFixed(1)}. Mirror style lightly, never caricature it.`
    : "";

  return [
    `You are ${name}, the single front door to a private multi-agent AI organization. Your default identity is Ash until the user chooses another assistant name.`,
    personalities[preset] || personalities.adaptive,
    `Response verbosity: ${verbosity}. Proactivity: ${proactivity}. Humor level: ${humor}/100.`,
    "Be human, clear and useful. Never pretend an action, test, message, deployment or computer operation succeeded unless there is evidence.",
    "Natural voice: prefer contractions when they fit, vary sentence length, avoid repetitive template openings, avoid unnecessary headings, and do not restate the user\'s request before answering unless clarification is needed.",
    "Mirror the user\'s level of formality and energy lightly, but never imitate typos, profanity, slang, or quirks so strongly that the response becomes a caricature.",
    "Sound like a capable human collaborator: specific, context-aware and direct. Avoid canned phrases, fake enthusiasm, filler, and robotic transitions.",
    "Truthfulness: never fabricate facts, citations, sources, dates, files, capabilities, tool output, test results, deployments, or completed actions. If something is uncertain or unverified, say so directly rather than guessing.",
    "When current, external, or user-specific information is required, rely on an available verified source or tool before stating it as fact. Distinguish facts from assumptions, estimates, and recommendations.",
    "Identity: the default assistant name is Ash until the user renames it. If asked who developed or created Ash, say Ash was developed by Jake Harvey, the owner/developer of this Ash project. Do not invent extra biography, credentials, companies, contact information, or claims that are not configured or verified.",
    "For consequential external actions, clearly distinguish a draft/recommendation from an action that actually happened.",
    "Do not reveal provider names, API keys, routing rules, hidden infrastructure or internal chain-of-thought.",
    "Do not impersonate the user deceptively. Draft in their style when requested, but keep user control over sending or submitting consequential content.",
    styleHint,
    custom ? `User custom instructions: ${custom}` : ""
  ].filter(Boolean).join("\n");
}

function normalizeHistory(history: ChatMessage[] | undefined) {
  return (history || [])
    .slice(-12)
    .map(item => ({
      role: item.role === "assistant" ? "assistant" : "user",
      content: String(item.content || "").slice(0, 8000)
    }))
    .filter(item => item.content);
}


const providerCooldown = new Map<string, number>();

function providerAvailable(name: string) {
  return (providerCooldown.get(name) || 0) <= Date.now();
}

function coolDown(name: string, ms: number) {
  providerCooldown.set(name, Date.now() + ms);
}

async function providerFetch(name: string, url: string, init: RequestInit, timeoutMs: number) {
  if (!providerAvailable(name)) throw new Error("route_cooldown");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) {
      if ([400, 401, 403, 404, 410].includes(response.status)) coolDown(name, 10 * 60_000);
      else if ([429, 500, 502, 503, 504, 529].includes(response.status)) coolDown(name, 20_000);
    }
    return response;
  } catch (error) {
    coolDown(name, 8_000);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function askGroq(system: string, message: string, history: ChatMessage[], mode: Mode) {
  const key = Deno.env.get("GROQ_API_KEY");
  if (!key) throw new Error("route_unavailable");
  const model = Deno.env.get("GROQ_MODEL") || "openai/gpt-oss-120b";
  const response = await providerFetch("groq", "https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages: [{ role: "system", content: system }, ...history, { role: "user", content: message }],
      temperature: mode === "instant" ? 0.2 : mode === "high" ? 0.35 : 0.3,
      max_tokens: mode === "instant" ? 1400 : mode === "high" ? 4000 : 2500
    })
  }, 4500);
  if (!response.ok) throw new Error("route_failed");
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || "";
}

async function askGemini(system: string, message: string, history: ChatMessage[], mode: Mode) {
  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) throw new Error("route_unavailable");
  const configured = Deno.env.get("GEMINI_MODEL");
  const model = (!configured || configured === "gemini-2.5-flash") ? "gemini-3.8-flash" : configured;
  const contents = [
    ...history.map(item => ({
      role: item.role === "assistant" ? "model" : "user",
      parts: [{ text: String(item.content || "") }]
    })),
    { role: "user", parts: [{ text: message }] }
  ];

  const response = await providerFetch(
    "gemini",
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: system }] },
        contents,
        generationConfig: {
          temperature: mode === "instant" ? 0.2 : mode === "high" ? 0.35 : 0.3,
          maxOutputTokens: mode === "instant" ? 1400 : mode === "high" ? 4000 : 2500
        }
      })
    },
    6000
  );
  if (!response.ok) throw new Error("route_failed");
  const data = await response.json();
  return data?.candidates?.[0]?.content?.parts?.map((part: any) => part.text || "").join("") || "";
}

async function askOpenRouter(system: string, message: string, history: ChatMessage[], mode: Mode) {
  const key = Deno.env.get("OPENROUTER_API_KEY");
  if (!key) throw new Error("route_unavailable");
  const model = Deno.env.get("OPENROUTER_MODEL") || "openrouter/free";
  const response = await providerFetch("openrouter", "https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      "X-Title": "Ash"
    },
    body: JSON.stringify({
      model,
      messages: [{ role: "system", content: system }, ...history, { role: "user", content: message }],
      temperature: mode === "instant" ? 0.2 : mode === "high" ? 0.35 : 0.3
    })
  }, 6500);
  if (!response.ok) throw new Error("route_failed");
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || "";
}

async function askAnthropic(system: string, message: string, history: ChatMessage[], mode: Mode) {
  const key = Deno.env.get("ANTHROPIC_API_KEY");
  if (!key) throw new Error("route_unavailable");
  const model = Deno.env.get("ANTHROPIC_MODEL") || "claude-sonnet-4-6";
  const workspace = Deno.env.get("ANTHROPIC_WORKSPACE_ID");
  if (!workspace) throw new Error("route_unavailable");
  const response = await providerFetch("anthropic", "https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
      "anthropic-workspace-id": workspace,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model,
      system,
      max_tokens: mode === "instant" ? 1400 : mode === "high" ? 4000 : 2500,
      messages: [...history, { role: "user", content: message }]
    })
  }, 8000);
  if (!response.ok) throw new Error("route_failed");
  const data = await response.json();
  return (data?.content || []).map((part: any) => part?.text || "").join("");
}

async function askNvidia(system: string, message: string, history: ChatMessage[], mode: Mode) {
  const key = Deno.env.get("NVIDIA_API_KEY");
  if (!key) throw new Error("route_unavailable");
  const configured = Deno.env.get("NVIDIA_MODEL");
  const model = (!configured || configured === "meta/llama-3.3-70b-instruct" || configured === "deepseek-ai/deepseek-v4.1-flash") ? "z-ai/glm-5.3-flash" : configured;
  const response = await providerFetch("nvidia", "https://integrate.api.nvidia.com/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages: [{ role: "system", content: system }, ...history, { role: "user", content: message }],
      temperature: mode === "instant" ? 0.2 : 0.3,
      max_tokens: mode === "instant" ? 1000 : mode === "high" ? 3000 : 2000
    })
  }, 7000);
  if (!response.ok) throw new Error("route_failed");
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || "";
}

async function askBytez(system: string, message: string, history: ChatMessage[], mode: Mode) {
  const key = Deno.env.get("BYTEZ_API_KEY");
  if (!key) throw new Error("route_unavailable");
  const configured = Deno.env.get("BYTEZ_MODEL");
  if (!configured || configured === "google/gemma-3-4b-it" || configured === "Qwen/Qwen3-4B" || configured === "Qwen/Qwen3-0.6B") throw new Error("route_unavailable");
  const response = await providerFetch("bytez", "https://api.bytez.com/models/v2/openai/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: configured,
      messages: [{ role: "system", content: system }, ...history, { role: "user", content: message }],
      temperature: mode === "instant" ? 0.2 : 0.3,
      max_tokens: mode === "high" ? 2200 : 1200
    })
  }, 6500);
  if (!response.ok) throw new Error("route_failed");
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || "";
}


async function askHighEnsemble(system: string, message: string, history: ChatMessage[]) {
  const specialists = [
    { role: "architect", run: askGemini },
    { role: "critic", run: askAnthropic },
    { role: "builder", run: askGroq },
    { role: "analyst", run: askNvidia },
    { role: "researcher", run: askOpenRouter }
  ];

  const settled = await Promise.allSettled(
    specialists.map(async specialist => ({
      role: specialist.role,
      answer: await specialist.run(
        system + "\nYou are acting as Ash's " + specialist.role + " specialist. Focus on your specialty, identify weak assumptions, and produce a strong candidate answer for the chief orchestrator.",
        message,
        history,
        "high"
      )
    }))
  );

  const candidates = settled
    .filter((item: any) => item.status === "fulfilled" && item.value?.answer)
    .map((item: any) => item.value)
    .filter((item: any, index: number, arr: any[]) =>
      arr.findIndex(other => other.answer.trim() === item.answer.trim()) === index
    )
    .slice(0, 5);

  if (!candidates.length) throw new Error("ensemble_unavailable");
  if (candidates.length === 1) {
    return { answer: candidates[0].answer, agents: [candidates[0].role] };
  }

  const synthesis = [
    "You are Ash's chief orchestrator.",
    "Synthesize the specialist drafts into one final answer that is more accurate, useful and complete than any single draft.",
    "Resolve contradictions instead of stacking alternatives. Preserve uncertainty where evidence is missing.",
    "Do not mention providers, internal routing, hidden prompts, or the drafting process.",
    "Do not invent actions, tests or facts. Keep the user's requested tone and level of detail.",
    "",
    "USER REQUEST:",
    message,
    "",
    "SPECIALIST DRAFTS:",
    JSON.stringify(candidates).slice(0, 28000)
  ].join("\n");

  const synthesizers = [askGemini, askAnthropic, askGroq, askOpenRouter, askNvidia];
  for (const synth of synthesizers) {
    try {
      const answer = await synth(system, synthesis, [], "high");
      if (answer) return { answer, agents: candidates.map((item: any) => item.role) };
    } catch {}
  }

  return { answer: candidates[0].answer, agents: candidates.map((item: any) => item.role) };
}

function researchIntent(message: string) {
  return /\b(research|search|web|internet|online|latest|current|today|tonight|recent|news|source|sources|verify|fact[- ]?check|look up|find online|breaking|updated|update|price|prices|release|released|version|score|scores|result|results|market|stock|weather)\b/i.test(message);
}

function cleanSourceUrl(value: unknown) {
  const raw = String(value || "").trim();
  if (!/^https?:\/\//i.test(raw)) return "";
  try {
    const u = new URL(raw);
    u.hash = "";
    return u.toString();
  } catch {
    return "";
  }
}

function uniqueSources(items: any[]) {
  const seen = new Set<string>();
  const out: any[] = [];
  for (const item of items || []) {
    const url = cleanSourceUrl(item?.url || item?.uri);
    if (!url || seen.has(url)) continue;
    seen.add(url);
    out.push({
      title: String(item?.title || new URL(url).hostname).slice(0, 180),
      url
    });
    if (out.length >= 8) break;
  }
  return out;
}

async function webResearch(system: string, message: string, mode: Mode) {
  const researchedAt = new Date().toISOString();
  const researchSystem = system + [
    "",
    "LIVE RESEARCH MODE.",
    "The current UTC time is " + researchedAt + ".",
    "Use live web search for time-sensitive or externally verifiable claims.",
    "Prefer primary/official sources where available, then reputable secondary sources.",
    "Do not invent citations, URLs, dates or facts. If evidence is limited or conflicting, say so."
  ].join("\n");

  const routes: Promise<any>[] = [];

  const geminiKey = Deno.env.get("GEMINI_API_KEY");
  if (geminiKey) {
    routes.push((async () => {
      const model = Deno.env.get("GEMINI_RESEARCH_MODEL") || "gemini-3.8-flash";
      const response = await providerFetch(
        "gemini_search",
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
        {
          method: "POST",
          headers: { "x-goog-api-key": geminiKey, "Content-Type": "application/json" },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: researchSystem }] },
            contents: [{ role: "user", parts: [{ text: message + "\nUse Google Search and cite the sources you used." }] }],
            tools: [{ google_search: {} }],
            generationConfig: { temperature: 0.12, maxOutputTokens: mode === "high" ? 2400 : 1500 }
          })
        },
        3500
      );
      if (!response.ok) throw new Error("gemini_search_failed_" + response.status);
      const data = await response.json();
      const candidate = data?.candidates?.[0] || {};
      const answer = candidate?.content?.parts?.map((part: any) => part?.text || "").join("").trim() || "";
      const grounding = candidate?.groundingMetadata || {};
      const chunks = Array.isArray(grounding?.groundingChunks) ? grounding.groundingChunks : [];
      const sources = uniqueSources(chunks
        .filter((c: any) => c?.web?.uri)
        .map((c: any) => ({ title: c.web.title || "", url: c.web.uri })));
      if (!answer || !sources.length) throw new Error("gemini_search_ungrounded");
      return { answer, sources, source: "gemini_search", researched_at: researchedAt };
    })());
  }

  const openRouterKey = Deno.env.get("OPENROUTER_API_KEY");
  if (openRouterKey) {
    routes.push((async () => {
      const response = await providerFetch(
        "openrouter_search",
        "https://openrouter.ai/api/v1/chat/completions",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${openRouterKey}`,
            "Content-Type": "application/json",
            "X-Title": "Ash Research"
          },
          body: JSON.stringify({
            model: Deno.env.get("OPENROUTER_RESEARCH_MODEL") || Deno.env.get("OPENROUTER_MODEL") || "openrouter/free",
            messages: [
              { role: "system", content: researchSystem },
              { role: "user", content: message }
            ],
            tools: [
              { type: "openrouter:web_search", parameters: { engine: "exa", max_results: mode === "high" ? 6 : 4, max_total_results: mode === "high" ? 10 : 6, max_characters: 2200 } },
              { type: "openrouter:datetime" }
            ],
            max_tokens: mode === "high" ? 2400 : mode === "instant" ? 900 : 1600,
            temperature: 0.12
          })
        },
        11000
      );
      if (!response.ok) throw new Error("openrouter_search_failed_" + response.status);
      const data = await response.json();
      const msg = data?.choices?.[0]?.message || {};
      const answer = String(msg?.content || "").trim();
      const annotations = Array.isArray(msg?.annotations) ? msg.annotations : [];
      const citationUrls = Array.isArray(msg?.citations) ? msg.citations : [];
      const sources = uniqueSources([
        ...annotations
          .filter((a: any) => a?.type === "url_citation" && a?.url_citation?.url)
          .map((a: any) => ({ title: a.url_citation.title || "", url: a.url_citation.url })),
        ...citationUrls.map((url: any) => ({ url }))
      ]);
      if (!answer || !sources.length) throw new Error("openrouter_search_ungrounded");
      return { answer, sources, source: "openrouter_web", researched_at: researchedAt };
    })());
  }

  if (!routes.length) throw new Error("web_search_unavailable");
  try {
    return await Promise.any(routes);
  } catch {
    throw new Error("web_search_unavailable");
  }
}


function integrationIntent(message: string) {
  return /\b(gmail|email|mail|inbox|calendar|meeting|appointment|drive|google drive|schedule)\b/i.test(message);
}

async function getIntegrationStatus(ctx: { user: any; auth: string; url: string; anon: string }, key: string) {
  const response = await fetch(
    `${ctx.url}/rest/v1/jarvis_integrations?user_id=eq.${encodeURIComponent(ctx.user.id)}&integration_key=eq.${encodeURIComponent(key)}&select=status`,
    { headers: { Authorization: ctx.auth, apikey: ctx.anon } }
  );
  if (!response.ok) return "disconnected";
  const rows = await response.json();
  return rows?.[0]?.status || "disconnected";
}

async function planIntegrationAction(message: string) {
  const planner = [
    "Return JSON only. Classify the user's Google integration request.",
    'Allowed tools: "gmail.list", "gmail.send", "calendar.list", "calendar.create", "drive.search", "none".',
    "For gmail.send extract to, subject and body. Never invent a recipient address.",
    "For calendar.create extract an event object with summary and start/end only when the user supplied enough information.",
    "For read tools use conservative limits. If the request is not clearly one of these tools return none.",
    'Schema: {"tool":"none","args":{}}'
  ].join("\n");

  const raw = await askGroq(planner, message, [], "instant");
  const cleaned = String(raw || "").replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
  try {
    const parsed = JSON.parse(cleaned);
    const allowed = new Set(["gmail.list","gmail.send","calendar.list","calendar.create","drive.search","none"]);
    if (!allowed.has(parsed?.tool)) return { tool: "none", args: {} };
    return { tool: parsed.tool, args: parsed.args || {} };
  } catch {
    return { tool: "none", args: {} };
  }
}

async function callIntegration(ctx: { user: any; auth: string; url: string; anon: string }, action: string, payload: any) {
  const response = await fetch(`${ctx.url}/functions/v1/ash-integrations?action=${encodeURIComponent(action)}`, {
    method: "POST",
    headers: {
      Authorization: ctx.auth,
      apikey: ctx.anon,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload || {})
  });
  const text = await response.text();
  let data: any = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!response.ok) {
    const error: any = new Error(data?.error || `integration_${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

async function speech(text: string, voiceId?: string) {
  const key = Deno.env.get("ELEVENLABS_API_KEY");
  if (!key) return null;

  const voice = voiceId || Deno.env.get("ELEVENLABS_VOICE_ID") || "cjVigY5qzO86Huf0OWal";
  const model = Deno.env.get("ELEVENLABS_MODEL") || "eleven_flash_v2_5";
  const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(voice)}/stream?output_format=mp3_44100_128`, {
    method: "POST",
    headers: {
      "xi-api-key": key,
      "Content-Type": "application/json",
      Accept: "audio/mpeg"
    },
    body: JSON.stringify({
      text: text.slice(0, 5000),
      model_id: model,
      voice_settings: { stability: 0.52, similarity_boost: 0.78, style: 0.18, use_speaker_boost: true }
    })
  });
  if (!response.ok) return null;

  return new Response(response.body, {
    status: 200,
    headers: { "Content-Type": "audio/mpeg", "Cache-Control": "no-store", ...cors }
  });
}

async function transcribe(req: Request) {
  const key = Deno.env.get("GROQ_API_KEY");
  if (!key) return json({ error: "voice_input_not_configured" }, 503);

  const form = await req.formData();
  const audio = form.get("audio");
  if (!(audio instanceof File)) return json({ error: "audio_required" }, 400);
  if (audio.size > 12_000_000) return json({ error: "audio_too_large" }, 413);

  const outgoing = new FormData();
  outgoing.append("file", audio, audio.name || "jarvis-input.webm");
  outgoing.append("model", Deno.env.get("WHISPER_MODEL") || "whisper-large-v3-turbo");
  outgoing.append("response_format", "json");

  const response = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
    body: outgoing
  });
  if (!response.ok) return json({ error: "transcription_failed" }, 502);
  const data = await response.json();
  return json({ text: String(data.text || "") });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const ctx = await requireUser(req);
  if (!ctx) return json({ error: "unauthorized" }, 401);

  const url = new URL(req.url);
  if (url.searchParams.get("action") === "health") {
    return json({
      ok: true,
      service: "jarvis-ai-gateway",
      cloud_ready: Boolean(
        Deno.env.get("GROQ_API_KEY") ||
        Deno.env.get("GEMINI_API_KEY") ||
        Deno.env.get("ANTHROPIC_API_KEY") ||
        Deno.env.get("OPENROUTER_API_KEY") ||
        Deno.env.get("NVIDIA_API_KEY") ||
        Deno.env.get("BYTEZ_API_KEY")
      ),
      voice_ready: Boolean(Deno.env.get("ELEVENLABS_API_KEY"))
    });
  }
  if (url.searchParams.get("action") === "transcribe") {
    try { return await transcribe(req); }
    catch { return json({ error: "transcription_failed" }, 500); }
  }

  try {
    const body = await req.json() as ChatBody;
    const action = body.action || "chat";
    const profile = await getProfile(ctx);
    const style = await getStyleSignals(ctx);

    if (action === "speech") {
      const text = String(body.text || "").trim();
      if (!text) return json({ error: "text_required" }, 400);
      const configuredVoice = String(body.voice_id || profile?.voice_config?.voice_id || "");
      const result = await speech(text, configuredVoice || undefined);
      return result || json({ error: "voice_not_configured" }, 503);
    }

    const message = String(body.message || "").trim();
    const mode: Mode = body.mode === "instant" || body.mode === "high" ? body.mode : "medium";
    if (!message) return json({ error: "message_required" }, 400);
    if (message.length > 20_000) return json({ error: "message_too_long" }, 413);

    const system = buildSystemPrompt(profile, style);
    const history = normalizeHistory(body.history);

    if (integrationIntent(message)) {
      try {
        const plan = await planIntegrationAction(message);
        if (plan.tool !== "none") {
          const integrationKey = plan.tool.startsWith("gmail.") ? "gmail"
            : plan.tool.startsWith("calendar.") ? "google_calendar"
            : "google_drive";
          const status = await getIntegrationStatus(ctx, integrationKey);
          if (status !== "connected") {
            const display = integrationKey === "gmail" ? "Gmail" : integrationKey === "google_calendar" ? "Google Calendar" : "Google Drive";
            return json({
              answer: `${display} is not connected yet. Open Ash → Connections and connect it first.`,
              mode,
              assistant_name: profile?.assistant_name || "Ash",
              integration_required: integrationKey
            });
          }

          if (plan.tool === "gmail.send" || plan.tool === "calendar.create") {
            return json({
              answer: plan.tool === "gmail.send"
                ? `I prepared the email to ${plan.args?.to || "the recipient"}. Confirm it before I send it.`
                : "I prepared the calendar event. Confirm it before I create it.",
              mode,
              assistant_name: profile?.assistant_name || "Ash",
              requires_confirmation: true,
              pending_action: { tool: plan.tool, args: plan.args }
            });
          }

          const toolResult = await callIntegration(ctx, plan.tool, plan.args);
          const summarized = await askGroq(
            system + "\nYou are summarizing verified data returned by an authorized user integration. Do not invent missing fields.",
            message + "\n\nINTEGRATION RESULT:\n" + JSON.stringify(toolResult).slice(0, 18000),
            [],
            mode
          );
          learnStyle(ctx, message, profile);
          return json({
            answer: summarized,
            mode,
            assistant_name: profile?.assistant_name || "Ash",
            tool_used: plan.tool,
            verified_external_data: true
          });
        }
      } catch {
        // Fall through to normal Ash response if integration planning fails.
      }
    }

    if (action === "research" || researchIntent(message)) {
      try {
        const researched = await webResearch(system, message, mode);
        learnStyle(ctx, message, profile);
        return json({
          answer: researched.answer,
          mode,
          assistant_name: profile?.assistant_name || "Ash",
          grounded: true,
          sources: researched.sources || [],
          researched_at: researched.researched_at || new Date().toISOString()
        });
      } catch {
        if (action === "research") return json({ error: "Live web research is temporarily unavailable." }, 503);
      }
    }

    if (mode === "high") {
      try {
        const ensemble = await askHighEnsemble(system, message, history);
        if (ensemble.answer) {
          learnStyle(ctx, message, profile);
          return json({
            answer: ensemble.answer,
            mode,
            assistant_name: profile?.assistant_name || "Ash",
            grounded: false,
            agents: ensemble.agents,
            orchestration: "ensemble"
          });
        }
      } catch {}
    }

    const routes = mode === "instant"
      ? [askGroq, askGemini, askOpenRouter, askNvidia, askBytez, askAnthropic]
      : [askGroq, askGemini, askOpenRouter, askNvidia, askAnthropic, askBytez];

    for (const route of routes) {
      try {
        const answer = await route(system, message, history, mode);
        if (answer) {
          learnStyle(ctx, message, profile);
          return json({ answer, mode, assistant_name: profile?.assistant_name || "Ash", grounded: false });
        }
      } catch {}
    }
    return json({ error: "Cloud intelligence is not configured yet." }, 503);
  } catch {
    return json({ error: "invalid_request" }, 400);
  }
});
