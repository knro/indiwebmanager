#!/usr/bin/python
import logging
import os
import threading

# local
from .AsyncSystemCommand import AsyncSystemCommand

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

    def __run(self, profile, mode, conf):
        cmd = 'indihub-agent -indi-server-manager=%s -indi-profile=%s -mode=%s -conf=%s -api-origins=%s > ' \
              '/tmp/indihub-agent.log 2>&1 &' % \
              (self.__web_addr, profile, mode, conf,
               '%s:%d,%s.local:%d' % (self.__hostname, self.__port, self.__hostname, self.__port))
        logging.info(cmd)
        self.__async_cmd = AsyncSystemCommand(cmd)
        # Run the command asynchronously
        self.__command_thread = threading.Thread(target=self.__async_cmd.run)
        self.__command_thread.start()

    def start(self, profile, mode=INDIHUB_AGENT_DEFAULT_MODE, conf=INDIHUB_AGENT_CONFIG):
        if self.is_running():
            self.stop()
        self.__run(profile, mode, conf)
        self.__mode = mode

    def stop(self):
        # Terminate will also kill the child processes like the drivers
        try:
            self.__async_cmd.terminate()
            self.__command_thread.join()
        except Exception as e:
            logging.warn('indihub_agent: termination failed with error ' + str(e))
        else:
            logging.info('indihub_agent: terminated successfully')

    def is_running(self):
        if self.__async_cmd:
            return self.__async_cmd.is_running()
        else:
            return False

    def get_mode(self):
        return self.__mode
