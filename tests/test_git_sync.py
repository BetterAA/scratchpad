import datetime as dt
import os
import subprocess
import tempfile
import unittest
from unittest import mock

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
        self.assertEqual(
            recent_cutoff(2, now),
            dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.timezone.utc),
        )


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
        local_text = run_git(
            self.root, "show", "main:.scratchpad-content/工作记录.txt"
        ).stdout
        self.assertEqual(local_text, "latest")
        pulled = repo.pull(1)
        self.assertEqual(pulled["items"][0]["content"], "latest")

    def test_push_rejects_invalid_item_before_writing(self):
        repo = GitRepository(self.root)
        with self.assertRaises(GitSyncError):
            repo.push([{"title": "bad/name", "content": "unsafe"}])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".scratchpad-content")))

    def test_remote_git_commands_allow_slow_credentials_and_network(self):
        completed = subprocess.CompletedProcess([], 0, "", "")
        for args, expected_timeout in (
            (["push", "origin", "main"], 120),
            (["pull", "--ff-only", "origin", "main"], 120),
            (["fetch", "origin"], 120),
            (["rev-parse", "HEAD"], 30),
            (["rev-parse", "--verify", "pull"], 30),
        ):
            with self.subTest(args=args):
                with mock.patch("git_sync.subprocess.run", return_value=completed) as run:
                    GitRepository(self.root)._run(args)
                self.assertEqual(run.call_args[1]["timeout"], expected_timeout)

    def test_timeout_messages_distinguish_remote_and_local_commands(self):
        for command in ("push", "pull", "fetch", "log"):
            with self.subTest(command=command):
                error = subprocess.TimeoutExpired(["git", command], 120)
                with mock.patch("git_sync.subprocess.run", side_effect=error):
                    with self.assertRaises(GitSyncError) as raised:
                        GitRepository(self.root, timeout=120)._run([command])
                message = str(raised.exception)
                if command == "log":
                    self.assertEqual(message, "Git 操作超时")
                else:
                    self.assertIn("Git 远端操作超时（120 秒）", message)
                    self.assertIn("网络或 Git 登录状态", message)

    def test_retry_push_uploads_local_commit_after_a_network_timeout(self):
        repo = GitRepository(self.root)
        items = [{"title": "工作记录", "content": "saved before timeout"}]
        original_run = subprocess.run

        def timeout_on_push(command, **kwargs):
            if command[1] == "push":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return original_run(command, **kwargs)

        with mock.patch("git_sync.subprocess.run", side_effect=timeout_on_push):
            with self.assertRaises(GitSyncError):
                repo.push(items)

        local_commit = run_git(self.root, "rev-parse", "HEAD").stdout
        self.assertNotEqual(
            run_git(self.remote, "rev-parse", "main").stdout, local_commit,
        )
        repo.push(items)
        self.assertEqual(
            run_git(self.remote, "rev-parse", "main").stdout, local_commit,
        )
        self.assertEqual(
            run_git(self.remote, "show", "main:.scratchpad-content/工作记录.txt").stdout,
            items[0]["content"],
        )

    def test_push_retries_pending_commit_when_content_unchanged(self):
        repo = GitRepository(self.root)
        repo.push([{"title": "笔记", "content": "v1"}])

        # 模拟推送失败：远端暂时不可用，提交只保存在本地
        broken = os.path.join(self.temp.name, "broken.git")
        os.rename(self.remote, broken)
        with self.assertRaises(GitSyncError):
            repo.push([{"title": "笔记", "content": "v2"}])
        os.rename(broken, self.remote)

        # 内容无新变化时重试，应把滞留的本地提交补推到远端
        result = repo.push([{"title": "笔记", "content": "v2"}])
        self.assertFalse(result["changed"])
        self.assertEqual(result["pushed"], 1)
        remote_text = run_git(
            self.remote, "show", "main:.scratchpad-content/笔记.txt"
        ).stdout
        self.assertEqual(remote_text, "v2")

    def test_push_without_changes_and_without_pending_commits(self):
        repo = GitRepository(self.root)
        repo.push([{"title": "笔记", "content": "v1"}])
        result = repo.push([{"title": "笔记", "content": "v1"}])
        self.assertEqual(
            result, {"changed": False, "count": 0, "commit": "", "pushed": 0}
        )


if __name__ == "__main__":
    unittest.main()
