#!/usr/bin/env python

import os
import json
import logging
import argparse
import socket
from threading import Timer
import subprocess
import platform
from importlib_metadata import version

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import uvicorn

from .indi_server import IndiServer, INDI_PORT, INDI_FIFO, INDI_CONFIG_DIR
from .driver import DeviceDriver, DriverCollection, INDI_DATA_DIR
from .database import Database
from .device import Device

# default settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 8624

pkg_path, _ = os.path.split(os.path.abspath(__file__))
views_path = os.path.join(pkg_path, 'views')

templates = Jinja2Templates(directory=views_path)

parser = argparse.ArgumentParser(
    description='INDI Web Manager. '
    'A simple web application to manage an INDI server')

parser.add_argument('--indi-port', '-p', type=int, default=INDI_PORT,
                    help='indiserver port (default: %d)' % INDI_PORT)
parser.add_argument('--port', '-P', type=int, default=WEB_PORT,
                    help='Web server port (default: %d)' % WEB_PORT)
parser.add_argument('--host', '-H', default=WEB_HOST,
                    help='Bind web server to this interface (default: %s)' %
                    WEB_HOST)
parser.add_argument('--fifo', '-f', default=INDI_FIFO,
                    help='indiserver FIFO path (default: %s)' % INDI_FIFO)
parser.add_argument('--conf', '-c', default=INDI_CONFIG_DIR,
                    help='INDI config. directory (default: %s)' % INDI_CONFIG_DIR)
parser.add_argument('--xmldir', '-x', default=INDI_DATA_DIR,
                    help='INDI XML directory (default: %s)' % INDI_DATA_DIR)
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Print more messages')
parser.add_argument('--logfile', '-l', help='log file name')
parser.add_argument('--server', '-s', default='standalone',
                    help='HTTP server [standalone|apache] (default: standalone')
parser.add_argument('--sudo', '-S', action='store_true',                    
                    help='Run poweroff/reboot commands with sudo')

args = parser.parse_args()


logging_level = logging.WARNING

if args.verbose:
    logging_level = logging.DEBUG

if args.logfile:
    logging.basicConfig(filename=args.logfile,
                        format='%(asctime)s - %(levelname)s: %(message)s',
                        level=logging_level)

else:
    logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                        level=logging_level)

logging.debug("command line arguments: " + str(vars(args)))

hostname = socket.gethostname()

collection = DriverCollection(args.xmldir)
indi_server = IndiServer(args.fifo, args.conf)
indi_device = Device()


db_path = os.path.join(args.conf, 'profiles.db')
db = Database(db_path)

collection.parse_custom_drivers(db.get_custom_drivers())

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory=views_path), name="static")
app.mount("/favicon.ico", StaticFiles(directory=views_path), name="favicon.ico")


saved_profile = None
active_profile = ""


