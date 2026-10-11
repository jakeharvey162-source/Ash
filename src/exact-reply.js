/** Deterministic, safe echo for exact-token voice checks; no cloud/model guesswork. */
export function exactRepeatToken(message) {
  if (typeof message !== "string") return null;
  const match = /^say\s+([a-zA-Z0-9_]{1,80})\s+exactly[.!]?$/i.exec(message.trim());
  return match ? match[1] : null;
}
