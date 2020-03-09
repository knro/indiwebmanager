# INDI Web Manager

INDI Web Manager is a simple Web Application to manage:

- [INDI](http://www.indilib.org) Server
- [INDIHUB](https://indihub.space) Agent

It supports multiple driver profiles
along with optional custom remote drivers. It can be used to start INDI server
locally, and also to connect or **chain** to remote INDI servers.

![INDI Web Manager](http://indilib.org/images/indi/indiwebmanager.png)

The Web Application is based on [Bottle Py](http://bottlepy.org)
micro-framework. It has a built-in webserver and by default listens on port 8624.

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

# Auto Start

If you selected any profile as **Auto Start** then the INDI server shall be
automatically started when the service is executed at start up.

# Auto Connect

Similary to Auto Start, **Auto Connect** would connect all the drivers after
the server is up and running.

# Start vs. Connect

What is the difference between *starting* a driver and *connecting* a driver?
- Start: The INDI server executes the driver. The driver starts up and provide a list of properties. It does not establish connection with the physical device.
- Connect: Establish connection to the physical device.

# Systemd configuration

The provided file `indiwebmanager.service` is an example *systemd service file*
that can be used to run `indi-web` at startup as *pi* user. If your username is different
please edit the file and change the username first.

Indiwebmanager must be installed system-wide:

```
sudo pip install indiweb
```

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
/api/server/status | GET | INDI server status (running or not) | {'server': bool, 'active_profile': profile_name}

**Example:** curl http://localhost:8624/api/server/status
**Reply:** [{"status": "False"}, {"active_profile": ""}]

### Start Server

URL | Method | Return | Format
--- | --- | --- | ---
/api/server/\<name>/start | POST | None | []

Where name is the equipment profile name to start.

**Example:** curl -X POST http://localhost:8624/api/server/start/Simulators
**Reply:** None

### Stop Server
URL | Method | Return | Format
--- | --- | --- | ---
/api/server/stop | POST | None | []

### Get running drivers list
URL | Method | Return | Format
--- | --- | --- | ---
/api/server/drivers | GET | Returns an array for all the locally **running** drivers

The format is as following:
- **Name**: Driver name. If no label is specified, the driver uses this default name.
- **Label**: If specified, set the driver name to this label.
- **Skeleton**: XML Skeleton path which is used by some drivers (e.g. EQMod)
- **Version**: Driver version.
- **Binary**: Executable driver binary
- **Family**: Category of driver (Telescopes, CCDs, Domes..etc)
- **Custom**: True if the driver is custom, false otherwise

**Example:** curl http://localhost:8624/api/server/drivers
**Reply:** [{"name": "Telescope Simulator", "label": "Telescope Simulator", "skeleton": null, "version": "1.0", "binary": "indi_simulator_telescope", "family": "Telescopes", "custom": false}, {"name": "CCD Simulator", "label": "CCD Simulator", "skeleton": null, "version": "1.0", "binary": "indi_simulator_ccd", "family": "CCDs", "custom": false}, {"name": "Focuser Simulator", "label": "Focuser Simulator", "skeleton": null, "version": "1.0", "binary": "indi_simulator_focus", "family": "Focusers", "custom": false}]

## Profiles

### Add new profile
URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/\<name> | POST | None | None

To add a profile named **foo**:

```
curl -H "Content-Type: application/json" -X POST http://localhost:8624/api/profiles/foo
```

### Delete profile
URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/\<name> | DELETE | None | None

To delete a profile named **foo**:

```
curl -X DELETE http://localhost:8624/api/profiles/foo
```

### Get All Profiles

URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles | GET | Returns all profiles | [{"port": number, "id": ID, "autostart": number, "name": profile_name}, ...]

**Example:** curl http://localhost:8624/api/profiles
**Reply:** [{"port": 7624, "id": 1, "autostart": 0, "autoconnect": 0, "name": "Simulators"}, {"port": 7624, "id": 2, "autostart": 0, "name": "EQ5"}]

### Get One Profile

URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/\<name> | GET | Returns one Profile

**Example:** curl http://localhost:8624/api/profiles/Simulators
**Reply:** {"id": 1, "name": "Simulators", "port": 7624, "autostart": 0, "autoconnect": 0}

### Update One Profile

URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/\<name> | PUT | Update profile info (port, autostar, autoconnect)

**Example:** curl -H 'Content-Type: application/json' -X PUT -d '{"port":9000,"autostart":1,"autoconnect":0}' http://localhost:8624/api/profiles/Simulators
**Reply:** None

### Save drivers to profile

URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/\<name>/drivers | POST | Save local and remote drivers to a profile. 
If profile does not exist, it is created. It expects an array of drivers.
- Local drivers must define the *label* attribute.
- Remote drivers must define the *remote* attribute.

For example:
[{"label":"Pegasus UPB"},{"remote":"astrometry@myremoteobservatory.com"}]

To add the drivers above to a profile named **My Obs**, we call the following.
**Example:** curl -H 'Content-Type: application/json' -X POST -d '[{"label":"Pegasus UPB"},{"remote":"astrometry@myremoteobservatory.com"}]' http://localhost:8624/api/profiles/My%20Obs/drivers
**Reply:** None

## Drivers

### List all Groups

URL | Method | Return | Format
--- | --- | --- | ---
/api/drivers/groups | GET | Get the driver categories

**Example:** curl http://localhost:8624/api/drivers/groups
**Reply:** ["Adaptive Optics", "Agent", "Auxiliary", "CCDs", "Detectors", "Domes", "Filter Wheels", "Focusers", "Spectrographs", "Telescopes", "Weather"]

### List all drivers

URL | Method | Return | Format
--- | --- | --- | ---
/api/drivers | GET | Get all the drivers information

**Example:** curl http://localhost:8624/api/drivers
**Reply:** [{"name": "AAG Cloud Watcher", "label": "AAG Cloud Watcher", "skeleton": null, "version": "1.4", "binary": "indi_aagcloudwatcher", "family": "Weather", "custom": false}, {"name": "ASI EFW", "label": "ASI EFW", "skeleton": null, "version": "0.9", "binary": "indi_asi_wheel", "family": "Filter Wheels", "custom": false}.....]

### Start specific driver

URL | Method | Return | Format
--- | --- | --- | ---
/api/drivers/start/\<label>| POST | Start a specific driver if INDI server is already running.

All spaces must be encoded with %20 as per URI standards.

**Example:** http://localhost:8624/api/drivers/start/Pegasus%20UPB
**Reply:** None

### Stop specific driver

URL | Method | Return | Format
--- | --- | --- | ---
/api/drivers/stop/\<label>| POST | Stop a specific driver if INDI server is already running.

All spaces must be encoded with %20 as per URI standards.

**Example:** http://localhost:8624/api/drivers/stop/Pegasus%20UPB
**Reply:** None

### Restart specific driver

URL | Method | Return | Format
--- | --- | --- | ---
/api/drivers/restart/\<label>| POST | Restart a specific driver if INDI server is already running.

All spaces must be encoded with %20 as per URI standards.

**Example:** http://localhost:8624/api/drivers/restart/Pegasus%20UPB
**Reply:** None

## INDIHUB Agent Methods

### Change indihub-agent current mode

You can launch [indihub-agent](https://github.com/indihub-space/agent) in three different modes or stop it with using this endpoint.

URL | Method | Return | Format
--- | --- | --- | ---
/api/indihub/mode/\<mode>| POST | Change indihub-agent to run in a specific mode if INDI server is already running.

Possible values for URI-parameter `mode`:
- `solo`
- `share`
- `robotic`
- or `off` to stop indihub-agent process

**Example:** curl -X POST /api/indihub/mode/solo
**Reply:** None

### Get indihub-agent status

URL | Method | Return | Format
--- | --- | --- | ---
/api/indihub/status | GET | Get status of `indihub-agent`

**Example:** curl /api/indihub/status

**Reply:** [{'status': 'True', 'mode': 'solo', 'active_profile': 'my-profile'}]

## System Commands

### Reboot the system 

URL | Method | Return | Format
--- | --- | --- | ---
/api/system/reboot| POST | Reboot the system on which the INDI server is running.

The driver and indi server are closed.

**Example:** http://localhost:8624/api/system/reboot
**Reply:** None

### Poweroff the system 

URL | Method | Return | Format
--- | --- | --- | ---
/api/system/poweroff| POST | powers off the system on which the INDI server is running.

The driver and indi server are closed.

**Example:** http://localhost:8624/api/system/poweroff
**Reply:** None

# Development

To run indiweb directly from the source directory make sure prerequisits are
installed and use:

```
python3 -m indiweb.main
```

# Authors

Jasem Mutlaq (mutlaqja@ikarustech.com)

Juan Menendez (juanmb@gmail.com)
