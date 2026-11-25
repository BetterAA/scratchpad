#!/usr/bin/env python3
"""Git synchronization for Scratchpad editor content."""

import datetime as dt
import os
import subprocess
import tempfile
import threading


SYNC_DIR = ".scratchpad-content"
DEFAULT_DAYS = 1
MIN_DAYS = 1
MAX_DAYS = 3650
GIT_TIMEOUT = 30
GIT_NETWORK_TIMEOUT = 120
REMOTE_GIT_COMMANDS = frozenset(("fetch", "pull", "push"))
MAX_PUSH_ATTEMPTS = 3
SYNC_COMMIT_MESSAGE = "scratchpad: sync editor content"


class GitSyncError(RuntimeError):
    """Raised when Git synchronization cannot complete."""


class GitSyncValidationError(GitSyncError):
    """Raised when the browser sends invalid synchronization content."""


def validate_title(value):
    if not isinstance(value, str):
        raise ValueError("标题必须是文本")
    title = value.strip()
    if not title:
        raise ValueError("标题不能为空")
    if title in (".", ".."):
        raise ValueError("标题不能是路径名")
    if "/" in title or "\\" in title or "\x00" in title:
        raise ValueError("标题不能包含斜杠")
    if any(ord(char) < 32 or ord(char) == 127 for char in title):
        raise ValueError("标题包含不可用字符")
    return title


def relative_path_for_title(value):
    return os.path.join(SYNC_DIR, validate_title(value) + ".txt")


def title_from_relative_path(path):
    normalized = str(path).replace("\\", "/")
    prefix = SYNC_DIR + "/"
    if not normalized.startswith(prefix) or not normalized.endswith(".txt"):
        raise ValueError("同步目录存在非法文件名")
    return validate_title(normalized[len(prefix):-4])


def normalize_items(items):
    if not isinstance(items, list):
        raise ValueError("items 必须是数组")
    normalized = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("同步内容格式不正确")
        title = validate_title(item.get("title"))
        content = item.get("content", "")
        if not isinstance(content, str):
            raise ValueError("内容必须是文本")
        normalized[title] = content
    return [{"title": title, "content": content} for title, content in normalized.items()]


