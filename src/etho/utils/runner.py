import subprocess
import fabric
from typing import Optional, Union, List
import invoke.exceptions
import logging

logger = logging.getLogger(__name__)


class Runner:
    """Manages remote processes."""

    def __init__(self, host: str, host_is_win: bool = False, host_is_remote: bool = False, python_exe: str = "python"):
        """_summary_

        Args:
            host (str): Host name or IP address of the machine to run the commands on.
            host_is_win (bool, optional): Defaults to False.
            host_is_remote (bool, optional): If False, run commands locallu.
                                             If True, run commands via ssh (fabric).
                                             Defaults to False.
            python_exe (str, optional): _description_. Defaults to "python".
        """
        self.host = host
        self.host_is_win = host_is_win
        self.host_is_remote = host_is_remote
        self.python_exe = python_exe

        host_uname = self.run('uname').stdout.lower()
        os_dct = {'nt': 'win', 'darwin': 'mac', 'linux': 'linux'}
        self.host_os = None
        for uname, os in os_dct.items():
            self.host_os = os if uname in host_uname else self.host_os

        # get host_name for ping
        token = host.split("@")
        if len(token) == 1:  # host_name
            self.user_name = ""
            self.host_name = token[0]
        else:  # user_name@host_name
            self.user_name = token[0]
            self.host_name = token[1]

    def run(
        self,
        cmd: str,
        timeout: Optional[float] = None,
        asynchronous: Optional[bool] = False,
        disown: bool = False,
        run_local: bool = False,
        new_console: bool = False,
    ) -> Union[invoke.runners.Result, invoke.runners.Promise, None]:
        """_summary_

        Args:
            cmd (str): _description_
            timeout (Optional[float], optional): _description_. Defaults to None.
            asynchronous (bool, optional): _description_. Defaults to False.
            disown (bool, optional): _description_. Defaults to False.
            run_local (bool, optional): Run cmd locally. Overrides host_is_remote attribute. Defaults to False.
            new_console (bool, optional): _description_. Defaults to False.

        Returns:
            (asynchronous=False) invoke.runners.Result
            (asynchronous=True) invoke.runners.Promise
            (disown=True or new_console=True if host_is_win) None

        Raises:
            UnexpectedExit, if the command exited nonzero and warn was False.
            Failure, if the command didnt even exit cleanly, e.g. if a StreamWatcher raised WatcherError.
        """
        if disown:  # avoids ValueError(cannot give disown and asynchronous at the same time)
            asynchronous = None

        logging.debug(f"Running {cmd} with the following parameters:")
        logging.debug(
            f"{self.host} with timeout={timeout}, asynchronous={asynchronous}, disown={disown}, run_local={run_local}, new_console={new_console}."
        )
        result = None
        if self.host_is_remote and not run_local:
            shell = (
                "cmd.exe" if self.host_is_win else None
            )  # control shell since powershell and cmd require different separators for commands - cmd.exe wants ";" and fails with "&&"
            result = fabric.Connection(self.host).run(
                cmd, hide=True, timeout=timeout, asynchronous=asynchronous, disown=disown, shell=shell
            )
        else:  # run local process
            if new_console:  # in a new concole window
                result = None
                if self.host_os == 'win':
                    out = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)#, shell=True, stdout=subprocess.PIPE)
                elif self.host_os == 'mac':
                    import appscript
                    appscript.app('Terminal').do_script(cmd)
                else:
                    pass
            else:  # hidden
                result = invoke.run(cmd, hide=True, timeout=timeout, asynchronous=asynchronous, disown=disown)

        return result

    def kill(self, pids: Union[int, List[int]]):
        """Kill process pid."""
        if not isinstance(pids, (list, tuple)):
            pids = list(pids)

        for pid in pids:
            logging.debug(f"Killing process with pid {pid}.")
            self.run(f"kill {pid}", asynchronous=False)

    def kill_python(self):
        """Kill all python processes."""
        logging.debug(f"Killing python processes.")
        if self.host_is_win:
            pids = self.pid(query="python.exe")
            if pids:
                self.kill(pids)
        else:
            self.run("pkill python", remote=True)

    def kill_service(self, service_name):
        pids = self.pid(query=service_name)
        if pids:
            logging.debug(f"Killing service '{service_name}' with pids {pids}.")
            self.kill(pids)

    def pid(self, query: str) -> List[int]:
        """Get pids of all processes partially matching `query`.

        Args:
            query (str): Process cmdline by which process can be recognized.

        Returns:
            List[int]: PIDs matching query
        """

        # get list of running processes on host
        py_code = "import psutil; import pprint; pprint.pprint([{'pid': p.info['pid'], 'cmdline': p.info['cmdline']} for p in psutil.process_iter(attrs=['cmdline', 'pid'])])"
        cmd = f'{self.python_exe} -c "{py_code}"'
        result = self.run(cmd)
        process_list = eval(result.stdout)

        # filter process list
        pids = []
        for process in process_list:
            if process["cmdline"] is not None:
                cmd = " ".join(process["cmdline"])
                if query in cmd and py_code not in cmd:
                    pids.append(process["pid"])

        return pids

    def is_running(self, pids: List[int]) -> bool:
        """Return True if at least one of the pids is in list of running processes."""
        for pid in pids:
            try:
                if self.host_is_win:
                    result = self.run(f"ps -Id {pid}")
                else:
                    result = self.run(f"ps -o pid= -p {pid}")
                if len(result.stdout) > 0:
                    return True
            except invoke.exceptions.UnexpectedExit as e:
                logging.debug(e, exc_info=e)
        return False

    def is_online(self) -> bool:
        """Pings host to see if it is online."""
        params = "-n 1" if self.is_win else "-c 1"  # run only once
        try:
            online = self.run(f"ping {params} {self.host_name}", run_local=True)
        except (invoke.exceptions.Failure, invoke.exceptions.UnexpectedExit) as e:
            logger.debug(e, exc_info=e)
            online = False
        return online


if __name__ == "__main__":
    sr = Runner("ncb@UKME04-13CW", host_is_win=True)
    print(sr.host)
    # sr.kill_python()
    print("starting long running process")
    # cmd = "source ~/.bash_profile;cd ~/;nohup python -m ethoservice.SlpZeroService"
    cmd = "python -c 'import time; time.sleep(100)'"
    sr.run(cmd, disown=True)
    pid = sr.pid(cmd)

    print(f"process pid: {pid}")
    print(f"pid {pid} is running: {sr.is_running(pid)}")
    print(f"killing pid {pid}")
    sr.kill(pid)
    print(f"pid {pid} is running: {sr.is_running(pid)}")
