import zerorpc
import abc
import zmq
import logging
from zmq.log.handlers import PUBHandler
import socket
import time
import os
import subprocess
from typing import Optional
import sys
import signal
import psutil


class BaseZeroService(abc.ABC, zerorpc.Server):
    """Define abstract base class for all 0services.

    Derivations need to change/implement the following properties/methods:
    LOGGING_PORT: network port for publishing log messages
    SERVICE_PORT: network port for communication with the head
    SERVICE_NAME: unique, three-letter identifier for the service
    is_busy: indicates whether service is running (True/False)
    cleanup: called when finishing/shutting down the service serviceease hardware, close files etc
    test - test functionality of the class (?)

    Optional:
    setup
    start

    Global functionality:
    server_start/server_stop
    progress -
    ping - check if server is alive (response with "pong")
    init_local_logger(self, logfilename)

    """

    # TODO: make more robust - add exceptions/try-catch
    LOGGING_PORT: Optional[int] = None  # network port used for publishing log messages
    SERVICE_PORT: Optional[int] = None  # network port for communicating with the head
    SERVICE_NAME: Optional[str] = None

    def __init__(self, *args, serializer: str = "default", head_ip: str = "192.168.1.1", **kwargs):
        """[summary]

        Args:
            serializer (str, optional): [description]. Defaults to 'default'.
            head_ip (str, optional): [description]. Defaults to '192.168.1.1'.
            logging_port (int, optional): [description]. Defaults to None.
            service_port (int, optional): [description]. Defaults to None.
        """
        self._serializer = serializer
        ctx = zerorpc.Context()
        ctx.register_serializer(self._serializer)
        super(BaseZeroService, self).__init__(*args, **kwargs, heartbeat=120, context=ctx)

        self._init_network_logger(head_ip)

        self._time_started = None
        self.duration = None
        self.prev_elapsed = 0
        self.info = dict()

    @classmethod
    def make(
        cls,
        serializer,
        user,
        host,
        folder_name,
        python_exe="python",
        host_is_remote: bool = False,
        host_is_win: bool = True,
        port=None,
        new_console: bool = False,
        run_local: bool = False,
    ):
        from ..utils.zeroclient import ZeroClient  # only works on the head node

        if port is None:
            port = cls.SERVICE_PORT

        server_name = f"{python_exe} -m {cls.__module__} {serializer} {port}"
        logging.debug(f"initializing {cls.SERVICE_NAME} at port {port}.")
        service = ZeroClient(
            "{0}@{1}".format(user, host),
            service_name=cls.__module__,
            serializer=serializer,
            host_is_remote=host_is_remote,
            host_is_win=host_is_win,
            python_exe=python_exe,
        )
        logging.debug("   starting server:", end="")
        ret = service.start_server(server_name, folder_name, warmup=1, new_console=new_console, run_local=run_local)
        logging.debug(f'{"success" if ret else "FAILED"}.')
        logging.debug("   connecting to server:", end="")

        ret = service.connect("tcp://{0}:{1}".format(host, port))
        logging.debug(f'{"success" if ret else "FAILED"}.')
        return service

    def _init_network_logger(self, head_ip: str = "192.168.1.1", log_level: int = logging.INFO):
        """Initialize logger that publishes messages over the network format.

        For live display of messages on head node (see ethomaster.head.headlogger).
        Args:
            head_ip: IP address to publish to (defaults to '192.168.1.1')
            lob_level: (defaults to logging.INFO)
        """

        # setup connection - publish to head_ip via LOGGIN_PORT
        ctx = zmq.Context()
        ctx.LINGER = 0
        pub = ctx.socket(zmq.PUB)
        pub.connect("tcp://{0}:{1}".format(head_ip, self.LOGGING_PORT))
        self.log = logging.getLogger((__name__))
        self.log.setLevel(log_level)

        # get host name or IP to append to message
        self.hostname = socket.gethostname()

        prefix = "%(asctime)s.%(msecs)03d {0}@{1}:".format(self.SERVICE_NAME, self.hostname)
        body = "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
        df = "%Y-%m-%d,%H:%M:%S"
        formatters = {
            logging.DEBUG: logging.Formatter(prefix + body + "\n", datefmt=df),
            logging.INFO: logging.Formatter(prefix + "%(message)s\n", datefmt=df),
            logging.WARN: logging.Formatter(prefix + body + "\n", datefmt=df),
            logging.ERROR: logging.Formatter(prefix + body + " - %(exc_info)s\n", datefmt=df),
            logging.CRITICAL: logging.Formatter(prefix + body + "\n", datefmt=df),
        }

        # setup log handler which publishe all log messages to the network
        handler = PUBHandler(pub)
        handler.setLevel(log_level)  # catch only important messages
        handler.formatters = formatters
        self.log.addHandler(handler)

        # initialize attributes for log to local file (should be in __init__)
        self.logfilename = None
        self.filelogger = None

    @abc.abstractmethod
    def is_busy(self):  # returns bool
        """return state of the instance - IDLE, BUSY, FAILED, etc"""

    @abc.abstractmethod
    def test(self):  # returns bool
        """test whether the instance will be functional"""

    @abc.abstractmethod
    def cleanup(self):  # returns bool
        """free resources"""

    def init_local_logger(self, logfilename):
        """log locally to LOGFILENAME"""
        self.logfilename = logfilename
        if self.filelogger is not None:
            # remove old handler
            self.log.removeHandler(self.filelogger)

        # create a file handler
        os.makedirs(os.path.dirname(self.logfilename), exist_ok=True)
        self.filelogger = logging.FileHandler(self.logfilename)
        self.filelogger.setLevel(logging.INFO)  # catch all messages

        # create a logging format
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d {0}@{1}: %(message)s".format(self.SERVICE_NAME, self.hostname), datefmt="%Y-%m-%d,%H:%M:%S"
        )
        self.filelogger.setFormatter(formatter)
        # add the handlers to the logger
        self.log.addHandler(self.filelogger)

    def _flush_loggers(self):
        """Make sure all log messages are sent/saved."""
        for handler in self.log.handlers:
            handler.flush()

    def _time_elapsed(self):
        if self._time_started is None:
            time_elapsed = None
        else:
            time_elapsed = time.time() - self._time_started
        return time_elapsed

    def attr(self, name: str):
        # 0rpc only exposes functions - can't access attributes directly
        # so we wrap attribute access in a function
        return self.__getattribute__(name)

    def information(self):
        """Information to display about the

        should be Dict[str, Dict[str, Any]]
        should be Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]]
        should be Dict[str, pd.DataFrame]

        Print to terminal with `ethoservice.utils.tui.rich_information`.
        """
        return self.info

    def progress(self):
        try:
            elapsed = self._time_elapsed()
            p = {
                "total": self.duration,
                "elapsed": elapsed,
                "elapsed_delta": elapsed - self.prev_elapsed,
                "elapsed_units": "seconds",
            }
            self.prev_elapsed = elapsed
            return p
        except:
            pass

    def ping(self):
        self.log.info("pong")
        return "pong"

    def service_start(self, ip_address: str = "tcp://0.0.0.0"):
        """Start service.

        Args:
            ip_address: "tcp://0.0.0.0"
        """
        self.log.warning("starting")
        self.bind(f"{ip_address}:{self.SERVICE_PORT}")
        self.run()
        self.log.warning("   done")

    def service_stop(self):
        """Stop service."""
        self.log.warning("stopping service")
        try:
            self.stop()
        except Exception as e:
            self.log.debug("stopnot", exc_info=e)
        self.log.warning("   done")
        self._flush_loggers()
        self.service_kill()

    def service_kill(self):
        self.log.warning("   kill process {0}".format(self.getpid()))
        iswin = sys.platform == "win32"
        if iswin:
            # run this in subprocess so the function returns - running this via os.system(...) will kill the process but not return
            subprocess.Popen(f"taskkill /F /PID {self.getpid()}")
        else:
            os.system(f"pkill -TERM -P {self.getpid()}")

    def kill(self):
        os.kill(self.pid, signal.SIGKILL)

    def kill_children(self):
        try:
            parent = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            return
        children = parent.children(recursive=True)
        for p in children:
            os.kill(p.pid, signal.SIGKILL)


    def _getpid(self):
        return os.getpid()[0]

    def getpid(self):
        return os.getpid()[0]

    @property
    def pid(self):
        return os.getpid()

    @property
    def pgrp(self):
        return os.getpgrp()


    def __del__(self):
        self.cleanup()
        self.stop()
        self._flush_loggers()
