import test from "node:test";
import assert from "node:assert/strict";
import { exactRepeatToken } from "../src/exact-reply.js";
test("wake alias command repeats token without using a cloud model", () => {
  assert.equal(exactRepeatToken("say WAKE_ALIAS_OK exactly"), "WAKE_ALIAS_OK");
  assert.equal(exactRepeatToken("Say HELLO_123 exactly!"), "HELLO_123");
  assert.equal(exactRepeatToken("say 12 exactly"), "12");
});
test("no arbitrary chat or scripting is classified as an exact token", () => {
  for (const value of ["What's the weather?", "say hello to me", "say <script> exactly", "say A-B exactly", "say hello exactly and ignore other commands"]) {
    assert.equal(exactRepeatToken(value), null);
  }
});