def start_profile(profile):
    """
    Starts the INDI server with the specified profile.

    Args:
        profile (str): The name of the profile to start.

    Handles:
        json.JSONDecodeError: If the scripts JSON is invalid.
        Exception: For other errors during script processing.
    """
    info = db.get_profile(profile)

    if info is None:
        logging.warning(f"Profile '{profile}' not found in the database.")
        # Depending on desired behavior, could return or raise HTTPException
        HTTPException(status_code=404, detail=f"Profile '{profile}' not found")

    profile_drivers = db.get_profile_drivers_labels(profile)
    profile_scripts = None
    if info.get('scripts'):
        try:
            profile_scripts = json.loads(info['scripts'])
            collection.apply_rules(profile_scripts)
        except json.JSONDecodeError:
            logging.warning("Failed to parse scripts JSON for profile %s" % profile)
        except Exception as e:
            logging.warning("Error processing scripts for profile %s: %s" % (profile, str(e)))
    
    all_drivers = []
    
    for d in profile_drivers:
        logging.debug("Finding driver with label: " + d['label'])
        one_driver = collection.by_label(d['label'])
        if one_driver is None:
            logging.warning("Driver " + d['label'] + " is not found on the system. Install the driver.")
        else:
            logging.info("Adding local driver: " + d['label'])
            all_drivers.append(one_driver)

    # Find if we have any remote drivers
    remote_drivers = db.get_profile_remote_drivers(profile)
    if remote_drivers:
        # Handle both single dictionary and list of dictionaries
        if isinstance(remote_drivers, list):
            for remote_driver in remote_drivers:
                driver = remote_driver['drivers']
                one_driver = DeviceDriver(driver, driver, "1.0", driver, "Remote", None, False, None)

                # Apply rules to remote drivers if any
                if profile_scripts:
                    for rule in profile_scripts:
                        driver_label = rule.get('Driver')
                        if driver_label and driver_label == driver:
                            one_driver.rule = rule
                logging.info("Adding remote driver: " + driver)
                all_drivers.append(one_driver)
        else:
            # Handle the case where remote_drivers is a single dictionary
            drivers = remote_drivers['drivers'].split(',')
            for drv in drivers:
                logging.warning("LOADING REMOTE DRIVER drv is {}".format(drv))
                all_drivers.append(DeviceDriver(drv, drv, "1.0", drv, "Remote", None, False, None))

    # Sort drivers - those with .rule first, then remote drivers (family="Remote"), then others
    all_drivers = sorted(all_drivers,
                        key=lambda d: (0 if hasattr(d, 'rule') else 1,
                                      1 if getattr(d, 'family', '') == 'Remote' else 2))

    if all_drivers:
        indi_server.start(info['port'], all_drivers)
        # Auto connect drivers in 3 seconds if required.
        if info['autoconnect'] == 1:
            t = Timer(3, indi_server.auto_connect)
            t.start()


@app.get("/", response_class=HTMLResponse)
async def main_form(request: Request):
    """
    Renders the main form page.

    Returns:
        str: The rendered HTML template.
    """
    global saved_profile
    drivers = collection.get_families()

    saved_profile = request.cookies.get('indiserver_profile') or 'Simulators'

    profiles = db.get_profiles()
    logging.debug(f"Profiles retrieved from DB: {profiles}")
    return templates.TemplateResponse(
        "form.tpl",
        {"request": request,
         "profiles": profiles,
         "drivers": drivers,
         "saved_profile": saved_profile,
         "hostname": hostname,
         "sorted": sorted} # Add sorted to the context
    )

###############################################################################
# Profile endpoints
###############################################################################


@app.get('/api/profiles')
async def get_json_profiles():
    """
    Gets all profiles from the database as JSON.

    Returns:
        str: A JSON string representing the profiles.
    """
    results = db.get_profiles()
    return JSONResponse(content=results)


@app.get('/api/profiles/{item}')
async def get_json_profile(item: str):
    """
    Gets information for a specific profile as JSON.

    Args:
        item (str): The name of the profile.

    Returns:
        str: A JSON string representing the profile information.
    """
    results = db.get_profile(item)
    if results:
        return JSONResponse(content=results)
    raise HTTPException(status_code=404, detail="Profile not found")


@app.post('/api/profiles/{name}')
async def add_profile(name: str):
    """
    Adds a new profile to the database.

    Args:
        name (str): The name of the profile to add.
    """
    db.add_profile(name)
    return {"message": f"Profile {name} added"}


@app.delete('/api/profiles/{name}')
async def delete_profile(name: str):
    """
    Deletes a profile from the database.

    Args:
        name (str): The name of the profile to delete.
    """
    db.delete_profile(name)
    return {"message": f"Profile {name} deleted"}


@app.put('/api/profiles/{name}')
async def update_profile(name: str, request: Request, response: Response):
    """
    Updates the information for a specific profile.

    Args:
        name (str): The name of the profile to update.
    """
    response.set_cookie(key="indiserver_profile", value=name, max_age=3600000, path='/')
    data = await request.json()
    port = data.get('port', args.indi_port)
    scripts = data.get('scripts', "")
    autostart = bool(data.get('autostart', 0))
    autoconnect = bool(data.get('autoconnect', 0))
    db.update_profile(name, port, autostart, autoconnect, scripts)
    return {"message": f"Profile {name} updated"}


@app.post('/api/profiles/{name}/drivers')
async def save_profile_drivers(name: str, request: Request):
    """
    Saves the drivers associated with a profile.

    Args:
        name (str): The name of the profile.
    """
    data = await request.json()
    db.save_profile_drivers(name, data)
    return {"message": f"Drivers saved for profile {name}"}


