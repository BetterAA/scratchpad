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

    def clone_remote(self):
        other = os.path.join(self.temp.name, "other")
        run_git(self.temp.name, "clone", "--branch", "main", self.remote, other)
        run_git(other, "config", "user.email", "other@example.com")
        run_git(other, "config", "user.name", "Other Editor")
        return other

    def remote_content(self, title):
        return run_git(
            self.remote, "show", "main:" + relative_path_for_title(title),
        ).stdout

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

    def test_push_preserves_remote_updates_when_branches_diverge(self):
        other = self.clone_remote()
        with open(os.path.join(other, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("remote documentation\n")
        run_git(other, "add", "README.md")
        run_git(other, "commit", "-m", "remote documentation")
        GitRepository(other).push([{"title": "远端笔记", "content": "keep remote"}])
        remote_commit = run_git(self.remote, "rev-parse", "main").stdout.strip()

        result = GitRepository(self.root).push([{"title": "本地笔记", "content": "keep local"}])

        self.assertTrue(result["changed"])
        self.assertEqual(self.remote_content("本地笔记"), "keep local")
        self.assertEqual(self.remote_content("远端笔记"), "keep remote")
        self.assertEqual(run_git(self.remote, "show", "main:README.md").stdout, "remote documentation\n")
        run_git(self.root, "merge-base", "--is-ancestor", remote_commit, "HEAD")

    def test_push_uses_submitted_content_for_a_conflicting_title(self):
        repo = GitRepository(self.root)
        repo.push([{"title": "工作记录", "content": "initial\n"}])
        other = self.clone_remote()
        GitRepository(other).push([
            {"title": "工作记录", "content": "remote edit\n"},
            {"title": "远端新增", "content": "preserve"},
        ])

        repo.push([{"title": "工作记录", "content": "local edit\n"}])

        self.assertEqual(self.remote_content("工作记录"), "local edit\n")
        self.assertEqual(self.remote_content("远端新增"), "preserve")
        self.assertEqual(run_git(self.root, "ls-files", "-u").stdout, "")

    def test_same_title_overwrite_does_not_combine_nonconflicting_edits(self):
        repo = GitRepository(self.root)
        seed = "first\nsecond\nthird\nfourth\nfifth\n"
        repo.push([{"title": "工作记录", "content": seed}])
        other = self.clone_remote()
        GitRepository(other).push([
            {"title": "工作记录", "content": seed.replace("first", "remote first")},
        ])
        local_content = seed.replace("fifth", "local fifth")

        repo.push([{"title": "工作记录", "content": local_content}])

        self.assertEqual(self.remote_content("工作记录"), local_content)

    def test_push_retries_if_remote_advances_again_during_sync(self):
        repo = GitRepository(self.root)
        other = self.clone_remote()
        other_repo = GitRepository(other)
        other_repo.push([{"title": "远端笔记", "content": "first remote edit"}])
        real_run = repo._run
        push_attempts = []

        def advance_remote_on_retry(args, **kwargs):
            if args[0] == "push":
                push_attempts.append(args)
                if len(push_attempts) == 2:
                    other_repo.push([{"title": "远端笔记", "content": "second remote edit"}])
            return real_run(args, **kwargs)

        with mock.patch.object(repo, "_run", side_effect=advance_remote_on_retry):
            repo.push([{"title": "本地笔记", "content": "local edit"}])

        self.assertEqual(len(push_attempts), 3)
        self.assertEqual(self.remote_content("远端笔记"), "second remote edit")
        self.assertEqual(self.remote_content("本地笔记"), "local edit")

    def test_conflict_outside_submitted_titles_aborts_and_keeps_both_versions(self):
        other = self.clone_remote()
        for root, content in ((self.root, "local code\n"), (other, "remote code\n")):
            with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as handle:
                handle.write(content)
            run_git(root, "add", "README.md")
            run_git(root, "commit", "-m", "edit documentation")
        run_git(other, "push", "origin", "main")

        with self.assertRaisesRegex(GitSyncError, "README.md"):
            GitRepository(self.root).push([{"title": "本地笔记", "content": "saved locally"}])

        self.assertEqual(run_git(self.root, "show", "HEAD:README.md").stdout, "local code\n")
        self.assertEqual(run_git(self.remote, "show", "main:README.md").stdout, "remote code\n")
        self.assertEqual(run_git(self.root, "show", "HEAD:" + relative_path_for_title("本地笔记")).stdout, "saved locally")
        self.assertEqual(run_git(self.root, "status", "--porcelain", "--untracked-files=no").stdout, "")
        self.assertNotEqual(subprocess.run(
            ["git", "rev-parse", "--verify", "MERGE_HEAD"], cwd=self.root,
            capture_output=True, text=True,
        ).returncode, 0)

    def test_remote_sync_preserves_unrelated_staged_changes(self):
        other = self.clone_remote()
        GitRepository(other).push([{"title": "远端笔记", "content": "remote edit"}])
        with open(os.path.join(self.root, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("uncommitted code\n")
        run_git(self.root, "add", "README.md")

        with self.assertRaisesRegex(GitSyncError, "未提交"):
            GitRepository(self.root).push([{"title": "本地笔记", "content": "local edit"}])

        self.assertEqual(run_git(self.root, "show", ":README.md").stdout, "uncommitted code\n")
        self.assertEqual(run_git(self.root, "show", "HEAD:README.md").stdout, "test\n")
        self.assertEqual(self.remote_content("远端笔记"), "remote edit")

    def test_git_error_keeps_the_cause_before_trailing_hints(self):
        result = subprocess.CompletedProcess(
            ["git", "push"], 1, "",
            "fatal: Authentication failed\nhint: See git help for details.\n",
        )
        with mock.patch("git_sync.subprocess.run", return_value=result):
            with self.assertRaisesRegex(GitSyncError, "Authentication failed"):
                GitRepository(self.root)._run(["push", "origin", "main"])


if __name__ == "__main__":
    unittest.main()
