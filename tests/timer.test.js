const test = require("node:test");
const assert = require("node:assert/strict");
const {
  normalizeMinutes,
  formatClock,
  formatDuration,
  elapsedSeconds,
  getPhase,
} = require("../timer.js");

test("normalizes countdown minutes to the supported range", () => {
  assert.equal(normalizeMinutes("25"), 25);
  assert.equal(normalizeMinutes("0"), 15);
  assert.equal(normalizeMinutes("1000"), 999);
  assert.equal(normalizeMinutes("bad"), 15);
});

test("formats positive countdown time with a two-digit minute and second", () => {
  assert.equal(formatClock(272), "04:32");
  assert.equal(formatClock(0), "00:00");
});

test("formats overtime with a visible negative sign", () => {
  assert.equal(formatClock(-1), "−00:01");
  assert.equal(formatClock(-138), "−02:18");
});

test("calculates complete use from remaining time before and after the deadline", () => {
  assert.equal(elapsedSeconds(900, 272), 628);
  assert.equal(elapsedSeconds(900, -138), 1038);
});

test("formats complete use and identifies timer phases", () => {
  assert.equal(formatDuration(628), "10 分 28 秒");
  assert.equal(getPhase(61), "running");
  assert.equal(getPhase(60), "low");
  assert.equal(getPhase(0), "low");
  assert.equal(getPhase(-1), "overtime");
});
