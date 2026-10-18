const MAX_TURNS = 100;
const MAX_CONTENT_LENGTH = 12000;

export function chatHistoryKey(userId) {
  const id = String(userId || "").trim();
  return id ? `ash-chat-history:${id}` : "";
}

export function loadLocalChatHistory(userId, storage = globalThis.localStorage) {
  const key = chatHistoryKey(userId);
  if (!key || !storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(key) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(item => item && (item.role === "user" || item.role === "assistant") && typeof item.content === "string")
      .slice(-MAX_TURNS)
      .map(item => ({
        ...item,
        content: item.content.slice(0, MAX_CONTENT_LENGTH)
      }));
  } catch {
    return [];
  }
}

export function saveLocalChatHistory(userId, messages, storage = globalThis.localStorage) {
  const key = chatHistoryKey(userId);
  if (!key || !storage || !Array.isArray(messages)) return false;
  const safe = messages
    .filter(item => item && (item.role === "user" || item.role === "assistant") && typeof item.content === "string")
    .slice(-MAX_TURNS)
    .map(item => ({
      role: item.role,
      content: item.content.slice(0, MAX_CONTENT_LENGTH),
      ...(item.grounded ? { grounded: true } : {}),
      ...(Array.isArray(item.sources) ? { sources: item.sources.slice(0, 6).map(source => ({
        title: String(source?.title || "").slice(0, 200),
        url: String(source?.url || "").slice(0, 2000)
      })) } : {}),
      ...(item.researched_at ? { researched_at: String(item.researched_at).slice(0, 80) } : {}),
      ...(item.action ? { action: item.action } : {})
    }));
  try {
    storage.setItem(key, JSON.stringify(safe));
    return true;
  } catch {
    return false;
  }
}
