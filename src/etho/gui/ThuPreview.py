import time
import sys
from ..utils.zeroclient import ZeroClient
from ..services.ThuZeroService import THU


def main(ip_address):
    # load config/protocols
    # prot = readconfig(protocolfile)
    # print(prot)
    maxduration = 7  # int(prot['NODE']['maxduration'])
    user_name = 'ncb'  # prot['NODE']['user']
    folder_name = '~/'  # prot['NODE']['folder']
    SER = 'pickle'
    pin = 4
    interval = 1

    thu_server_name = 'python -m {0} {1}'.format(THU.__module__, SER)
    print([THU.SERVICE_PORT, THU.SERVICE_NAME])
    thu = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pithu', serializer=SER)
    print(' starting server:', end='')
    ret = thu.start_server(thu_server_name, folder_name, warmup=1)
    print(f'{"success" if ret else "FAILED"}.')
    print(' connecting to server:', end='')
    thu.connect("tcp://{0}:{1}".format(ip_address,  THU.SERVICE_PORT))
    print(f'{"success" if ret else "FAILED"}.')
    print(pin, interval, maxduration)
    # thu.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
    # thu.setup(prot['THU']['pin'], prot['THU']['interval'], maxduration)
    thu.setup(pin, interval, maxduration)
    time.sleep(1)
    print(thu.progress())
    thu.start()
    cnt = 0
    while cnt < maxduration-2:
        print(thu.info())
        time.sleep(1)
        cnt += 1
    print('done')
    thu.finish()
    print('finished')


if __name__ == '__main__':
    '''USAGE: `python ./ThuPreview.py HOSTNAME`'''
    if len(sys.argv) > 1:
        host = sys.argv[1]
        main(host)
