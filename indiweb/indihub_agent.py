#!/usr/bin/python

import os
import logging
from subprocess import call
import psutil

INDIHUB_AGENT_OFF = 'off'
INDIHUB_AGENT_DEFAULT_MODE = 'solo'

try:
    INDIHUB_AGENT_CONFIG = os.path.join(os.environ['HOME'], '.indihub')
except KeyError:
    INDIHUB_AGENT_CONFIG = '/tmp/indihub'

if not os.path.exists(INDIHUB_AGENT_CONFIG):
    os.makedirs(INDIHUB_AGENT_CONFIG)

INDIHUB_AGENT_CONFIG += '/indihub.json'


class IndiHubAgent(object):
    def __init__(self, web_addr, hostname, port):
        self.__web_addr = web_addr
        self.__hostname = hostname
        self.__port = port
        self.__mode = INDIHUB_AGENT_OFF

        # stop running indihub-agent, if any
        self.stop()

    def __run(self, profile, mode, conf):
        cmd = 'indihub-agent -indi-server-manager=%s -indi-profile=%s -mode=%s -conf=%s -api-origins=%s > ' \
              '/tmp/indihub-agent.log 2>&1 &' % \
              (self.__web_addr, profile, mode, conf,
               '%s:%d,%s.local:%d' % (self.__hostname, self.__port, self.__hostname, self.__port))
        logging.info(cmd)
        call(cmd, shell=True)

    def start(self, profile, mode=INDIHUB_AGENT_DEFAULT_MODE, conf=INDIHUB_AGENT_CONFIG):
        if self.is_running():
            self.stop()

        self.__run(profile, mode, conf)
        self.__mode = mode

    def stop(self):
        self.__mode = 'off'
        cmd = ['pkill', '-2', 'indihub-agent']
        logging.info(' '.join(cmd))
        ret = call(cmd)
        if ret == 0:
            logging.info('indihub-agent terminated successfully')
        else:
            logging.warn('terminating indihub-agent failed code ' + str(ret))

    def is_running(self):
        for proc in psutil.process_iter():
            if proc.name() == 'indihub-agent':
                return True
        return False

    def get_mode(self):
        return self.__mode
