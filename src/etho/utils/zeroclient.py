import zerorpc
import time
from .runner import Runner
import zmq
import logging
from zmq.log.handlers import PUBHandler
import socket
from .. import config


class ZeroClient(zerorpc.Client):
    def __init__(
        self,
        host: str,
        service_name: str = "CLIENT",
        logging_port: str = "1460",
        serializer: str = "default",
        python_exe: str = "python",
    ):
        """_summary_

        Args:
            host (str): Host name or IP address used for ZeroRPC connections.
            service_name (str, optional): _description_. Defaults to 'CLIENT'.
            logging_port (str, optional): _description_. Defaults to '1460'.
            serializer (str, optional): _description_. Defaults to 'default'.
        """
        self.SERVICE_NAME = service_name
        self.LOGGING_PORT = logging_port

        ctx = zerorpc.Context()
        ctx.register_serializer(serializer)
        super(ZeroClient, self).__init__(timeout=180, heartbeat=90, context=ctx)
        self._init_network_logger()

        self.sr = Runner(host, python_exe=python_exe)
        self.pid = None  # pid of local server process

    def _init_network_logger(self, log_level: int = logging.INFO):
        # TODO: set log levels of logger and handler
        ctx = zmq.Context()
        ctx.LINGER = 0
        pub = ctx.socket(zmq.PUB)
        head_ip = config["name"]  # log to head
        pub.connect("tcp://{0}:{1}".format(head_ip, self.LOGGING_PORT))

        self.log = logging.getLogger()
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

        handler = PUBHandler(pub)
        handler.formatters = formatters
        handler.setLevel(log_level)
        self.log.addHandler(handler)

    def start_server(self, server_name, warmup=2, timeout=5, new_console: bool = False):
        self.log.info(f"   {self.SERVICE_NAME} starting")
        self.sr.run(server_name, timeout=timeout, new_console=new_console, disown=True)
        self.pid = self.sr.pid(query=server_name)
        self.log.info(f"   {self.SERVICE_NAME} warmup")
        time.sleep(warmup)  # wait for server to warm up
        status = self.sr.is_running(self.pid)
        self.log.info(f"   {self.SERVICE_NAME} done")
        return status

    def stop_server(self):
        self.log.info(f"   {self.SERVICE_NAME} finish and cleanup")
        self.finish()
        self.cleanup()
        self.log.info(f"   {self.SERVICE_NAME} killing")
        if self.sr.is_running(self.pid):
            self.sr.kill(self.pid)
        return not self.sr.is_running(self.pid)

    def get_server_pid(self, query):
        return self.sr.pid(query)

    def close(self):
        pass

    def __del__(self):
        self.close()
