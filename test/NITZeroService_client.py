import time
from utils.zeroclient import ZeroClient
from services.NITriggerZeroService import NIT
import pandas as pd
from .. import config
from utils.config import readconfig
import numpy as np
import subprocess
import defopt

# ip_address = 'localhost'
# protocolfile = 'protocols/default.txt'
# playlistfile = 'playlists/IPItuneChaining.txt'
# #
# # load config/protocols
# prot = readconfig(protocolfile)
# # maxDuration = int(3600)
#
#
# user_name = config['GENERAL']['user']
# folder_name = config['GENERAL']['folder']


def main(basename: str, filecounter: int):
    ip_address = 'localhost'
    port = "/Dev1/port0/line1:3"
    START = [1, 0, 0]
    STOP = [0, 1, 0]
    NEXT = [0, 0, 1]  # or [1, 0, 1]
    print(basename, filecounter)
    print([NIT.SERVICE_PORT, NIT.SERVICE_NAME])
    nit = ZeroClient("{0}".format(ip_address), 'nidaq')
    try:
        sp = subprocess.Popen('python -m ethoservice.NITriggerZeroService')
        nit.connect("tcp://{0}:{1}".format(ip_address, NIT.SERVICE_PORT))
        print('done')
        nit.setup(-1, port)
        # nit.init_local_logger('{0}/{1}_nit.log'.format(dirname, filename))
        print('sending START')
        nit.send_trigger(START)
        print(filecounter)

        # NEXT would be sent from within DAQZeroService
        time.sleep(5)
        print('sending NEXT')
        nit.send_trigger(NEXT)
        filecounter += 1
        print(filecounter)
        time.sleep(5)
        print('sending NEXT')
        nit.send_trigger(NEXT)
        filecounter += 1
        print(filecounter)

        time.sleep(5)
        print('sending STOP')
        nit.send_trigger(STOP)
    except:
        pass
    nit.finish()

    nit.stop_server()

    del(nit)

    sp.terminate()
    sp.kill()


if __name__ == '__main__':
    defopt.run(main)
