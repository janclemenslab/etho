import zerorpc
import time
from ethomaster.utils.SSHRunner import SSHRunner, is_win
import zmq
import logging
from zmq.log.handlers import PUBHandler
import socket
from ethomaster import config
import subprocess

class ZeroClient(zerorpc.Client):

    def __init__(self, ssh_address, service_name='CLIENT', logging_port='1460', serializer='default'):
        self.SERVICE_NAME = service_name
        self.LOGGING_PORT = logging_port

        ctx = zerorpc.Context()
        ctx.register_serializer(serializer)
        super(ZeroClient, self).__init__(timeout=180, heartbeat=90, context=ctx)
        self._init_network_logger()
        # for interacting with server process
        self.sr = SSHRunner(ssh_address)
        self.pid = None   # pid of server process on remote machine

    def _init_network_logger(self):
        ctx = zmq.Context()
        ctx.LINGER = 0
        pub = ctx.socket(zmq.PUB)
        head_ip = config['HEAD']['name']
        pub.connect('tcp://{0}:{1}'.format(head_ip, self.LOGGING_PORT))

        self.log = logging.getLogger()
        self.log.setLevel(logging.INFO)

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

        handler = PUBHandler(pub)
        handler.formatters = formatters
        handler.setLevel(logging.INFO)
        self.log.addHandler(handler)

    def start_server(self, server_name, folder_name='.', warmup=2, timeout=5):
        self.log.info(f'   {self.SERVICE_NAME} starting')
        if is_win():
            popen = subprocess.Popen(server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.pid = popen.pid
            status = 'unknown'
        else:
            cmd = "source ~/.bash_profile;cd {0};nohup {1}".format(
                folder_name, server_name)
            self.pid = self.sr.run_and_get_pid(cmd, timeout=timeout)
            self.log.info(f'   {self.SERVICE_NAME} warmup')
            time.sleep(warmup)  # wait for server to warm up
            status = self.is_running_server()
        self.log.info(f'   {self.SERVICE_NAME} done')
        return status

    def stop_server(self):
        self.log.info(f'   {self.SERVICE_NAME} finish and cleanup')
        self.finish()
        self.cleanup()
        self.log.info(f'   {self.SERVICE_NAME} killing')
        if self.is_running_server():
            self.sr.kill(self.pid)
        return not self.is_running_server()

    def get_server_pid(self, query, folder_name, timeout=5):
        # get PID for server of type "query"
        return self.sr.get_pid(query)
        # TEST: or maybe just self._pid() ??

    def is_running_server(self):
        return self.sr.is_running(self.pid)

    def close(self):
        pass

    def __del__(self):
        self.close()