def parse_days(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = DEFAULT_DAYS
    return max(MIN_DAYS, min(MAX_DAYS, days))


def _as_utc(value):
    if value is None:
        value = dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def recent_cutoff(days, now=None):
    return _as_utc(now) - dt.timedelta(days=parse_days(days))


def _parse_commit_time(value):
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _as_utc(dt.datetime.fromisoformat(text))
    except ValueError as exc:
        raise GitSyncError("Git 提交时间格式不正确") from exc


def _git_error_detail(result):
    return "\n".join(
        output.strip() for output in (result.stderr, result.stdout) if output.strip()
    ) or "Git 操作失败"


class GitRepository:
    def __init__(self, root, now=None, timeout=GIT_TIMEOUT):
        self.root = os.path.abspath(root)
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.timeout = timeout
        self._lock = threading.Lock()

    def _run(self, args, check=True):
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        is_remote = bool(args) and str(args[0]) in REMOTE_GIT_COMMANDS
        timeout = GIT_NETWORK_TIMEOUT if is_remote else self.timeout
        try:
            result = subprocess.run(
                ["git"] + [str(arg) for arg in args],
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise GitSyncError("找不到 Git 命令") from exc
        except subprocess.TimeoutExpired as exc:
            if is_remote:
                raise GitSyncError(
                    "Git 远端操作超时（{} 秒），请检查网络或 Git 登录状态".format(timeout)
                ) from exc
            raise GitSyncError("Git 操作超时") from exc

        if check and result.returncode != 0:
            raise GitSyncError(_git_error_detail(result))
        return result

    def status(self):
        try:
            branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        except GitSyncError as exc:
            raise GitSyncError("当前目录不是可用的 Git 仓库") from exc
        if not branch or branch == "HEAD":
            raise GitSyncError("当前 Git 仓库处于 detached HEAD")
        try:
            remote = self._run(["remote", "get-url", "origin"]).stdout.strip()
        except GitSyncError as exc:
            raise GitSyncError("当前仓库没有配置 origin 远端") from exc
        if not remote:
            raise GitSyncError("当前仓库没有配置 origin 远端")
        return {"branch": branch, "remote": remote}

    def _ahead_count(self, branch):
        """Return how many local commits are not on origin yet."""
        try:
            result = self._run([
                "rev-list", "--count", "origin/{0}..{0}".format(branch)
            ])
        except GitSyncError:
            return 0
        try:
            return int(result.stdout.strip() or "0")
        except ValueError:
            return 0

    def _merge_in_progress(self):
        return self._run([
            "rev-parse", "--verify", "--quiet", "MERGE_HEAD"
        ], check=False).returncode == 0

    def _write_items(self, items):
        paths = []
        sync_directory = os.path.join(self.root, SYNC_DIR)
        if os.path.islink(sync_directory):
            raise GitSyncError("同步目录不能是符号链接")
        try:
            os.makedirs(sync_directory, exist_ok=True)
            for item in items:
                relative_path = relative_path_for_title(item["title"])
                absolute_path = os.path.join(self.root, relative_path)
                temporary_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8", newline="", delete=False,
                        dir=sync_directory, prefix=".scratchpad-write-",
                    ) as handle:
                        temporary_path = handle.name
                        handle.write(item["content"])
                    # 替换目录项，避免跟随同标题的符号链接或修改硬链接目标。
                    os.replace(temporary_path, absolute_path)
                finally:
                    if temporary_path and os.path.exists(temporary_path):
                        os.unlink(temporary_path)
                paths.append(relative_path)
        except (OSError, ValueError) as exc:
            raise GitSyncError("无法写入同步内容：{}".format(exc)) from exc
        return paths

    def _sync_remote(self, branch, items):
        if self._run(["status", "--porcelain", "--untracked-files=no"]).stdout.strip():
            raise GitSyncError("本地还有未提交的其他改动，请先保存这些改动后重试")
        self._run(["fetch", "origin", branch])
        remote_commit = self._run(["rev-parse", "FETCH_HEAD"]).stdout.strip()
        paths = {relative_path_for_title(item["title"]) for item in items}
        try:
            # 标题按文件路径识别；resolve 不会把旧标题的改动传播到重命名后的其他标题。
            result = self._run([
                "merge", "--strategy=resolve", "--no-ff", "--no-commit",
                "--no-edit", remote_commit
            ], check=False)
            if not self._merge_in_progress():
                if result.returncode:
                    raise GitSyncError(_git_error_detail(result))
                return
            conflicts = set(filter(None, self._run([
                "diff", "--name-only", "--diff-filter=U", "-z"
            ]).stdout.split("\0")))
            outside_titles = sorted(conflicts - paths)
            if outside_titles:
                raise GitSyncError(
                    "远端更新与本地其他文件冲突，请先处理这些文件后重试：{}".format(
                        "、".join(outside_titles)
                    )
                )
            # 同标题始终使用本次提交的完整文本，包括 Git 能自动合并的情况。
            written_paths = self._write_items(items)
            self._run(["add", "--"] + written_paths)
            self._run(["commit", "--no-edit"])
        except GitSyncError as exc:
            if self._merge_in_progress():
                try:
                    self._run(["merge", "--abort"])
                except GitSyncError as cleanup_error:
                    raise GitSyncError(
                        "自动合并失败：{}\n撤销合并也失败：{}\n"
                        "本地改动已保留，仓库仍有未完成的合并，"
                        "请先检查并处理合并状态后重试。".format(exc, cleanup_error)
                    ) from exc
            raise

    def _push_branch(self, branch, items):
        synced = False
        try:
            for attempt in range(MAX_PUSH_ATTEMPTS):
                result = self._run(["push", "--porcelain", "origin", branch], check=False)
                if result.returncode == 0:
                    return synced
                detail = _git_error_detail(result)
                if "(non-fast-forward)" not in detail and "(fetch first)" not in detail:
                    raise GitSyncError(detail)
                if attempt == MAX_PUSH_ATTEMPTS - 1:
                    raise GitSyncError("远端在推送期间持续更新，请稍后重试")
                self._sync_remote(branch, items)
                synced = True
        except GitSyncError as exc:
            raise GitSyncError(
                "提交已保存在本地，但推送远端失败：{}".format(exc)
            ) from exc

    def push(self, items):
        with self._lock:
            return self._push(items)

    def _push(self, items):
        try:
            normalized = normalize_items(items)
        except ValueError as exc:
            raise GitSyncValidationError(str(exc)) from exc
        if not normalized:
            raise GitSyncError("没有可推送的内容")

        repository = self.status()
        branch = repository["branch"]
        if self._merge_in_progress():
            raise GitSyncError("仓库有尚未完成的合并，请先完成或取消合并后重试")
        paths = self._write_items(normalized)

        changed = self._run(["status", "--porcelain", "--"] + paths).stdout.strip()
        ahead = self._ahead_count(branch)
        if changed:
            self._run(["add", "--"] + paths)
            self._run([
                "commit", "--only", "-m", SYNC_COMMIT_MESSAGE, "--"
            ] + paths)
        # 总是执行推送：内容无变化时，把上次失败滞留的本地提交补推上去
        synced = self._push_branch(branch, normalized)
        changed = bool(changed or synced)
        commit = self._run(["rev-parse", "--short", "HEAD"]).stdout.strip()
        if not changed:
            return {
                "changed": False, "count": 0,
                "commit": commit if ahead else "", "pushed": ahead,
            }
        return {"changed": True, "count": len(paths), "commit": commit, "pushed": 0}

    def pull(self, days=DEFAULT_DAYS):
        with self._lock:
            return self._pull(days)

    def _pull(self, days=DEFAULT_DAYS):
        repository = self.status()
        normalized_days = parse_days(days)
        self._run(["pull", "--ff-only", "origin", repository["branch"]])
        paths = self._run([
            "-c", "core.quotePath=false", "ls-files", "--", SYNC_DIR + "/*.txt"
        ]).stdout.splitlines()
        cutoff = recent_cutoff(normalized_days, self.now())
        items = []

        for relative_path in paths:
            relative_path = relative_path.strip()
            if not relative_path:
                continue
            try:
                title = title_from_relative_path(relative_path)
            except ValueError as exc:
                raise GitSyncError(str(exc)) from exc
            committed_at = self._run([
                "log", "-1", "--format=%cI", "--", relative_path
            ]).stdout.strip()
            if not committed_at or _parse_commit_time(committed_at) < cutoff:
                continue
            absolute_path = os.path.join(self.root, relative_path)
            try:
                with open(absolute_path, "r", encoding="utf-8") as handle:
                    content = handle.read()
            except OSError as exc:
                raise GitSyncError("无法读取同步内容：{}".format(exc)) from exc
            items.append({
                "title": title,
                "content": content,
                "committedAt": committed_at,
            })

        return {"days": normalized_days, "items": items}

