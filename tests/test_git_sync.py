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


if __name__ == "__main__":
    unittest.main()
