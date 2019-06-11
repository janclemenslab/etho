import platform
import os
import concurrent.futures

from ethomaster.head.ZeroClient import ZeroClient
from ethomaster import config
from ethomaster.utils.SSHRunner import SSHRunner
from ethoservice.SndZeroService import SND
from ethoservice.CamZeroService import CAM
from ethoservice.ThuZeroService import THU


# struct like object
class Struct():
    def __init__(self):
        pass


def islinux():
    return platform == "linux" or platform == "linux2"


def ismac():
    return platform == "darwin"


def iswin():
    return platform == "win32"


def getlist(string, delimiter=',', stripwhitespace=True):
    stringlist = string.split(delimiter)
    if stripwhitespace:
        stringlist = [item.strip() for item in stringlist]
    return stringlist


def list_clients(client_name):
    clients = {}
    for ii in range(len(client_name)):
        clients[client_name[ii]] = Struct()
        clients[client_name[ii]].name = client_name[ii]
        clients[client_name[ii]].is_online = ping(client_name[ii])
    return clients


def client_status(host, service='CAM'):
    services = {'CAM': CAM, 'SND': SND, 'THU': THU}
    S = services[service]
    folder_name = config['GENERAL']['folder']
    user = config['GENERAL']['user']
    alive_string = {True: 'alive', False: 'dead'}
    results = {'was_already_running': None,
               'can_start': None, 'can_ping': None, 'can_stop': None}
    isalive = ping(host)
    print("{0} is {1}".format(host, alive_string[isalive]))
    if isalive:
        # try to connect to each service
        server_name = 'python -m {0}'.format(S.__module__)
        print("{0}@{1}".format(S.__module__, host))
        c = ZeroClient("{0}@{1}".format(user, host))
        try:
            c.pid = c.check_is_running_server(
                S.__module__, folder_name, timeout=1)
            results['was_already_running'] = len(c.pid) > 0
            if len(c.pid):
                print("{0}@{1}: is running (pid={2})".format(
                    S.__module__, host, c.pid))
                is_started = True
            else:
                print("{0}@{1}: starting server".format(S.__module__, host))
                is_started = c.start_server(
                    server_name, folder_name, warmup=1, timeout=1)
                results['can_start'] = is_started
                print("{0}@{1}: server started".format(S.__module__, host))
            if is_started:
                try:
                    c.connect(
                        "tcp://{0}:{1}".format(host, S.SERVICE_PORT))
                    print("{0}@{1}: connected".format(S.__module__, host))
                    print(
                        "{0}@{1}: ping - {2}".format(S.__module__, host, c.ping()))
                    results['can_ping'] = c.ping() == 'pong'
                except Exception as e:
                    print(e)
                c.log.error('test')
                print("{0}@{1}: stop - {2}".format(S.__module__,
                                                   host, c.stop_server()))
                results['can_stop'] = True

            else:
                print("{0}@{1}: could not start server".format(
                    S.__module__, host))
                results['can_start'] = False
        except Exception as e:
            print(e)
    return results

def get_service_pid(host, service):
    user = config['GENERAL']['user']
    c = ZeroClient("{0}@{1}".format(user, host), service_name=S)
    pid = c.check_is_running_server(S, folder_name, timeout=1)
    return pid


def get_running_services(host, services=None):

    if services is None:
        services = config['GENERAL']['services']
    folder_name = config['GENERAL']['folder']
    user = config['GENERAL']['user']
    test_results = {}
    # make sure node is alive
    if ping(host):
        for S in services:
            # try to connect to each service
            try:
                c = ZeroClient("{0}@{1}".format(user, host), service_name=S)
                # pid = c.check_is_running_server(S, folder_name, timeout=2)
                pid = c.get_server_pid(S, folder_name, timeout=2)
                if len(pid):
                    test_results[S] = "running (pid={0})".format(pid)
                else:
                    test_results[S] = "not running"
            except Exception as e:
                test_results[S] = e
            finally:
                try:
                    c.close()
                except:
                    pass
    else:
        for S in services:
            test_results[S] = "node offline"

    return test_results

def kill_service(host, service):
    user = config['GENERAL']['user']
    pid = get_service_Pid(host, service)
    sr = SSHRunner("{0}@{1}".format(user, host))
    sr.kill(pid)


def kill_all_services(host):
    user = config['GENERAL']['user']
    sr = SSHRunner("{0}@{1}".format(user, host))
    for service in config['GENERAL']['services']:
        pid = get_service_Pid(host, service)
        sr.kill(pid)


def reboot(host):
    user = config['GENERAL']['user']
    sr = SSHRunner("{0}@{1}".format(user, host))
    sr.run_foreground("$echo 'droso123' | sudo -S reboot now")


def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that some hosts may not respond to a ping request even if the host name is valid.
    """
    # Ping parameters as function of OS
    parameters = "-n 1 -w 1000" if platform.system().lower() == "windows" else "-c 1 -W 1"
    suffix = ">nul 2>&1" if platform.system().lower() == "windows" else ">/dev/null 2>&1"
    # Pinging (">/dev/null 2>&1" supresses output)
    exit_code = os.system(
        "ping {0} {1}{2}".format(parameters, host, suffix))
    # 0=success
    return exit_code == 0


def exepool(func, args):
    # We can use a with statement to ensure threads are cleaned up promptly
    out = dict()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Start the load operations and mark each future with its URL
        future_to_url = {executor.submit(func, arg): arg for arg in args}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                out[url] = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (url, exc))
    return out


if __name__ == "__main__":
    client_names = config['GENERAL']['hosts']
    print(client_names)
    services = config['GENERAL']['services']
    print(exepool(ping, client_names))
    print(exepool(get_running_services, client_names))
