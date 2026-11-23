# Git 内容同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** 为草稿编辑器增加本地 Git 推送和按最近 X 天筛选的 Git 拉取功能，让标题相同的内容覆盖远端和本地。

**Architecture:** 浏览器端用 git-sync.js 处理标题校验、重复标题去重和拉取结果合并；本地 Python 服务用 git_sync.py 封装仓库状态、文件写入、提交、推送和按提交时间筛选。server.py 只负责 HTTP JSON 路由。同步内容保存到 .scratchpad-content/<标题>.txt，GitHub Pages 没有本地服务时两个按钮自动禁用。

**Tech Stack:** 原生 HTML/CSS/JavaScript、Python 3.7+、unittest、Node 内置 node:test、Git CLI。

---

### Task 1: 为浏览器端 Git 合并逻辑建立失败测试

**Files:**
- Create: tests/git-sync.test.js
- Test target: git-sync.js（此时尚未创建）

- [ ] **Step 1: Write the failing tests**

创建 tests/git-sync.test.js，先锁定标题校验、推送去重、拉取覆盖和天数边界：

~~~js
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
~~~

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

~~~bash
node --test tests/git-sync.test.js
~~~

Expected: the test file fails because ../git-sync.js does not exist yet.

- [ ] **Step 3: Commit the failing frontend tests**

~~~bash
git add tests/git-sync.test.js
git commit -m "test: specify browser git sync behavior"
~~~

### Task 2: Implement browser-side Git sync helpers

**Files:**
- Create: git-sync.js
- Test: tests/git-sync.test.js

- [ ] **Step 1: Implement the CommonJS/browser-compatible helper module**

创建 git-sync.js，保留标题 trim 后的值，拒绝路径穿越字符，并让同名标签的后一个内容覆盖前一个：

~~~js
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.GitSync = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function cleanTitle(value) {
    return String(value == null ? "" : value).trim();
  }

  function isUntitled(value) {
    var title = cleanTitle(value);
    return !title || /^草稿\s*\d*$/.test(title) || title === "暂存";
  }

  function titleError(value) {
    var title = cleanTitle(value);
    if (isUntitled(title)) return "请先编辑标题";
    if (title === "." || title === "..") return "标题不能是路径名";
    if (/[\\/\u0000]/.test(title)) return "标题不能包含斜杠";
    for (var i = 0; i < title.length; i++) {
      if (title.charCodeAt(i) < 32 || title.charCodeAt(i) === 127) return "标题包含不可用字符";
    }
    return "";
  }

  function collectPushItems(tabs) {
    var items = [];
    var invalid = [];
    (tabs || []).forEach(function (tab, index) {
      var title = cleanTitle(tab && tab.title);
      var error = titleError(title);
      if (error) {
        invalid.push({ index: index, title: title || "（空标题）", error: error });
        return;
      }
      var item = { title: title, content: String(tab && tab.content || "") };
      var found = false;
      items.forEach(function (existing) {
        if (existing.title === title) {
          existing.content = item.content;
          found = true;
        }
      });
      if (!found) items.push(item);
    });
    return { items: invalid.length ? [] : items, invalid: invalid };
  }

  function mergePulledTabs(tabs, items, makeId) {
    var next = (tabs || []).map(function (tab) {
      return { id: tab.id, title: tab.title, content: tab.content };
    });
    var updated = 0;
    var added = 0;
    (items || []).forEach(function (item) {
      var matched = false;
      next.forEach(function (tab) {
        if (cleanTitle(tab.title) === item.title) {
          tab.content = item.content;
          matched = true;
          updated++;
        }
      });
      if (!matched) {
        next.push({ id: makeId(), title: item.title, content: item.content });
        added++;
      }
    });
    return { tabs: next, updated: updated, added: added };
  }

  function normalizeDays(value) {
    var days = parseInt(value, 10);
    if (!days || days < 1) days = 1;
    if (days > 3650) days = 3650;
    return days;
  }

  return {
    collectPushItems: collectPushItems,
    isUntitled: isUntitled,
    mergePulledTabs: mergePulledTabs,
    normalizeDays: normalizeDays,
  };
});
~~~

