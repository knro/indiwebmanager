#!/usr/bin/python

import os
import xml.etree.ElementTree as ET

# Default INDI data directory
INDI_DATA_DIR = "/usr/share/indi/"


class DeviceDriver:
    """Device driver container"""

    def __init__(self, name, label, version, binary, family, skel=None):
        self.name = name
        self.label = label
        self.skeleton = skel
        self.version = version
        self.binary = binary
        self.family = family
        self.role = ""


class DriverCollection:
    """A collection of drivers"""

    def __init__(self, path=INDI_DATA_DIR):
        self.path = path
        self.drivers = []
        self.files = []
        self.parse_drivers()

    def parse_drivers(self):
        for fname in os.listdir(self.path):
            # Skip Skeleton files
            if fname.endswith(".xml") and "_sk" not in fname:
                self.files.append(os.path.join(self.path, fname))

        for fname in self.files:
            tree = ET.parse(fname)
            root = tree.getroot()

            for group in root:
                family = group.attrib['group']

                for device in group:
                    label = device.attrib["label"]
                    skel = device.attrib.get("skel", None)
                    drv = device[0]
                    name = drv.attrib["name"]
                    binary = drv.text
                    version = device[1].text

                    skel_file = os.path.join(self.path, skel) if skel else None
                    driver = DeviceDriver(name, label, version,
                                          binary, family, skel_file)
                    self.drivers.append(driver)

        # Sort all drivers by label
        self.drivers.sort(key=lambda x: x.label)

    def by_label(self, label):
        for driver in self.drivers:
            if (driver.label == label):
                return driver

    def by_name(self, name):
        for driver in self.drivers:
            if (driver.name == name):
                return driver

    def by_binary(self, binary):
        for driver in self.drivers:
            if (driver.binary == binary):
                return driver

    def get_families(self):
        families = {}
        for drv in self.drivers:
            if drv.family in families:
                families[drv.family].append(drv.label)
            else:
                families[drv.family] = [drv.label]
        return families
