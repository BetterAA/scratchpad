# 倒计时停止与超时负向计时 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让草稿编辑器的倒计时支持醒目运行状态、用户停止、到时后负向计时，并在停止后提示完整用时。

**Architecture:** 把无 DOM 的分钟归一化、时钟格式化、计时阶段和用时计算提取到根目录 `timer.js`，同时支持浏览器全局和 Node CommonJS 导入。`index.html` 继续负责页面交互，但用 `Date.now()` 计算实际经过时间，让后台标签页恢复后仍能显示正确的剩余或超时时间；`setInterval` 只负责刷新。到零时只触发一次提示音和红色告警，计时器保持运行直到用户点击“停止”。

**Tech Stack:** 原生 HTML/CSS/JavaScript、Node 内置 `node:test`、现有 Python 静态服务。

---

### Task 1: 为计时纯逻辑建立失败测试

**Files:**
- Create: `tests/timer.test.js`
- Test target: `timer.js`（此时尚未创建，测试应先失败）

- [ ] **Step 1: Write the failing tests**

创建 `tests/timer.test.js`，覆盖输入归一化、正向和负向时钟显示、完整用时、运行阶段：

```js
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
```

- [ ] **Step 2: Run the tests and verify the failure is expected**

Run:

```bash
node --test tests/timer.test.js
```

