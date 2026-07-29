"""Manage the SHIEP-Pipeline VPN helper process."""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .config import PROXY_URL, USE_PROXY, VPN_BINARY


class VpnManager:
    """Start and stop the SHIEP-Pipeline process."""

    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        bind: str = "127.0.0.1:1080",
        binary_path: str = "",
    ):
        self.server = server
        self.username = username
        self.password = password
        self.bind = bind
        self.binary = self._resolve_binary(binary_path)
        self.log_path = Path("data") / "vpn.log"
        self.last_error = ""
        self._recent_lines: list[str] = []
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None

    @staticmethod
    def _resolve_binary(binary_path: str = "") -> Path:
        if binary_path:
            return Path(binary_path)

        candidates = [
            Path.cwd() / VPN_BINARY,
            Path(getattr(sys, "_MEIPASS", Path.cwd())) / VPN_BINARY,
            Path(sys.executable).resolve().parent / VPN_BINARY,
            Path(sys.executable).resolve().parent / "_internal" / VPN_BINARY,
        ]
        return next((path for path in candidates if path.exists()), candidates[0])

    def _log(self, message: str):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        self._recent_lines.append(line)
        self._recent_lines = self._recent_lines[-30:]
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    @staticmethod
    def _free_port(port: str):
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags,
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid.isdigit():
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            creationflags=creationflags,
                        )
        except Exception:
            pass

    def _proxy_port_ready(self) -> bool:
        try:
            host, port = self.bind.rsplit(":", 1)
            with socket.create_connection((host, int(port)), timeout=0.4):
                return True
        except OSError:
            return False

    def _read_output(self):
        if not self._process or not self._process.stdout:
            return
        try:
            for raw_line in self._process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                self._log(f"[VPN] {line}")
                lowered = line.lower()
                if any(token in lowered for token in ("error", "panic", "failed", "denied", "invalid")):
                    self.last_error = line
        except Exception as ex:
            self._log(f"[VPN] output reader stopped: {ex}")

    def start(self, timeout: float = 45) -> bool:
        self.last_error = ""
        self._recent_lines = []
        self._log(f"[VPN] binary: {self.binary}")
        self._log(f"[VPN] bind: {self.bind}")

        if self.is_running():
            self._log("[VPN] process already running")
            return True

        if self._proxy_port_ready():
            self._log("[VPN] proxy port already ready")
            return True

        if not self.binary.exists():
            self.last_error = f"VPN binary not found: {self.binary}"
            self._log(f"[VPN] {self.last_error}")
            return False

        self._free_port(self.bind.split(":")[1])

        cmd = [
            str(self.binary),
            "--server",
            self.server,
            "--username",
            self.username,
            "--bind",
            self.bind,
        ]

        try:
            popen_kwargs = {
                "env": {**os.environ, "SHIEP_PIPELINE_PASSWORD": self.password},
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            }
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                popen_kwargs["startupinfo"] = startupinfo
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            self._process = subprocess.Popen(cmd, **popen_kwargs)
            self._log(f"[VPN] started pid={self._process.pid}")
        except Exception as ex:
            self.last_error = f"failed to start VPN process: {ex}"
            self._log(f"[VPN] {self.last_error}")
            return False

        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._process.poll() is not None:
                self.last_error = self.last_error or f"VPN process exited with code {self._process.returncode}"
                self._log(f"[VPN] {self.last_error}")
                return False
            if self._proxy_port_ready():
                self._log("[VPN] ready")
                return True
            time.sleep(0.25)

        self.last_error = f"VPN startup timed out after {int(timeout)}s"
        self._log(f"[VPN] {self.last_error}")
        self.stop()
        return False

    def stop(self):
        if self._process:
            self._log("[VPN] stopping")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._log("[VPN] stopped")
            self._process = None

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def error_summary(self) -> str:
        return self.last_error or (self._recent_lines[-1] if self._recent_lines else "")

    def get_proxy_url(self) -> str:
        return PROXY_URL if USE_PROXY else ""
