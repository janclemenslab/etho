import json
import logging
import platform
import subprocess
from typing import List, Optional, Union

import psutil

logger = logging.getLogger(__name__)


class Runner:
    """Manages local processes."""

    def __init__(self, host: str = "localhost", python_exe: str = "python"):
        self.host = host
        self.python_exe = python_exe

        system = platform.system().lower()
        if system.startswith("win"):
            self.host_os = "win"
        elif system == "darwin":
            self.host_os = "mac"
        else:
            self.host_os = system or "unknown"

    def run(
        self,
        cmd: str,
        timeout: Optional[float] = None,
        asynchronous: Optional[bool] = False,
        disown: bool = False,
        new_console: bool = False,
    ) -> Union[subprocess.CompletedProcess, subprocess.Popen, None]:
        """Run a command on the local machine."""
        logging.debug(
            f"Running {cmd} with timeout={timeout}, asynchronous={asynchronous}, disown={disown}, new_console={new_console}."
        )

        if new_console:
            if self.host_os == "win":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif self.host_os == "mac":
                script = f'tell application "Terminal" to do script {json.dumps(cmd)}'
                subprocess.Popen(["osascript", "-e", script])
            else:
                subprocess.Popen(cmd, shell=True, start_new_session=True)
            return None

        if disown:
            subprocess.Popen(
                cmd,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return None

        if asynchronous:
            return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        return result

    def kill(self, pids: Union[int, List[int]]):
        """Kill process pid."""
        if pids is None:
            return
        if isinstance(pids, int):
            pids = [pids]

        for pid in pids:
            logging.debug(f"Killing process with pid {pid}.")
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass

    def kill_python(self):
        """Kill all local python processes matching the runner's python executable name."""
        logging.debug("Killing python processes.")
        query = "python.exe" if self.host_os == "win" else "python"
        pids = self.pid(query=query)
        if pids:
            self.kill(pids)

    def kill_service(self, service_name):
        pids = self.pid(query=service_name)
        if pids:
            logging.debug(f"Killing service '{service_name}' with pids {pids}.")
            self.kill(pids)

    def pid(self, query: str) -> List[int]:
        """Get pids of all local processes partially matching `query`."""
        pids = []
        for process in psutil.process_iter(attrs=["cmdline", "pid"]):
            cmdline = process.info["cmdline"]
            if cmdline is None:
                continue
            cmd = " ".join(cmdline)
            if query in cmd:
                pids.append(process.info["pid"])
        return pids

    def is_running(self, pids: List[int]) -> bool:
        """Return True if at least one of the pids is running."""
        return any(psutil.pid_exists(pid) for pid in pids)

    def is_online(self) -> bool:
        """Return True if the configured host responds to ping."""
        params = "-n 1" if self.host_os == "win" else "-c 1"
        try:
            self.run(f"ping {params} {self.host}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.debug(e, exc_info=e)
            return False
        return True
