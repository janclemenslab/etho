import zerorpc
import abc
import sys
import zmq
import logging
from zmq.log.handlers import PUBHandler
import socket
import time
import os

class BaseZeroService(abc.ABC, zerorpc.Server):
    """Allows serving the extending class via zerorpc.

    Abstract base class for all 0services

    Derivations need to change/implement the following properties/methods:
    LOGGING_PORT -
    SERVICE_PORT -
    SERVICE_NAME -
    is_busy -
    cleanup -
    test - test functionality of the class

    Global functionality:
    server_start/server_stop
    progress -
    ping - check if server is alive (response with "pong")
    """

    # TODO: make more robust - add exceptions/try-catch
    LOGGING_PORT = None
    SERVICE_PORT = None
    SERVICE_NAME = None

    def __init__(self, *args, serializer='default', **kwargs):
        self._serializer = serializer
        ctx = zerorpc.Context()
        ctx.register_serializer(serializer)
        super(BaseZeroService, self).__init__(*args, **kwargs, heartbeat=120, context=ctx)
        self._init_network_logger()

        self._time_started = None
        self.duration = None

        self.MOVEFILES_ON_FINISH = False
        self.targetpath = '/home/ncb/remote/'

    def _init_network_logger(self):
        ctx = zmq.Context()
        ctx.LINGER = 0
        pub = ctx.socket(zmq.PUB)
        head_ip = '192.168.1.2'   # FIXME: this shold come from config
        pub.connect('tcp://{0}:{1}'.format(head_ip, self.LOGGING_PORT))
        self.log = logging.getLogger()
        self.log.setLevel(logging.DEBUG)

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
        handler.setLevel(logging.WARNING)  # catch only important messages
        handler.formatters = formatters
        self.log.addHandler(handler)
        # log to local file - init empty
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
        for handler in self.log.handlers:
            handler.flush()

    def _movefiles(self, sourcepaths, targetpath):
        """move files of rpi - usually called during `finish`"""

        self.log.error(sourcepaths)
        self.log.error(targetpath)

        # mount remote
        # CHECK FOR .REMOTE.TXT - if not there try - mount
        if ~os.path.isfile('/home/ncb/remote/.REMOTE.TXT'):
            try:
                self.log.error("echo 'droso123' | sshfs ncb@192.168.1.2:data /home/ncb/remote -o password_stdin")
                self.log.error(os.system("echo 'droso123' | sshfs ncb@192.168.1.2:data /home/ncb/remote -o password_stdin"))
            except Exception as e:
                print(e)
                self.log.error(e)

        if os.path.isfile('/home/ncb/remote/.REMOTE.TXT'):
            for source in sourcepaths:
                # THIS IS TERRIBLE - probably should be a parameter:
                targetdir = os.path.split(os.path.split(source)[0])[1]
                # make this a separate function
                try:
                    self.log.warning("moving {0} to {1}".format(source, targetpath))
                    # rsync move files
                    try:
                        self.log.error("rsync -avhz --remove-source-files {0} /home/ncb/remote/{1}/".format(source, targetdir))
                        self.log.error(os.system("rsync -avhz --remove-source-files {0} /home/ncb/remote/{1}/".format(source, targetdir)))
                    except Exception as e:
                        self.log.error(e)

                    self.log.warning("done moving {0} to {1}".format(source, targetpath))
                except Exception as e:  # TODO: catch specific exception!
                    self.log.error(e)
        else:
            self.log.warning('remote not mounted - skipping.')

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

    def service_start(self, ip_address="tcp://0.0.0.0"):
        self.log.warning("starting starting")
        self.bind(ip_address + ":" + self.SERVICE_PORT)
        self.run()
        self.log.warning("   done")

    def service_stop(self):
        self.log.warning("stopping service")
        try:
            sys.exit(0)  # raises an exception so the finally clause is executed
        except Exception as e:
            pass
        finally:
            try:
                self.stop()
            except Exception as e:
                print(e)
            self.log.warning("   done")
            self._flush_loggers()
            self.service_kill()

    def service_kill(self):
        self.log.warning('   kill process {0}'.format(self._getpid()))
        # os.kill(os.getpid())  # DOES NOT WORK - WHY?
        os.system('kill {0}'.format(self._getpid()))

    def _getpid(self):
        return os.getpid()

    def __del__(self):
        self.cleanup()
        self.stop()
        self._flush_loggers()