- [ ] **Step 2: Run focused tests and syntax check**

Run:

~~~bash
node --test tests/git-sync.test.js
node --check git-sync.js
~~~

Expected: all five tests pass and the syntax check exits 0.

- [ ] **Step 3: Commit the helper module**

~~~bash
git add git-sync.js tests/git-sync.test.js
git commit -m "feat: add browser git sync helpers"
~~~

### Task 3: Specify the Python Git repository behavior

**Files:**
- Create: tests/test_git_sync.py
- Test target: git_sync.py（此时尚未创建）

- [ ] **Step 1: Write pure helper and local-bare-repository tests**

创建 tests/test_git_sync.py。测试通过临时 bare repository 验证同标题覆盖和拉取筛选，避免只测试 mock：

~~~python
import datetime as dt
import os
import subprocess
import tempfile
import unittest

from git_sync import (
    GitRepository,
    GitSyncError,
    normalize_items,
    parse_days,
    recent_cutoff,
    relative_path_for_title,
    validate_title,
)


def run_git(cwd, *args, env=None):
    return subprocess.run(
        ["git"] + list(args), cwd=cwd, check=True,
        capture_output=True, text=True, env=env,
    )


class GitSyncHelpersTest(unittest.TestCase):
    def test_validate_title_rejects_paths_and_keeps_unicode(self):
        self.assertEqual(validate_title("  工作记录  "), "工作记录")
        self.assertEqual(relative_path_for_title("工作记录"), ".scratchpad-content/工作记录.txt")
        with self.assertRaises(ValueError):
            validate_title("../outside")
        with self.assertRaises(ValueError):
            validate_title("bad/name")

    def test_normalize_items_uses_the_last_duplicate(self):
        self.assertEqual(
            normalize_items([
                {"title": "同名", "content": "old"},
                {"title": "同名", "content": "new"},
            ]),
            [{"title": "同名", "content": "new"}],
        )

    def test_parse_days_and_cutoff(self):
        self.assertEqual(parse_days(None), 1)
        self.assertEqual(parse_days(0), 1)
        self.assertEqual(parse_days(4000), 3650)
        now = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(recent_cutoff(2, now), dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.timezone.utc))


class GitRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.temp.name, "work")
        self.remote = os.path.join(self.temp.name, "remote.git")
        os.makedirs(self.root)
        run_git(self.temp.name, "init", "--bare", self.remote)
        run_git(self.root, "init")
        run_git(self.root, "config", "user.email", "test@example.com")
        run_git(self.root, "config", "user.name", "Git Sync Test")
        run_git(self.root, "branch", "-M", "main")
        run_git(self.root, "remote", "add", "origin", self.remote)
        with open(os.path.join(self.root, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("test\n")
        run_git(self.root, "add", "README.md")
        run_git(self.root, "commit", "-m", "initial")
        run_git(self.root, "push", "origin", "main")

    def tearDown(self):
        self.temp.cleanup()

    def test_push_overwrites_same_title_and_pull_returns_recent_content(self):
        repo = GitRepository(self.root)
        repo.push([{"title": "工作记录", "content": "first"}])
        repo.push([{"title": "工作记录", "content": "latest"}])
        remote_text = run_git(
            self.remote, "show", "main:.scratchpad-content/工作记录.txt"
        ).stdout
        self.assertEqual(remote_text, "latest")
        pulled = repo.pull(1)
        self.assertEqual(pulled["items"][0]["content"], "latest")

    def test_push_rejects_invalid_item_before_writing(self):
        repo = GitRepository(self.root)
        with self.assertRaises(GitSyncError):
            repo.push([{"title": "bad/name", "content": "unsafe"}])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".scratchpad-content")))


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the Python tests and verify RED**

Run:

~~~bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_git_sync.py -v
~~~

Expected: collection fails because git_sync.py does not exist yet.

- [ ] **Step 3: Commit the failing Python tests**

