#!/usr/bin/python

import os
import logging
import xml.etree.ElementTree as ET

# Default INDI data directory
INDI_DATA_DIR = os.environ.get('INDI_DATA_DIR', "/usr/share/indi/")


class DeviceDriver:
    """
    Represents an INDI device driver.
    """

    def __init__(self, name, label, version, binary, family, skel=None, mdpd=False, custom=False, rule=None):
        """
        Initializes a DeviceDriver object.

        Args:
            name (str): The name of the driver.
            label (str): The label of the driver.
            version (str): The version of the driver.
            binary (str): The binary path of the driver.
            family (str): The family of the driver.
            skel (str, optional): The skeleton file path. Defaults to None.
            mdpd (bool, optional): Whether it's an MDPD driver. Defaults to False.
            custom (bool, optional): Whether it's a custom driver. Defaults to False.
            rule (dict, optional): Associated rule for the driver. Defaults to None.
        """
        self.name = name
        self.label = label
        self.skeleton = skel
        self.version = version
        self.binary = binary
        self.family = family
        self.mdpd = mdpd
        self.custom = custom
        self.rule = rule
        self.role = ""


class DriverCollection:
    """
    A collection of INDI drivers.
    """

    def __init__(self, path=INDI_DATA_DIR):
        """
        Initializes a DriverCollection and parses drivers from the specified path.

        Args:
            path (str, optional): The path to the INDI data directory. Defaults to INDI_DATA_DIR.
        """
        self.path = path
        self.drivers = []
        self.files = []
        self.parse_drivers()

    def parse_drivers(self):
        """
        Parses driver information from XML files in the INDI data directory.

        Handles:
            KeyError: If a required attribute is not found in an XML file.
            ET.ParseError: If there is an error parsing an XML file.
        """
        for fname in os.listdir(self.path):
            # Skip Skeleton files
            if fname.endswith('.xml') and '_sk' not in fname:
                self.files.append(os.path.join(self.path, fname))

        for fname in self.files:
            try:
                tree = ET.parse(fname)
                root = tree.getroot()

                for group in root.findall('devGroup'):
                    family = group.attrib['group']

                    for device in group.findall('device'):
                        label = device.attrib['label']
                        skel = device.attrib.get('skel', None)
                        mdpd = device.attrib.get('mdpd', None) == 'true'
                        drv = device.find('driver')
                        name = drv.attrib['name']
                        binary = drv.text
                        version = device.findtext('version', '0.0')

                        skel_file = os.path.join(self.path, skel) if skel else None
                        driver = DeviceDriver(name, label, version,
                                              binary, family, skel_file, mdpd, False, None)
                        self.drivers.append(driver)

            except KeyError as e:
                logging.error("Error in file %s: attribute %s not found" % (fname, e))
            except ET.ParseError as e:
                logging.error("Error in file %s: %s" % (fname, e))

        # Sort all drivers by label
        self.drivers.sort(key=lambda x: x.label)

    def parse_custom_drivers(self, drivers):
        """
        Parses custom driver information.

        Args:
            drivers (list): A list of dictionaries representing custom drivers.
        """
        for custom in drivers:
            driver = DeviceDriver(custom['name'], custom['label'], custom['version'], custom['exec'],
                                  custom['family'], None, False, True, None)
            self.drivers.append(driver)

    def clear_custom_drivers(self):
        """
        Removes custom drivers from the collection.
        """
        self.drivers = list(filter(lambda driver: driver.custom is not True, self.drivers))

    def by_label(self, label):
        """
        Finds a driver by its label.

        Args:
            label (str): The label of the driver to find.

        Returns:
            DeviceDriver or None: The found driver or None if not found.
        """
        # Try first an exact match
        for driver in self.drivers:
            if driver.label == label:
                return driver
        # Try second as partial match
        for driver in self.drivers:
            if label.startswith(driver.label):
                return driver
        return None

    def by_name(self, name):
        """
        Finds a driver by its name.

        Args:
            name (str): The name of the driver to find.

        Returns:
            DeviceDriver or None: The found driver or None if not found.
        """
        for driver in self.drivers:
            if (driver.name == name):
                return driver

        return None

    def by_binary(self, binary):
        """
        Finds a driver by its binary path.

        Args:
            binary (str): The binary path of the driver to find.

        Returns:
            DeviceDriver or None: The found driver or None if not found.
        """
        for driver in self.drivers:
            if (driver.binary == binary):
                return driver

        return None

    def get_families(self):
        """
        Gets a dictionary of driver families and their associated driver labels.

        Returns:
            dict: A dictionary where keys are family names and values are lists of driver labels.
        """
        families = {}
        for drv in self.drivers:
            if drv.family in families:
                families[drv.family].append(drv.label)
            else:
                families[drv.family] = [drv.label]
        return families
        
    def apply_rules(self, rules):
        """
        Applies rules to drivers based on their labels.

        Args:
            rules (list): A list of dictionaries representing the rules.
        """
        if not rules:
            return
            
        for rule in rules:
            driver_label = rule.get('Driver')
            
            if driver_label:
                driver = self.by_label(driver_label)
                if driver:
                    driver.rule = rule
