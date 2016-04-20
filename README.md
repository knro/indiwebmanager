# INDI Web Manager

INDI Web Manager is a simple Web Application to manage [INDI](http://www.indilib.org) server. It supports multiple driver profiles along with optional custom remote drivers. It can be used to start INDI server locally, and also to connect or **chain** to remote INDI servers.

![INDI Web Manager](http://indilib.org/images/indi/indiwebmanager.png)

# Installation

INDI Library must be installed on the target system. The Web Application is based on [Bottle Py](http://bottlepy.org) micro-framework. It has a built-in webserver and by default listens on port 8080. Install the pre-requisites:

```
$ sudo apt-get install python-dev
$ sudo pip install psutil
```

Copy the **servermanager** folder to $(HOME) or any folder where the user has read and write access.

# Usage

The INDI Web Manager can run as a standalone server. It can be started manually by invoking python:

```
$ cd servermanager
$ python drivermanager.py
```

Then using your favorite web browser, go to http://localhost:8080 if the INDI Web Manager is running locally. If the INDI Web Manager is installed on a remote system, simply replace localhost with the hostname or IP address of the remote system.

# Auto Start

To enable the INDI Web Manager to automatically start after a system reboot, a systemd service file is provided for your convenience:

```
[Unit]
Description=INDI Web Manager
After=multi-user.target

[Service]
Type=idle
ExecStart=/usr/bin/python /home/pi/servermanager/drivermanager.py

[Install]
WantedBy=multi-user.target
```

The above service files assumes you copied the servermanager directory to /home/pi, so change it to whereever you installed the directory on your target system.

Copy the indiwebmanager.service file to **/lib/systemd/system**:

```
sudo cp indiwebmanager.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/indiwebmanager.service
```

Now configure systemd to load the service file during boot:

```
sudo systemctl daemon-reload
sudo systemctl enable indiwebmanager.service
```

Finally, reboot the system for your changes to take effect:

```
sudo reboot
```

After startup, check the status of the INDI Web Manager service:

```
sudo systemctl status indiwebmanager.service
```

If all appears OK, you can start using the Web Application using any browser.

# Profiles

The Web Application provides a default profile to run simulator drivers. To use a new profile, add the profile name and then click  the plus button. Next, select which drivers to run under this particular profile. After selecting the drivers, click the **Save** icon to save all your changes.

# API

INDI Web Manager provides a RESTful API to control all aspects of the application. Data communication is via JSON messages. All URLs are appended to the hostname:port running the INDI Web Manager.

## INDI Server Methods

### Get Server Status

|URL                 |   Method      |       Return                          | Format         |
:------------------:|:-------------:|:-------------------------------------:|:-----------------
/api/server/status       GET          INDI server status (running or not)      {'server', bool}

### Get drivers list
* url: /api/server/drivers
* method: GET
* Returns an array for all the drivers available in the device. It only returns a list of the drivers labels.
* format: {'driver': driver_executable}

### TODO

# Author

Jasem Mutlaq (mutlaqja@ikarustech.com)
