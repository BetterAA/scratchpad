const test = require("node:test");
const assert = require("node:assert/strict");
const {
  collectPushItems,
  mergePulledTabs,
  normalizeDays,
  isUntitled,
} = require("../git-sync.js");

test("recognizes generated and empty titles as untitled", () => {
  assert.equal(isUntitled("草稿 1"), true);
  assert.equal(isUntitled("  "), true);
  assert.equal(isUntitled("工作记录"), false);
});

test("collects all tabs and lets the later duplicate title win", () => {
  const result = collectPushItems([
    { title: "工作记录", content: "first" },
    { title: "会议", content: "notes" },
    { title: "工作记录", content: "latest" },
  ]);

  assert.deepEqual(result.invalid, []);
  assert.deepEqual(result.items, [
    { title: "工作记录", content: "latest" },
    { title: "会议", content: "notes" },
  ]);
});

test("reports untitled and unsafe titles before a push", () => {
  const result = collectPushItems([
    { title: "草稿 1", content: "needs a name" },
    { title: "bad/name", content: "unsafe path" },
  ]);

  assert.equal(result.items.length, 0);
  assert.equal(result.invalid.length, 2);
});

test("merges pulled content into matching tabs and appends new titles", () => {
  const result = mergePulledTabs(
    [
      { id: "a", title: "工作记录", content: "old" },
      { id: "b", title: "本地草稿", content: "keep" },
    ],
    [
      { title: "工作记录", content: "remote" },
      { title: "远端记录", content: "new" },
    ],
    () => "c"
  );

  assert.equal(result.updated, 1);
  assert.equal(result.added, 1);
  assert.deepEqual(result.tabs, [
    { id: "a", title: "工作记录", content: "remote" },
    { id: "b", title: "本地草稿", content: "keep" },
    { id: "c", title: "远端记录", content: "new" },
  ]);
});

test("clamps the pull window to one through 3650 days", () => {
  assert.equal(normalizeDays(undefined), 1);
  assert.equal(normalizeDays("0"), 1);
  assert.equal(normalizeDays("30"), 30);
  assert.equal(normalizeDays("9999"), 3650);
});
