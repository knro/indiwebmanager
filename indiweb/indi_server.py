#!/usr/bin/python
import logging
import os
from subprocess import call, check_output
import threading

# Local imports
from .AsyncSystemCommand import AsyncSystemCommand

INDI_PORT = 7624
INDI_FIFO = '/tmp/indiFIFO'
try:
    INDI_CONFIG_DIR = os.path.join(os.environ['HOME'], '.indi')
except KeyError:
    INDI_CONFIG_DIR = '/tmp/indi'

class IndiServer(object):
    def __init__(self, fifo=INDI_FIFO, conf_dir=INDI_CONFIG_DIR):
        self.__fifo = fifo
        self.__sock_path = f"{self.__fifo}_sock"
        self.__conf_dir = conf_dir
        self.__async_cmd = None
        self.__command_thread = None

    def __clear_fifo(self):
        logging.info("Deleting fifo %s" % self.__fifo)
        call(['rm', '-f', self.__fifo])
        call(['mkfifo', self.__fifo])

    def __run(self, port):
        cmd = 'indiserver -p %d -m 1000 -v -f %s -u %s > /tmp/indiserver.log 2>&1' % \
            (port, self.__fifo, self.__sock_path)
        logging.info(cmd)
        self.__async_cmd = AsyncSystemCommand(cmd)
        # Run the command asynchronously
        self.__command_thread = threading.Thread(target=self.__async_cmd.run)
        self.__command_thread.start()

    def start_driver(self, driver):
        # escape quotes if they exist
        cmd = 'start %s' % driver.binary

        if driver.skeleton:
            cmd += ' -s "%s"' % driver.skeleton

        cmd += ' -n "%s"' % driver.label
        cmd = cmd.replace('"', '\\"')
        full_cmd = 'echo "%s" > %s' % (cmd, self.__fifo)
        logging.info(full_cmd)
        call(full_cmd, shell=True)
        self.__running_drivers[driver.label] = driver

    def stop_driver(self, driver):
        # escape quotes if they exist
        cmd = 'stop %s' % driver.binary

#        if "@" not in driver.binary:
        cmd += ' -n "%s"' % driver.label

        cmd = cmd.replace('"', '\\"')
        full_cmd = 'echo "%s" > %s' % (cmd, self.__fifo)
        logging.info(full_cmd)
        call(full_cmd, shell=True)
        del self.__running_drivers[driver.label]

    def start(self, port=INDI_PORT, drivers=[]):
        if self.is_running():
            self.stop()

        self.__clear_fifo()
        self.__run(port)
        self.__running_drivers = {}

        for driver in drivers:
            self.start_driver(driver)

    def stop(self):
        # Terminate will also kill the child processes like the drivers
        try:
            self.__async_cmd.terminate()
            self.__command_thread.join()
        except Exception as e:
            logging.warn('indi_server: termination failed with error ' + str(e))
        else:
            logging.info('indi_server: terminated successfully')

    def is_running(self):
        if self.__async_cmd:
            return self.__async_cmd.is_running()
        else:
            return False

    def set_prop(self, dev, prop, element, value):
        cmd = ['indi_setprop', '%s.%s.%s=%s' % (dev, prop, element, value)]
        call(cmd)

    def get_prop(self, dev, prop, element):
        cmd = ['indi_getprop', '%s.%s.%s' % (dev, prop, element)]
        output = check_output(cmd)
        return output.split('=')[1].strip()

    def get_state(self, dev, prop):
        return self.get_prop(dev, prop, '_STATE')

    def auto_connect(self):
        cmd = ['indi_getprop', '*.CONNECTION.CONNECT']
        output = ""
        try:
            output = check_output(cmd).decode('utf_8')
        except Exception as e:
            logging.error(e)

        output = output.replace("Off", "On")

        for dev in output.splitlines():
            command = ['indi_setprop', dev]
            logging.info(command)
            call(command)

    def get_running_drivers(self):
        drivers = self.__running_drivers
        return drivers