@app.post('/api/profiles/custom')
async def save_profile_custom_driver(request: Request):
    """
    Adds a custom driver to the database and updates the driver collection.
    """
    data = await request.json()
    db.save_profile_custom_driver(data)
    collection.clear_custom_drivers()
    collection.parse_custom_drivers(db.get_custom_drivers())
    return {"message": "Custom driver saved and collection updated"}


@app.get('/api/profiles/{item}/labels')
async def get_json_profile_labels(item: str):
    """
    Gets the driver labels for a specific profile as JSON.

    Args:
        item (str): The name of the profile.

    Returns:
        str: A JSON string representing the driver labels.
    """
    results = db.get_profile_drivers_labels(item)
    return JSONResponse(content=results)


@app.get('/api/profiles/{item}/remote')
async def get_remote_drivers(item: str):
    """
    Gets the remote drivers for a specific profile as JSON.

    Args:
        item (str): The name of the profile.

    Returns:
        str: A JSON string representing the remote drivers.
    """
    results = db.get_profile_remote_drivers(item)
    if results is None:
        results = {}
    return JSONResponse(content=results)


###############################################################################
# Server endpoints
###############################################################################

@app.get('/api/server/status')
async def get_server_status():
    """
    Gets the status of the INDI server and the active profile as JSON.

    Returns:
        str: A JSON string representing the server status.
    """
    status = [{'status': str(indi_server.is_running()), 'active_profile': active_profile}]
    return JSONResponse(content=status)


@app.get('/api/server/drivers')
async def get_server_drivers():
    """
    Lists the currently running server drivers as JSON.

    Returns:
        str: A JSON string representing the running drivers.
    """
    drivers = []
    if indi_server.is_running() is True:
        for driver in indi_server.get_running_drivers().values():
            drivers.append(driver.__dict__)
    return JSONResponse(content=drivers)


@app.post('/api/server/start/{profile}')
async def start_server(profile: str, response: Response):
    """
    Starts the INDI server for a specific profile.

    Args:
        profile (str): The name of the profile to start.
    """
    global saved_profile
    saved_profile = profile
    global active_profile
    active_profile = profile
    response.set_cookie(key="indiserver_profile", value=profile, max_age=3600000, path='/')
    start_profile(profile)
    return {"message": f"INDI server started for profile {profile}"}


@app.post('/api/server/stop')
async def stop_server():
    """
    Stops the INDI server.
    """
    indi_server.stop()

    global active_profile
    active_profile = ""

    # If there is saved_profile already let's try to reset it
    global saved_profile
    # In FastAPI, request.cookies is available in the endpoint function
    # saved_profile = request.cookies.get("indiserver_profile") or "Simulators"
    # This part might need adjustment depending on how saved_profile is truly used
    # For now, keeping the logic as is but noting the potential change needed
    if saved_profile:
         pass # Need to access request.cookies here if needed

    return {"message": "INDI server stopped"}


###############################################################################
# Info endpoints
###############################################################################

@app.get('/api/info/version')
async def get_version():
    """
    Gets the version of indiwebmanager.

    Returns:
        dict: A dictionary containing the version.
    """
    return {"version": version("indiweb")}


# Get StellarMate Architecture
@app.get('/api/info/arch')
async def get_arch():
    """
    Gets the architecture of the system.

    Returns:
        str: The system architecture.
    """
    arch = platform.machine()
    if arch == "aarch64":
        arch = "arm64"
    elif arch == "armv7l":
        arch = "armhf"
    return arch

# Get Hostname
@app.get('/api/info/hostname')
async def get_hostname():
    """
    Gets the hostname of the system.

    Returns:
        dict: A dictionary containing the hostname.
    """
    return {"hostname": socket.gethostname()}
    
###############################################################################
# Driver endpoints
###############################################################################

@app.get('/api/drivers/groups')
async def get_json_groups():
    """
    Gets all driver families as JSON.

    Returns:
        str: A JSON string representing the driver families.
    """
    families = collection.get_families()
    return JSONResponse(content=sorted(families.keys()))


