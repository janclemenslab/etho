#!/usr/bin/env python
import time
import zmq
import logging
import logging.handlers
from ethomaster import config


if __name__ == '__main__':
    logger = logging.getLogger('')
    logger.setLevel(logging.INFO)
    # __ to console logger
    console = logging.StreamHandler()
    # console.setLevel(logging.DEBUG)
    # formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
    # add handler to logger
    logger.addHandler(console)

    # __ set to-file-logger that creates new log file everyday at midnight
    file = logging.handlers.TimedRotatingFileHandler(
        'log/{0}'.format(time.strftime("%Y-%m-%d")), 'midnight', 1)
    file.suffix = "%Y-%m-%d"  # or anything else that strftime will allow
    # formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    # tell the handler to use this format
    file.setFormatter(formatter)
    # file.setLevel(logging.INFO)
    # add handler to logger
    logger.addHandler(file)

    # subscribe to all logging ports
    logging_ports = range(int(config['LOGGER']['portrange'][0]), int(config['LOGGER']['portrange'][1]))
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt_string(zmq.SUBSCRIBE, '')
    for port in logging_ports:
        sub.bind('tcp://0.0.0.0:{0}'.format(port))

    print('LISTENING FOR MESSAGES')
    while True:
        # logger publishes logger as multipart: [level, message]
        try:
            level, message = sub.recv_multipart(zmq.NOBLOCK)
            # get level-appropriate logging function
            log = getattr(logger, level.decode('utf8').lower())
            log(message.decode('utf8').rstrip())
        except zmq.error.Again as e:
            pass
        time.sleep(.01)
