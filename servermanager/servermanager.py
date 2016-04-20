#!/usr/bin/python

import subprocess, sys, psutil, re
from parsedrivers import driversList

 #2 Specify INDI FIFO, or leave the default value.
indi_fifo = "/tmp/indiFIFO"

### Script Functions ###
##################################################################################
##################################################################################
##################################################################################

def clearFIFO():
    sendCommand("rm -f " + indi_fifo)
    sendCommand("mkfifo " + indi_fifo)

def startINDIServer(port=7624):
    cmd = 'indiserver -p ' + str(port) + ' -m 100 -v -f ' + indi_fifo + ' > /dev/null 2>&1 &'
    print cmd
    sys.stdout.flush()
    subprocess.call(cmd, shell=True)    
    
def sendCommand(command):
    cmd = command
    #print cmd
    sys.stdout.flush()
    output = subprocess.check_output(cmd, shell=True)
    #print output
    sys.stdout.flush()
    return output

def startINDIDriver(driver):
    cmd = None
    if "@" in driver.binary:
        # escape quotes if they exist
        driver.binary = driver.binary.replace('"','\\"')
        cmd = 'echo \"start ' + driver.binary + '\" > ' + indi_fifo
    else:        
        cmd = 'echo \"start ' + driver.binary + ' -n \"' + driver.label + '\"\"  > ' + indi_fifo        
    print cmd
    sys.stdout.flush()
    subprocess.call(cmd, shell=True)

def setINDIValue(deviceName, propertyName, elementName, value):
    cmd = "indi_setprop " + deviceName + "." + propertyName + "." + elementName + "=" + value
    #print cmd
    sys.stdout.flush()
    subprocess.call(cmd, shell=True)    
    
def getINDIValue(deviceName, propertyName, elementName):
    cmd = "indi_getprop " + deviceName + "." + propertyName + "." + elementName
    #print cmd
    sys.stdout.flush()
    output = subprocess.check_output(cmd, shell=True)    
    value  = output.split('=')
    return value[1]

def getINDIState(deviceName, propertyName):
    cmd = "indi_getprop " + deviceName + "." + propertyName + "._STATE"
    #print cmd
    sys.stdout.flush()
    output = subprocess.check_output(cmd, shell=True)
    value  = output.split('=')
    return value[1].strip()


def startServer(port, drivers):
    clearFIFO()
    startINDIServer(port)
    for driver in drivers:
        print ("Driver binary is " + driver.binary)
        sys.stdout.flush()
        startINDIDriver(driver)
    
def stopServer():
    cmd = "pkill indiserver"
    print cmd
    sys.stdout.flush()
    subprocess.call(cmd, shell=True)
    
def isServerRunning():
    for proc in psutil.process_iter():
        if (proc.name() == "indiserver"):
            return True
    return False
                   
def getRunningDrivers():
    runningDrivers = [proc.name() for proc in psutil.process_iter() if proc.name().startswith("indi_")]
    return runningDrivers
            
