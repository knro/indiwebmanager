#!/usr/bin/python

import xml.etree.ElementTree as ET
import os
import json

# INDI Data Directory
INDIDataDir = "/usr/share/indi/"

# device driver container
class DeviceDriver:
    def __init__(self, name, label, version, binary, family):
        self.name   = name
        self.label  = label
        self.version= version
        self.binary = binary
        self.family = family
        self.role   = ""
    
driversList    = []
xmlDriverFiles = []

for file in os.listdir(INDIDataDir):
    # Skip Skeleton files
    if (file.endswith(".xml") and "_sk" not in file):
        print (INDIDataDir + file)
        xmlDriverFiles.append(INDIDataDir + file)              

for file in xmlDriverFiles:
    print "Parsing XML file: " + file
    tree = ET.parse(file)
    root = tree.getroot()
    for group in root:        
        #print " ---> " + group.attrib['group']
        family = group.attrib['group']
        for device in group:
            label = device.attrib["label"];
            driver = device[0]
            name   = driver.attrib["name"]
            binary = driver.text
            version = device[1].text   
            newDeviceDriver = DeviceDriver(name, label, version, binary, family)
            driversList.append(newDeviceDriver)

# Sort all drivers by label            
driversList.sort(key=lambda x: x.label)


def findDriverByLabel(label):
    for driver in driversList:
        #print ("comparing between " + driver.label + " and request " + label)
        if (driver.label == label):
            return driver
                
def findDriverByName(name):
    for driver in driversList:
        if (driver.label == name):
            return driver
        
def findDriverByBinary(binary):
    for driver in driversList:
        if (driver.binary == binary):
            return driver
        