Expected: the test process fails because `../timer.js` does not exist yet. This is the required RED state for the new timer behavior.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/timer.test.js
git commit -m "test: specify countdown timing behavior"
```

### Task 2: 实现可测试的计时纯逻辑

**Files:**
- Create: `timer.js`
- Test: `tests/timer.test.js`

- [ ] **Step 1: Implement the minimal CommonJS/browser-compatible module**

创建 `timer.js`，导出测试需要的五个函数，并在浏览器中挂载到 `window.TimerLogic`：

```js
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TimerLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function normalizeMinutes(value) {
    var mins = parseInt(value, 10);
    if (!mins || mins < 1) mins = 15;
    if (mins > 999) mins = 999;
    return mins;
  }

  function formatClock(totalSeconds) {
    var seconds = Math.floor(Math.abs(Number(totalSeconds) || 0));
    var minutes = Math.floor(seconds / 60);
    var remainder = seconds % 60;
    var prefix = Number(totalSeconds) < 0 ? "−" : "";
    return prefix + (minutes < 10 ? "0" : "") + minutes + ":" +
      (remainder < 10 ? "0" : "") + remainder;
  }

  function elapsedSeconds(durationSec, timeLeftSec) {
    return Math.max(0, Math.floor(durationSec - timeLeftSec));
  }

  function formatDuration(totalSeconds) {
    var seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    var minutes = Math.floor(seconds / 60);
    return minutes + " 分 " + (seconds % 60) + " 秒";
  }

  function getPhase(timeLeftSec) {
    if (timeLeftSec < 0) return "overtime";
    if (timeLeftSec <= 60) return "low";
    return "running";
  }

  return {
    normalizeMinutes: normalizeMinutes,
    formatClock: formatClock,
    elapsedSeconds: elapsedSeconds,
    formatDuration: formatDuration,
    getPhase: getPhase,
  };
});
```

- [ ] **Step 2: Run the focused tests and verify GREEN**

Run:

```bash
node --test tests/timer.test.js
```

Expected: all five tests pass with zero failures.

- [ ] **Step 3: Check the module syntax**

Run:

```bash
node --check timer.js
```

Expected: exit code 0 and no output.

- [ ] **Step 4: Commit the pure logic**

```bash
git add timer.js tests/timer.test.js
git commit -m "feat: add testable countdown time logic"
```

### Task 3: 接入醒目状态和停止按钮

**Files:**
- Modify: `index.html:40-60` for timer colors and button styling
- Modify: `index.html:217-235` to load `timer.js` and keep timer references
- Modify: `index.html:434-515` to replace the timer controller

- [ ] **Step 1: Load the pure logic before the inline application script**

Insert `<script src="timer.js"></script>` immediately before the existing inline `<script>` tag. The inline controller can then call `TimerLogic` in the browser without changing the page’s loading model.

- [ ] **Step 2: Add the visual state rules**

Extend the existing countdown CSS with these state classes:

```css
.timebox {
  padding: 2px 4px; border: 1px solid transparent; border-radius: 8px;
  transition: color .2s, background .2s, border-color .2s, box-shadow .2s;
}
.timebox.running {
  color: #b45309; background: #fffbeb; border-color: #fbbf24;
  box-shadow: 0 0 0 3px rgba(245,158,11,.12);
}
.timebox.running #timeLeft { color: #b45309; font-weight: 700; }
.timebox.running #timeLeft.low { color: #ea580c; }
.timebox.overtime {
  color: #dc2626; background: #fef2f2; border-color: #fca5a5;
  box-shadow: 0 0 0 3px rgba(220,38,38,.14);
}
.timebox.overtime #timeLeft { color: #dc2626; font-weight: 700; }
button.btn.timer-stop {
  background: #dc2626; color: #fff; border-color: #dc2626; font-weight: 600;
}
button.btn.timer-stop:hover { background: #b91c1c; border-color: #b91c1c; }
```

Keep the existing `body.alarm` rules for the one-time arrival alert, but remove the one-minute auto-clear behavior so the red state remains until the user stops the timer.

- [ ] **Step 3: Replace the timer controller with timestamp-based updates**

Use the following behavior in the existing timer section:

```js
var timerInterval = null;
var timeLeftSec = 0;
var timerDurationSec = 0;
var timerStartedAt = 0;
var timerAlarmShown = false;

function clearAlarm() {
  document.body.classList.remove("alarm");
}

function showTimerPhase() {
  var phase = TimerLogic.getPhase(timeLeftSec);
  timeLeft.textContent = TimerLogic.formatClock(timeLeftSec);
  timeLeft.classList.toggle("low", phase === "low");
  timeBox.classList.toggle("overtime", phase === "overtime");
}

function updateTimer(triggerAlarm) {
  if (!timerStartedAt) return;
  var elapsed = Math.floor((Date.now() - timerStartedAt) / 1000);
  timeLeftSec = timerDurationSec - elapsed;
  showTimerPhase();
  if (triggerAlarm !== false && timeLeftSec <= 0 && !timerAlarmShown) {
    timerAlarmShown = true;
    startAlarm();
  }
}

function stopTimer() {
  if (!timerStartedAt) return;
  updateTimer(false);
  var elapsed = TimerLogic.elapsedSeconds(timerDurationSec, timeLeftSec);
  var overtime = Math.max(0, -timeLeftSec);
  clearInterval(timerInterval);
  timerInterval = null;
  timerStartedAt = 0;
  timerDurationSec = 0;
  timeBox.classList.remove("running", "overtime");
  timeLeft.classList.remove("low");
  clearAlarm();
  btnTime.classList.remove("timer-stop");
  btnTime.textContent = "time";
  btnTime.title = "开始倒计时";
  var message = "完整用时：" + TimerLogic.formatDuration(elapsed);
  if (overtime) message += "（含超时 " + TimerLogic.formatDuration(overtime) + "）";
  showPanel("计时已停止", message, false);
}

function startAlarm() {
  document.body.classList.add("alarm");
  beep();
  showPanel("倒计时", "时间到，仍在计时中，请点击“停止”结束本次计时。", false);
}

btnTime.addEventListener("click", function () {
  if (timerInterval) { stopTimer(); return; }
  var mins = TimerLogic.normalizeMinutes(timeInput.value);
  timeInput.value = mins;
  timerDurationSec = mins * 60;
  timerStartedAt = Date.now();
  timerAlarmShown = false;
  timeLeftSec = timerDurationSec;
  clearAlarm();
  runPanel.classList.remove("show");
  timeBox.classList.add("running");
  timeBox.classList.remove("overtime");
  btnTime.classList.add("timer-stop");
  btnTime.textContent = "停止";
  btnTime.title = "停止并显示完整用时";
  showTimerPhase();
  timerInterval = setInterval(function () { updateTimer(true); }, 1000);
});
```

The replacement must remove `alarmTimer`, the old automatic `stopTimer()` call at zero, and the editor input listener that clears the alarm. The editor input handler must not cancel overtime; only the explicit stop button or a new timer start clears the alarm.

- [ ] **Step 4: Run the pure tests after integration**

Run:

```bash
node --test tests/timer.test.js
```

Expected: all tests remain green.

- [ ] **Step 5: Commit the page integration**

```bash
git add index.html
git commit -m "feat: keep countdown running past zero"
```

### Task 4: 更新功能说明并做浏览器验证

**Files:**
- Modify: `README.md:15`

- [ ] **Step 1: Update the README behavior description**

Replace the current `time` bullet with:

```markdown
- **time**：倒计时（默认 15 分钟，可编辑），运行中醒目显示并可停止；归零后继续负向计时，停止后提示完整用时
```

- [ ] **Step 2: Run automated verification**

Run:

```bash
node --test tests/timer.test.js
node --check timer.js
python3 -m py_compile server.py
git diff --check
```

Expected: all Node tests pass, both syntax checks exit 0, and `git diff --check` reports no whitespace errors.

- [ ] **Step 3: Verify the running state in a browser**

Start the existing local server with `python3 server.py`, open `http://127.0.0.1:8765/index.html`, enter `1` in the minute input, and click `time`. Confirm the input is hidden, the countdown is visible in the emphasized timer box, and the button reads `停止`. Click `停止` before the minute elapses and confirm the bottom panel contains `完整用时`.

- [ ] **Step 4: Verify zero and overtime behavior in a browser**

Start another one-minute timer and let it run for at least 61 seconds. Confirm the display passes through `00:00` and then shows a negative value such as `−00:01`, the timer remains active, and the button still reads `停止`. Click `停止` and confirm the panel contains both `完整用时` and `含超时`.

- [ ] **Step 5: Verify restart behavior**

Start a new timer after stopping. Confirm the old message panel is cleared, the timer returns to a positive countdown, the timer box is no longer red, and the button again reads `停止` until the next stop.

- [ ] **Step 6: Commit the documentation update**

```bash
git add README.md
git commit -m "docs: describe countdown overtime behavior"
```

