#!/usr/bin/env python3
"""草稿（本地版）服务：静态页面、/run 和本地 Git 同步接口。"""
import json
import os
import subprocess
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from git_sync import GitRepository, GitSyncError, GitSyncValidationError

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 15  # 秒
GIT_REPOSITORY = GitRepository(ROOT)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("请求格式错误") from exc
        if not isinstance(payload, dict):
            raise ValueError("请求格式错误")
        return payload

    def do_GET(self):
        if self.path == "/git/status":
            try:
                status = GIT_REPOSITORY.status()
                self._json(200, {"available": True, **status})
            except GitSyncError as exc:
                self._json(503, {"available": False, "error": str(exc)})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/git/push":
            self._git_push()
            return
        if self.path == "/git/pull":
            self._git_pull()
            return
        if self.path != "/run":
            self._json(404, {"error": "not found"})
            return
        try:
            code = self._body_json().get("code", "")
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        if not code.strip():
            self._json(200, {"stdout": "", "stderr": "", "exitCode": 0})
            return
        # 在一次性临时目录里运行，结束后目录自动删除，不留痕迹
        with tempfile.TemporaryDirectory() as td:
            script = os.path.join(td, "main.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write(code)
            try:
                proc = subprocess.run(
                    [sys.executable, script],
                    cwd=td,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT,
                )
                self._json(200, {
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "exitCode": proc.returncode,
                })
            except subprocess.TimeoutExpired:
                self._json(200, {
                    "stdout": "",
                    "stderr": "运行超时（{} 秒），已终止".format(TIMEOUT),
                    "exitCode": -1,
                })
            except Exception as e:
                self._json(500, {"error": str(e)})

    def _git_push(self):
        try:
            payload = self._body_json()
            result = GIT_REPOSITORY.push(payload.get("items"))
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except GitSyncValidationError as exc:
            self._json(400, {"error": str(exc)})
        except GitSyncError as exc:
            self._json(502, {"error": str(exc)})
        else:
            self._json(200, result)

    def _git_pull(self):
        try:
            payload = self._body_json()
            result = GIT_REPOSITORY.pull(payload.get("days", 1))
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except GitSyncError as exc:
            self._json(502, {"error": str(exc)})
        else:
            self._json(200, result)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
