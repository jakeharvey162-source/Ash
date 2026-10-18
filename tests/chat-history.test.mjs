import test from "node:test";
import assert from "node:assert/strict";
import { chatHistoryKey, loadLocalChatHistory, saveLocalChatHistory } from "../src/chat-history.js";

function createStorage(seed = {}) {
  const data = new Map(Object.entries(seed));
  return {
    getItem: key => data.has(key) ? data.get(key) : null,
    setItem: (key, value) => data.set(key, String(value)),
    data
  };
}

test("history is stored separately for each signed-in user", () => {
  const storage = createStorage();
  assert.equal(saveLocalChatHistory("user-a", [{ role: "user", content: "hello" }], storage), true);
  assert.equal(loadLocalChatHistory("user-a", storage)[0].content, "hello");
  assert.deepEqual(loadLocalChatHistory("user-b", storage), []);
  assert.equal(chatHistoryKey("user-a"), "ash-chat-history:user-a");
});

test("invalid and malformed history is safely ignored", () => {
  const storage = createStorage({ "ash-chat-history:user-a": "{broken" });
  assert.deepEqual(loadLocalChatHistory("user-a", storage), []);
  assert.deepEqual(loadLocalChatHistory("", storage), []);
});

test("history is bounded and ignores invalid turns", () => {
  const storage = createStorage();
  const turns = Array.from({ length: 130 }, (_, i) => ({ role: "user", content: String(i) }));
  turns.push({ role: "system", content: "not a chat turn" }, null);
  assert.equal(saveLocalChatHistory("user-a", turns, storage), true);
  const loaded = loadLocalChatHistory("user-a", storage);
  assert.equal(loaded.length, 100);
  assert.equal(loaded[0].content, "30");
  assert.equal(loaded.at(-1).content, "129");
});

test("storage quota failures do not crash chat", () => {
  const storage = { getItem: () => null, setItem: () => { throw new Error("quota"); } };
  assert.equal(saveLocalChatHistory("user-a", [{ role: "assistant", content: "hi" }], storage), false);
  assert.deepEqual(loadLocalChatHistory("user-a", storage), []);
});
