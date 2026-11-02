#!/usr/bin/env python3
"""草稿（本地版）服务：静态页面 + /run 接口（把页面内容作为 Python 脚本在本机运行）"""
import json
import os
import subprocess
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 15  # 秒


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

    def do_POST(self):
        if self.path != "/run":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            code = json.loads(self.rfile.read(length).decode("utf-8")).get("code", "")
        except Exception:
            self._json(400, {"error": "请求格式错误"})
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

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