~~~bash
git add tests/test_git_sync.py
git commit -m "test: specify git repository sync behavior"
~~~

### Task 4: Implement the Git repository service

**Files:**
- Create: git_sync.py
- Test: tests/test_git_sync.py

- [ ] **Step 1: Implement validation, date filtering and Git operations**

git_sync.py must provide the imported helpers and a GitRepository with these behaviors:

~~~python
SYNC_DIR = ".scratchpad-content"
DEFAULT_DAYS = 1
MIN_DAYS = 1
MAX_DAYS = 3650
GIT_TIMEOUT = 30

class GitSyncError(RuntimeError):
    pass

def validate_title(value):
    # trim; reject empty, ., .., slash, backslash, NUL and control characters
    # return the trimmed title

def relative_path_for_title(value):
    return os.path.join(SYNC_DIR, validate_title(value) + ".txt")

def normalize_items(items):
    # require a list of {title, content}; validate each title and string content;
    # keep one item per title, with the later item winning

def parse_days(value):
    # parse integer and clamp to [MIN_DAYS, MAX_DAYS], defaulting to 1

def recent_cutoff(days, now=None):
    # return UTC now minus parse_days(days)

class GitRepository:
    def __init__(self, root, now=None, timeout=GIT_TIMEOUT):
        # store absolute root, injected clock, and command timeout

    def status(self):
        # read the current branch and origin URL; reject detached/no-remote repos

    def push(self, items):
        # normalize before writing; write only requested .scratchpad-content paths;
        # stage those exact paths, commit once, push origin/<current branch>;
        # return changed/count/commit and leave unrelated worktree changes alone

    def pull(self, days=DEFAULT_DAYS):
        # git pull --ff-only origin <branch>; list .scratchpad-content/*.txt;
        # use each file's latest %cI commit time and return files newer than cutoff
~~~

Git subprocesses must set GIT_TERMINAL_PROMPT=0, capture stdout/stderr, enforce the timeout, and convert non-zero exit codes into GitSyncError with a short stderr/stdout message. Pull results include title, content, and the ISO commit timestamp.

- [ ] **Step 2: Run the Python tests and syntax check**

Run:

~~~bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_git_sync.py -v
python3 -m py_compile git_sync.py
~~~

Expected: all five tests pass and the module compiles. Restore any tracked __pycache__ file changed by the syntax check before committing.

- [ ] **Step 3: Commit the Git service**

~~~bash
git add git_sync.py tests/test_git_sync.py
git commit -m "feat: add local git repository sync service"
~~~

### Task 5: Add local HTTP routes for Git operations

**Files:**
- Modify: server.py:2-72

- [ ] **Step 1: Add JSON parsing and Git service wiring**

Import GitRepository and GitSyncError, create GIT_REPOSITORY = GitRepository(ROOT), and add:

~~~python
def do_GET(self):
    if self.path == "/git/status":
        try:
            status = GIT_REPOSITORY.status()
            self._json(200, {"available": True, **status})
        except GitSyncError as exc:
            self._json(503, {"available": False, "error": str(exc)})
        return
    super().do_GET()
~~~

Refactor the existing body parsing into _body_json, keep /run behavior unchanged, and route /git/push and /git/pull to GIT_REPOSITORY.push(payload["items"]) and GIT_REPOSITORY.pull(payload.get("days", 1)). Return 400 for invalid JSON or invalid titles, 502 for Git command failures, and JSON success results for no-change and empty-pull cases.

- [ ] **Step 2: Run server syntax and route smoke checks**

Run:

~~~bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile server.py
python3 -c 'import server; print(server.PORT)'
~~~

Expected: exit 0 and output 8765. Restore any tracked cache file after the compile check.

- [ ] **Step 3: Commit the server routes**

~~~bash
git add server.py
git commit -m "feat: expose git sync HTTP routes"
~~~

### Task 6: Add Git controls, title reminder, pull window and local merge behavior