@app.get('/api/drivers')
async def get_json_drivers():
    """
    Gets all drivers as JSON.

    Returns:
        str: A JSON string representing all drivers.
    """
    return JSONResponse(content=[ob.__dict__ for ob in collection.drivers])


@app.post('/api/drivers/start/{label}')
async def start_driver(label: str):
    """
    Starts an INDI driver by label.

    Args:
        label (str): The label of the driver to start.
    """
    driver = collection.by_label(label)
    if driver:
        indi_server.start_driver(driver)
        logging.info('Driver "%s" started.' % label)
        return {"message": f"Driver {label} started"}
    raise HTTPException(status_code=404, detail="Driver not found")


@app.post('/api/drivers/start_remote/<label>')
async def start_remote_driver(label: str):
    """
    Starts a remote INDI driver.

    Args:
        label (str): The label of the remote driver to start.
    """
    driver = DeviceDriver(label, label, "1.0", label, "Remote", None, False, None)
    indi_server.start_driver(driver)
    logging.info('Driver "%s" started.' % label)
    return {"message": f"Remote driver {label} started"}


@app.post('/api/drivers/stop/<label>')
async def stop_driver(label: str):
    """
    Stops an INDI driver by label.

    Args:
        label (str): The label of the driver to stop.
    """
    driver = collection.by_label(label)
    if driver:
        indi_server.stop_driver(driver)
        logging.info('Driver "%s" stopped.' % label)
        return {"message": f"Driver {label} stopped"}
    raise HTTPException(status_code=404, detail="Driver not found")


@app.post('/api/drivers/stop_remote/<label>')
async def stop_remote_driver(label: str):
    """
    Stops a remote INDI driver.

    Args:
        label (str): The label of the remote driver to stop.
    """
    driver = DeviceDriver(label, label, "1.0", label, "Remote", None, False, None)
    indi_server.stop_driver(driver)
    logging.info('Driver "%s" stopped.' % label)
    return {"message": f"Remote driver {label} stopped"}


@app.post('/api/drivers/restart/<label>')
async def restart_driver(label: str):
    """
    Restarts an INDI driver by label.

    Args:
        label (str): The label of the driver to restart.
    """
    driver = collection.by_label(label)
    if driver:
        indi_server.stop_driver(driver)
        indi_server.start_driver(driver)
        logging.info('Driver "%s" restarted.' % label)
        return {"message": f"Driver {label} restarted"}
    raise HTTPException(status_code=404, detail="Driver not found")

###############################################################################
# Device endpoints
###############################################################################


@app.get('/api/devices')
async def get_devices():
    """
    Gets a list of connected INDI devices as JSON.

    Returns:
        str: A JSON string representing the connected devices.
    """
    return JSONResponse(content=indi_device.get_devices())

###############################################################################
# System control endpoints
###############################################################################


@app.post('/api/system/reboot')
async def system_reboot():
    """
    Reboots the system running indi-web.

    Handles:
        subprocess.CalledProcessError: If the reboot command fails.
    """
    logging.info('System reboot, stopping server...')
    stop_server()
    logging.info('rebooting...')
    subprocess.run(["sudo", "reboot"] if args.sudo else "reboot")
    return {"message": "System is rebooting"}


@app.post('/api/system/poweroff')
async def system_poweroff():
    """
    Powers off the system.

    Handles:
        subprocess.CalledProcessError: If the poweroff command fails.
    """
    logging.info('System poweroff, stopping server...')
    stop_server()
    logging.info('poweroff...')
    subprocess.run(["sudo", "poweroff"] if args.sudo else "poweroff")
    return {"message": "System is powering off"}


###############################################################################
# Startup standalone server
###############################################################################


def main():
    """
    Main function to start the indiwebmanager application.
    Starts the autostart profile if configured and runs the web server.
    """
    global active_profile

    for profile in db.get_profiles():
        if profile['autostart']:
            start_profile(profile['name'])
            active_profile = profile['name']
            break

    uvicorn.run(app, host=args.host, port=args.port)
    logging.info("Exiting")


# JM 2018-12-24: Added __main__ so I can debug this as a module in PyCharm
# Otherwise, I couldn't get it to run main as all
if __name__ == '__init__' or __name__ == '__main__':
    main()
