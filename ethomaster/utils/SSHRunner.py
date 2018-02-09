import subprocess
import re
import platform
import os
import time
from subprocess import PIPE, Popen
from fabric.api import *

env.hosts = []
env.user = 'ncb'
env.warn_only = True
env.password = 'droso123'


def cmdline(command):
    process = Popen(
        args=command,
        stdout=PIPE,
        shell=True
    )
    return process.communicate()[0]

def is_mac():
    return platform.system().lower() == 'darwin'

def is_win():
    return platform.system().lower() == 'windows'

def is_linux():
    return platform.system().lower() == 'linux'

def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that some hosts may not respond to a ping request even if the host name is valid.
    """
    # Ping parameters as function of OS

    parameters = "-n 1" if is_win() else "-c 1"
    suffix = ">nul 2>&1" if is_win() else ">/dev/null 2>&1"
    # Pinging (">/dev/null 2>&1" supresses output)
    exit_code = os.system(
        "ping {0} {1}{2}".format(parameters, host, suffix))
    # 0=success
    return exit_code == 0


class SSHRunner():
    """manages remote processes

    run
    runbg
    pid(output)
    kill
    ps
    is_running
    """

    def __init__(self, host):
        self.host = host
        token = host.split('@')
        if len(token)==1:  # host_name
            self.user_name = ''
            self.host_name = token[0]
        else:  # user_name@host_name
            self.user_name = token[0]
            self.host_name = token[1]

    def run(self, cmd, timeout=None):
        # `>/dev/null 2>&1` makes sure we return
        # `echo $!` prints pid of spawned process

        prefix = "plink -i C:/Users/ncb/Documents/raspberry.ppk" if is_win() else "ssh -f"

        if is_win():
            cmd = '{0} {1} "{2} >/dev/null 2>&1 & echo $!"'.format(
                prefix, self.host, cmd)
        else:
            cmd = "{0} {1} '{2} >/dev/null 2>&1 & echo $!'".format(
                prefix, self.host, cmd)
        try:
            output = cmdline(cmd)
            # universal_newlines=True so output is string and not byte
            # output = subprocess.check_output(
            #     cmd, shell=True, universal_newlines=True, timeout=timeout)
        except subprocess.CalledProcessError as e:
            output = e.output + "\n"
        except subprocess.TimeoutExpired as e:
            output = e.output + "\n"

        return output

    def run_and_get_pid(self, cmd, timeout=None):
        output = self.run(cmd, timeout=timeout)
        return self._parse_pid(output)

    def run_foreground(self, cmd, timeout=None):
        # `>/dev/null 2>&1` makes sure we return
        # `echo $!` prints pid of spawned process
        prefix = "plink -i C:/Users/ncb/Documents/raspberry.ppk" if is_win() else "ssh -f"

        if is_win():
            cmd = '{0} {1} "{2}"'.format(prefix, self.host, cmd)
        else:
            cmd = "{0} {1} '{2}'".format(prefix, self.host, cmd)

        # cmd = "ssh -f {0} '{1}'".format(self.host, cmd)
        # universal_newlines=True so output is string and not byte
        try:
            output = subprocess.check_output(
                cmd, shell=True, universal_newlines=True, timeout=timeout)
        except subprocess.CalledProcessError as e:
            output = e.output + "\n"
        except subprocess.TimeoutExpired as e:
            output = e.output + "\n"
        return output


    def run_fabric(self, command, sudo_run=False, timeout=2):
        with settings(hide('running'), timeout=timeout, host_string=self.host):
            try:
                if sudo_run:
                    return sudo(command)
                else:
                    return run(command)
            except Exception as e:
                    return e

    def run_background(self, cmd, timeout=None):
         return self.run("nohup {0}".format(cmd), timeout=timeout)

    def _parse_pid(self, output):
        if isinstance(output, bytes):
            output = output.decode()
        pid = output.strip().split('\n')[-1]
        # clean of junk characters
        pid = re.sub(r'[^\d]+', '', pid)
        return pid

    def _parse_out(self, output):
        if isinstance(output, bytes):
            output = output.decode()
        return output.strip().split('\n')[:-1]

    def kill(self, pid):
        '''kill process pid'''
        return self.run('kill {0}\n'.format(pid))

    def kill_python(self):
        '''kill all python processes'''
        return self.run('pkill python\n')

    def kill_service(self, servicename):
        this_pid = self.get_pid(servicename)
        if this_pid:
            return self.kill(this_pid)
        else:
            return None

    def get_pid(self, query):
        '''get pids of all processes partially matching `query`'''
        output = self.run_foreground("source ~/.bash_profile;python -m ethoservice.utils.find_pid {0}".format(query))
        return self._parse_pid(output)


    def reboot(self, wait=False, timeout=10, wait_interval=0.1):
        '''
        reboot host, can `wait` `timeout` seconds for host to come back
        '''
        output = self.run_fabric('reboot', sudo_run=True, timeout=1)
        if wait:
            time.sleep(2)  # make sure host is down
            wait_seconds = 0
            while wait_seconds<timeout and not self.is_online():
                wait_seconds += wait_interval
                time.sleep(wait_interval)

            return self.is_online()
        else:
            return output

    def ps(self, pid):
        return self.run('ps {0}\n'.format(pid))

    def is_running(self, pid):
        ''' return True if `pid` is in list of running processes'''
        if platform.system().lower() == "windows":
            output = self.run('ps -p {0}\n'.format(pid))
        else:
            output = self.run('ps -o pid= -p {0}\n'.format(pid))
        return len(self._parse_out(output))>0

    def is_online(self):
        return ping(self.host_name)


if __name__ == '__main__':
    sr = SSHRunner('ncb@rpi6')
    print(sr.host)
    sr.kill_python()
    print("starting process")
    cmd = "source ~/.bash_profile;cd ~/;nohup python -m ethoservice.SlpZeroService"
    output = sr.run(cmd)
    pid = sr._parse_pid(output)
    print("process pid: {0}".format(pid))
    print("pid {0} is running: {1}".format(pid, sr.is_running(pid)))
    print("killing pid {0}".format(pid))
    sr.kill(pid)
    print("pid {0} is running: {1}".format(pid, sr.is_running(pid)))
    print('rebooting')

    print(sr.reboot(wait=True))
