import zerorpc
import abc
import sys
import zmq
import logging
from zmq.log.handlers import PUBHandler
import socket
import time
import os
import subprocess
from ethoservice.utils.common import iswin


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
    LOGGING_PORT = None  # network port used for publishing log messages
    SERVICE_PORT = None  # network port for communicating with the head
    SERVICE_NAME = None

    def __init__(self, *args, serializer: str = 'default', head_ip: str = '192.168.1.1',
                 **kwargs):
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


    @classmethod
    def make(cls, SER, user_name, ip_address, folder_name, python_exe='python', remote=False, port=None):
        import ethomaster.head  # only works on the head node
        if port is None:
            port = cls.SERVICE_PORT

        server_name = '{0} -m {1} {2}'.format(python_exe, cls.__module__, SER)
        print(f'initializing {cls.SERVICE_NAME} at port {port}.')
        service = ethomaster.head.ZeroClient.ZeroClient("{0}@{1}".format(user_name, ip_address), 'piservice', serializer=SER)
        print('   starting server:', end='')
        ret = service.start_server(server_name, folder_name, warmup=1, remote=remote)
        print(f'{"success" if ret else "FAILED"}.')
        print('   connecting to server:', end='')
        ret = service.connect("tcp://{0}:{1}".format(ip_address, port))
        print(f'{"success" if ret else "FAILED"}.')
        return service

    def _init_network_logger(self, head_ip: str = '192.168.1.1', log_level: str = logging.INFO):
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
        pub.connect('tcp://{0}:{1}'.format(head_ip, self.LOGGING_PORT))
        self.log = logging.getLogger()
        self.log.setLevel(log_level)

        # get host name or IP to append to message
        self.hostname = socket.gethostname()

        prefix = "%(asctime)s.%(msecs)03d {0}@{1}:".format(
            self.SERVICE_NAME, self.hostname)
        body = "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
        df = "%Y-%m-%d,%H:%M:%S"
        formatters = {
            logging.DEBUG: logging.Formatter(prefix + body + "\n", datefmt=df),
            logging.INFO: logging.Formatter(prefix + "%(message)s\n", datefmt=df),
            logging.WARN: logging.Formatter(prefix + body + "\n", datefmt=df),
            logging.ERROR: logging.Formatter(prefix + body + " - %(exc_info)s\n", datefmt=df),
            logging.CRITICAL: logging.Formatter(prefix + body + "\n", datefmt=df)}

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
        formatter = logging.Formatter("%(asctime)s.%(msecs)03d {0}@{1}: %(message)s".format(
            self.SERVICE_NAME, self.hostname), datefmt="%Y-%m-%d,%H:%M:%S")
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

    def progress(self):
        if (self._time_elapsed() is None) or (self.duration is None):
            progress = None
        else:
            progress = self._time_elapsed() / self.duration
        return [self._time_elapsed(), self.duration, 'seconds', progress]

    def ping(self):
        self.log.info('pong')
        return "pong"

    def service_start(self, ip_address: str = "tcp://0.0.0.0"):
        """Start service.

        Args:
            ip_address: "tcp://0.0.0.0"
        """
        self.log.warning("starting starting")
        self.bind(ip_address + ":" + self.SERVICE_PORT)
        self.run()
        self.log.warning("   done")

    def service_stop(self):
        """Stop service."""
        self.log.warning("stopping service")
        try:
            self.stop()
        except Exception as e:
            print(e)
        self.log.warning("   done")
        self._flush_loggers()
        self.service_kill()

    def service_kill(self):
        self.log.warning('   kill process {0}'.format(self._getpid()))
        if iswin():
            # run this in subprocess so the function returns - running this via os.system(...) will kill the process but not return
            subprocess.Popen('taskkill /F /PID {0}'.format(self._getpid()))
        else:
            os.system('kill {0}'.format(self._getpid()))

    def _getpid(self):
        return os.getpid()

    def getpid(self):
        return os.getpid()

    def __del__(self):
        self.cleanup()
        self.stop()
        self._flush_loggers()