**Files:**
- Modify: index.html:20-230 for styles, toolbar buttons and dialogs
- Modify: index.html:230-706 for capability detection and Git event handlers
- Modify: index.html to load git-sync.js
- Modify: git-sync.js from Task 2

- [ ] **Step 1: Add the toolbar controls and dialogs**

Load <script src="git-sync.js"></script> before the existing inline application script. Add 推送 Git and 拉取 Git buttons beside the existing toolbar actions. Add a push mask with a title list and 确认推送 button, and a pull mask with gitDaysInput (type=number, min=1, max=3650, default 1) and 确认拉取 button. Dialog text must explicitly say that same-title content overwrites the remote or local content.

- [ ] **Step 2: Add Git button styles and state variables**

Add a muted disabled style consistent with the existing buttons and declare btnGitPush, btnGitPull, gitPushMask, gitPullMask, gitDaysInput, gitAvailable, gitBusy, and pendingGitItems. Extend updateButtons() so both Git buttons are disabled when the local service is unavailable or an operation is running.

- [ ] **Step 3: Implement capability detection and push confirmation**

On initialization call GET /git/status. Enable buttons only when the response has available: true; otherwise set their titles to 仅本地版可用. On push click, call GitSync.collectPushItems(state.tabs). If invalid is non-empty, show a message listing each title that needs renaming and do not open the network request. Otherwise populate the confirmation dialog with all unique titles and open it. Recollect the tabs on final confirmation so edits made while the dialog was open are included.

- [ ] **Step 4: Implement push and pull requests**

Add a JSON helper that checks response.ok, extracts {error}, and rejects failed requests. Push sends {items} to /git/push, disables both buttons, then reports the number of files and commit in the message panel. Pull sends {days: GitSync.normalizeDays(gitDaysInput.value)} to /git/pull; on success call GitSync.mergePulledTabs(state.tabs, data.items, uid), update state.tabs, render(), and persist(). Report updated and added counts, close the dialog, and re-enable buttons in finally.

- [ ] **Step 5: Verify the browser UI locally**

Run the local service, open the editor, and verify:

1. On a static server or GitHub Pages, both Git buttons are disabled.
2. With a default title, push opens the title reminder and does not send a request.
3. After renaming two tabs, push creates two .scratchpad-content/*.txt files in one commit.
4. Pushing the same title again changes the same remote file.
5. Pulling with the default 1-day window replaces a matching local tab and appends a new remote tab.
6. Pulling with a larger window includes older pushed content.

- [ ] **Step 6: Commit the UI integration**

~~~bash
git add index.html git-sync.js
git commit -m "feat: add git push and pull controls"
~~~

### Task 7: Update documentation and run the complete verification suite

**Files:**
- Modify: README.md

- [ ] **Step 1: Document the Git sync behavior**

Add the two Git features to the feature list, state that they are available in the local version, document .scratchpad-content/, the default recent-1-day pull window, title requirements, same-title overwrite behavior, and the fact that remote content is stored as ordinary UTF-8 text.

- [ ] **Step 2: Run automated checks**

Run:

~~~bash
node --test tests/timer.test.js tests/git-sync.test.js
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_git_sync.py -v
node --check timer.js
node --check git-sync.js
python3 -m py_compile git_sync.py server.py
git diff --check
~~~

Expected: all JavaScript and Python tests pass, syntax checks exit 0, and no whitespace errors are reported. Restore any tracked __pycache__ file changed by Python compilation.

- [ ] **Step 3: Review the final diff and working tree**

Run:

~~~bash
git diff --stat main...HEAD
git status --short --branch
~~~

Expected: the diff contains only the Git sync implementation, tests, documentation and the design/plan records; the working tree is clean.

- [ ] **Step 4: Commit the documentation**

~~~bash
git add README.md
git commit -m "docs: describe git content sync"
~~~

- [ ] **Step 5: Merge and push the completed feature**

After the merged local `main` passes the complete verification suite, push the updated branch to the configured remote:

~~~bash
git push origin main
git ls-remote origin refs/heads/main
~~~

Expected: the remote `main` ref equals the verified local `main` commit.
