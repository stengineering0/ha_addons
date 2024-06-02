import asyncio
import getopt
import logging
import os
import signal
from enum import Enum
from sys import argv

import yaml
from voluptuous import Required, Schema, MultipleInvalid, All, Any, Optional, Coerce

from wb_connector import WbConnector
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.getLogger().setLevel(logging.INFO)  # root

logger = logging.getLogger(__name__)

STOP = asyncio.Event()

class ConfigLogLevel(Enum):
    FATAL = 'FATAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'


LOGLEVEL_MAPPER = {
    ConfigLogLevel.FATAL: logging.FATAL,
    ConfigLogLevel.ERROR: logging.ERROR,
    ConfigLogLevel.WARNING: logging.WARNING,
    ConfigLogLevel.INFO: logging.INFO,
    ConfigLogLevel.DEBUG: logging.DEBUG,
}

config_schema = Schema({
    Optional('general', default={}): {
        Optional('loglevel', default=ConfigLogLevel.WARNING): Coerce(ConfigLogLevel),
    },
    Required('wirenboard'): {
        Required('broker_host'): str,
        Optional('broker_port', default=1883): int,
        Optional('username'): str,
        Optional('password'): str,
        Optional('client_id', default='wirenboard-mqtt-discovery'): str
    },
})


def ask_exit(*args):
    logger.info('Exiting')
    STOP.set()


async def main(conf):
    logging.basicConfig(level=LOGLEVEL_MAPPER[conf['general']['loglevel']])
    logging.getLogger('gmqtt').setLevel(logging.ERROR)  # don't need extra messages from mqtt

    wiren_conf = conf['wirenboard']

    logger.info('Starting')
    wiren = WbConnector(
        broker_host=wiren_conf['broker_host'],
        broker_port=wiren_conf['broker_port'],
        username=wiren_conf['username'] if 'username' in wiren_conf else None,
        password=wiren_conf['password'] if 'password' in wiren_conf else None,
        client_id=wiren_conf['client_id']
    )

    await wiren.connect()  # FIXME: handle connect exceptions

    await STOP.wait()

    await wiren.disconnect()


def usage():
    print('Usage:\n'
          '_main.py -c <config_file>')


if __name__ == '__main__':
    config_file = None
    try:
        opts, args = getopt.getopt(argv[1:], "hc:")
    except getopt.GetoptError:
        usage()
        exit(1)
    for opt, arg in opts:
        if opt == '-h':
            usage()
            exit()
        elif opt == '-c':
            config_file = arg
    if not config_file:
        usage()
        exit(1)

    try:
        with open(config_file) as f:
            config_file_content = f.read()
    except OSError as e:
        logger.error(e)
        exit(1)

    config = yaml.load(config_file_content, Loader=yaml.FullLoader)
    if not config:
        logger.error(f'Could not load conf "{config_file}"')
        exit(1)
    try:
        config = config_schema(config)
    except MultipleInvalid as e:
        logger.error('Config error')
        logger.error(e)
        exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.add_signal_handler(signal.SIGINT, ask_exit)
    loop.add_signal_handler(signal.SIGTERM, ask_exit)

    loop.run_until_complete(main(config))
