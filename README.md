# INDI Web Manager

INDI Web Manager is a simple Web Application to manage
[INDI](http://www.indilib.org) server. It supports multiple driver profiles
along with optional custom remote drivers. It can be used to start INDI server
locally, and also to connect or **chain** to remote INDI servers.

![INDI Web Manager](http://indilib.org/images/indi/indiwebmanager.png)

The Web Application is based on [Bottle Py](http://bottlepy.org)
micro-framework. It has a built-in webserver and by default listens on port
8624.

# Installation

Before installing the **indiweb** package, make sure the INDI library is
installed on the target system.

You can install the **indiweb** Python package using pip:

```
$ pip install indiweb
```

You may want to install it system-wide, only in your user account or even into
a [virtual environment](https://virtualenv.pypa.io/en/stable/) (if you are a
developer).

If you want to install it system-wide, you will have to invoke pip with
superuser rights:

```
$ sudo pip install indiweb
```

# Usage

After installing the **indiweb** package, the command **indi-web** will be
available in your sytem PATH.

You can obtain help about the **indi-web** command by invoking:

```
$ indi-web -h
```

The INDI Web Manager runs as a standalone web server. It can be started
manually by invoking:

```
$ indi-web -v
```

Then using your favorite web browser, go to
[http://localhost:8624](http://localhost:8624) if the INDI Web Manager is
running locally. If the INDI Web Manager is installed on a remote system,
simply replace localhost with the hostname or IP address of the remote system.

# Auto start

If you selected any profile as **Auto Start** then the INDI server shall be
automatically started when the service is executed at start up.

# Systemd configuration

The provided file `indiwebmanager.service` is an example *systemd service file*
that can be used to run `indi-web` as root.

`indiwebmanager-pi.service` is another example of service file. In this case
`indi-web` will run as *pi* user.

Copy your preferred service file to `/etc/systemd/system`:

```
sudo cp indiwebmanager.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/indiwebmanager.service
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

The Web Application provides a default profile to run simulator drivers. To use
a new profile, add the profile name and then click  the plus button. Next,
select which drivers to run under this particular profile. After selecting the
drivers, click the **Save** icon to save all your changes. To enable automatic
startup of INDI server for a particular profile when the device boots up or
when invoked manually via the **systemctl** command, check the **Auto Start**
checkbox.

# API

INDI Web Manager provides a RESTful API to control all aspects of the
application. Data communication is via JSON messages. All URLs are appended to
the hostname:port running the INDI Web Manager.

## INDI Server Methods

### Get Server Status

 URL | Method | Return | Format
--- | --- | --- | ---
/api/server/status | GET | INDI server status (running or not) | {'server': bool}

**Example:** curl http://localhost:8624/api/server/status
**Reply:** [{"status": "False"}]

### Start Server

 TODO

### Stop Server
URL | Method | Return | Format
--- | --- | --- | ---
/api/server/stop | POST | None | []

### Get running drivers list
URL | Method | Return | Format
--- | --- | --- | ---
/api/server/drivers | GET | Returns an array for all the locally running drivers | {'driver': driver_executable}

**Example:** curl http://localhost:8624/api/server/drivers
**Reply:** [{"driver": "indi_simulator_ccd"}, {"driver": "indi_simulator_telescope"}, {"driver": "indi_simulator_focus"}]

## Profiles

### Add new profile
URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/<name> | POST | None | None

To add a profile named **foo**:

```
curl -H "Content-Type: application/json" -X POST http://localhost:8624/api/profiles/foo
```

### Delete profile
URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/<name> | DELETE | None | None

To delete a profile named **foo**:

```
curl -X DELETE http://localhost:8624/api/profiles/foo
```

### Get All Profiles

TODO

### TODO

# Authors

Jasem Mutlaq (mutlaqja@ikarustech.com)

Juan Menendez (juanmb@gmail.com)
