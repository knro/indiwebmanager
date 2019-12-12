#!/usr/bin/python

# import os
import re
import logging
from subprocess import check_output


class Device:
    """A collection of device"""

    def __init__(self):
        self.host = "localhost"
        self.port = 7624

    @staticmethod
    def get_devices():
        cmd = ['indi_getprop', '*.CONNECTION.CONNECT']
        try:
            output = check_output(cmd).decode('utf_8')
            lines = re.split(r'[\n=]', output)
            output = {lines[i]: lines[i + 1] for i in range(0, len(lines) - 1, 2)}
            # lines = re.split(r'[=]', output)
            devices = []
            for key, val in output.items():
                device_name = re.match("[^.]*", key)
                devices.append({"device": device_name.group(), "connected": val == "On"})
            return devices
        except Exception as e:
            logging.error(e)
