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

from fastapi import FastAPI, Request, Response, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import uvicorn

from .indi_server import IndiServer, INDI_PORT, INDI_FIFO, INDI_CONFIG_DIR
from .driver import DeviceDriver, DriverCollection, INDI_DATA_DIR
from .database import Database
from .device import Device
from .indi_client import get_indi_client, start_indi_client, stop_indi_client
from .evt_indi_client import get_websocket_manager, create_indi_event_listener

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

app = FastAPI(title="INDI Web Manager", version="1.0.0")

# Serve static files
app.mount("/static", StaticFiles(directory=views_path), name="static")


saved_profile = None
active_profile = ""
evt_listener_initialized = False


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


@app.get("/", response_class=HTMLResponse, tags=["Web Interface"])
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


@app.get('/api/profiles', tags=["Profiles"])
async def get_json_profiles():
    """
    Gets all profiles from the database as JSON.

    Returns:
        str: A JSON string representing the profiles.
    """
    results = db.get_profiles()
    return JSONResponse(content=results)


@app.get('/api/profiles/{item}', tags=["Profiles"])
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


@app.post('/api/profiles/{name}', tags=["Profiles"])
async def add_profile(name: str):
    """
    Adds a new profile to the database.

    Args:
        name (str): The name of the profile to add.
    """
    db.add_profile(name)
    return {"message": f"Profile {name} added"}


@app.delete('/api/profiles/{name}', tags=["Profiles"])
async def delete_profile(name: str):
    """
    Deletes a profile from the database.

    Args:
        name (str): The name of the profile to delete.
    """
    db.delete_profile(name)
    return {"message": f"Profile {name} deleted"}


@app.put('/api/profiles/{name}', tags=["Profiles"])
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


@app.post('/api/profiles/{name}/drivers', tags=["Profiles"])
async def save_profile_drivers(name: str, request: Request):
    """
    Saves the drivers associated with a profile.

    Args:
        name (str): The name of the profile.
    """
    data = await request.json()
    db.save_profile_drivers(name, data)
    return {"message": f"Drivers saved for profile {name}"}


@app.post('/api/profiles/custom/add', tags=["Profiles"])
async def save_profile_custom_driver(request: Request):
    """
    Adds a custom driver to the database and updates the driver collection.
    """
    data = await request.json()
    db.save_profile_custom_driver(data)
    collection.clear_custom_drivers()
    collection.parse_custom_drivers(db.get_custom_drivers())
    return {"message": "Custom driver saved and collection updated"}


@app.get('/api/profiles/{item}/labels', tags=["Profiles"])
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


@app.get('/api/profiles/{item}/remote', tags=["Profiles"])
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

@app.get('/api/server/status', tags=["Server"])
async def get_server_status():
    """
    Gets the status of the INDI server and the active profile as JSON.

    Returns:
        str: A JSON string representing the server status.
    """
    status = [{'status': str(indi_server.is_running()), 'active_profile': active_profile}]
    return JSONResponse(content=status)


@app.get('/api/server/drivers', tags=["Server"])
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


@app.post('/api/server/start/{profile}', tags=["Server"])
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
    global evt_listener_initialized
    response.set_cookie(key="indiserver_profile", value=profile, max_age=3600000, path='/')
    start_profile(profile)

    # Start INDI client connection after a short delay
    import asyncio
    async def start_client():
        await asyncio.sleep(3)  # Wait for server to start
        profile_info = db.get_profile(profile)
        port = profile_info.get('port', 7624) if profile_info else 7624
        start_indi_client('localhost', port)

        # Initialize event listener for WebSocket updates
        global evt_listener_initialized
        if not evt_listener_initialized:
            indi_client = get_indi_client()
            event_loop = asyncio.get_event_loop()
            create_indi_event_listener(indi_client, event_loop)
            evt_listener_initialized = True
            logging.info("INDI event listener initialized for WebSocket updates")

    asyncio.create_task(start_client())

    return {"message": f"INDI server started for profile {profile}"}


@app.post('/api/server/stop', tags=["Server"])
async def stop_server():
    """
    Stops the INDI server.
    """
    indi_server.stop()
    stop_indi_client()  # Also stop the INDI client

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

@app.get('/api/info/version', tags=["Info"])
async def get_version():
    """
    Gets the version of indiwebmanager.

    Returns:
        dict: A dictionary containing the version.
    """
    return {"version": version("indiweb")}


# Get StellarMate Architecture
@app.get('/api/info/arch', tags=["Info"])
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
@app.get('/api/info/hostname', tags=["Info"])
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

@app.get('/api/drivers/groups', tags=["Drivers"])
async def get_json_groups():
    """
    Gets all driver families as JSON.

    Returns:
        str: A JSON string representing the driver families.
    """
    families = collection.get_families()
    return JSONResponse(content=sorted(families.keys()))


@app.get('/api/drivers', tags=["Drivers"])
async def get_json_drivers():
    """
    Gets all drivers as JSON.

    Returns:
        str: A JSON string representing all drivers.
    """
    return JSONResponse(content=[ob.__dict__ for ob in collection.drivers])


@app.post('/api/drivers/start/{label}', tags=["Drivers"])
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


@app.post('/api/drivers/start_remote/{label}', tags=["Drivers"])
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


@app.post('/api/drivers/stop/{label}', tags=["Drivers"])
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


@app.post('/api/drivers/stop_remote/{label}', tags=["Drivers"])
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


@app.post('/api/drivers/restart/{label}', tags=["Drivers"])
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


@app.get('/device/{device_name}', response_class=HTMLResponse, tags=["Web Interface"])
async def device_control_panel(request: Request, device_name: str):
    """
    Renders the device control panel page.

    Args:
        device_name (str): The name of the device to control.

    Returns:
        str: The rendered HTML template.
    """
    try:
        logging.info(f"Loading device control panel for: {device_name}")

        # Check if template file exists
        import os
        template_path = os.path.join(views_path, "device_control.tpl")
        if not os.path.exists(template_path):
            raise HTTPException(status_code=500, detail=f"Template not found: {template_path}")

        return templates.TemplateResponse(
            "device_control.tpl",
            {"request": request, "device_name": device_name}
        )
    except Exception as e:
        logging.error(f"Error loading device control panel for {device_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading device control panel: {str(e)}")


@app.get('/api/devices', tags=["Devices"])
async def get_devices():
    """
    Retrieve all currently connected INDI devices.

    This endpoint returns a list of all devices currently connected
    to the INDI server.

    Returns:
        list: Device names as an array of strings.

    Example response:
    ```json
    [
        "CCD Simulator",
        "Telescope Simulator",
        "..."
    ]
    ```

    Raises:
        503: Service unavailable if INDI server is not running
    """
    # Try INDI client first, fallback to old method
    client = get_indi_client()
    if client.is_connected():
        devices = client.get_devices()
        return JSONResponse(content=devices)
    else:
        return JSONResponse(content=indi_device.get_devices())


@app.get('/api/devices/{device_name}/structure', tags=["Devices"])
async def get_device_structure(device_name: str):
    """
    Retrieve the complete property structure for a specific INDI device.

    This endpoint provides the hierarchical structure of all properties available
    on the specified device, organized by property groups. This is essential for
    building dynamic user interfaces that can adapt to different device types.

    Args:
        device_name (str): The exact name of the INDI device (case-sensitive)

    Returns:
        dict: Nested dictionary containing the complete device structure:
            - Top level: property group names
            - Second level: property names within each group
            - Third level: property metadata and element definitions

    Example response:
    ```json
    {
        "Main Control": {
            "CONNECTION": {
                "type": "Switch",
                "perm": "rw",
                "state": "Ok",
                "elements": {
                    "CONNECT": {"value": "On", "label": "Connect", ...},
                    "DISCONNECT": {"value": "Off", "label": "Disconnect", ...}
                },
                ...
            }
        },
        ...
    }
    ```

    Raises:
        404: Device not found or not available
        503: INDI server not running or client not connected
    """
    global evt_listener_initialized
    client = get_indi_client()
    if not client.is_connected():
        # Try to connect to INDI server
        if indi_server.is_running():
            port = 7624  # Default INDI port
            profiles = db.get_profiles()
            for profile in profiles:
                if profile.get('name') == active_profile:
                    port = profile.get('port', 7624)
                    break

            if not start_indi_client('localhost', port):
                raise HTTPException(status_code=503, detail="Cannot connect to INDI server")

            # Initialize event listener for WebSocket updates if not already done
            if not evt_listener_initialized:
                import asyncio
                event_loop = asyncio.get_event_loop()
                create_indi_event_listener(client, event_loop)
                evt_listener_initialized = True
                logging.info("INDI event listener initialized for WebSocket updates (via structure endpoint)")
        else:
            raise HTTPException(status_code=503, detail="INDI server is not running")

    # Wait for device to be available
    if not client.wait_for_device(device_name, timeout=3):
        raise HTTPException(status_code=404, detail=f"Device '{device_name}' not found or not available")

    structure = client.get_device_structure(device_name)
    if not structure:
        raise HTTPException(status_code=404, detail="Device found but no properties available yet. Try refreshing.")

    return JSONResponse(content=structure)


@app.get('/api/devices/{device_name}/poll', tags=["Devices"])
async def poll_device_properties(device_name: str, since: float = None):
    """
    Poll for device properties that have changed since a specific timestamp.

    This endpoint enables real-time monitoring by returning only the
    properties that have been modified since the last check. 

    Args:
        device_name (str): The exact name of the INDI device to monitor
        since (float, optional): Unix timestamp (seconds since epoch) to check
                                changes from. If omitted, returns all dirty properties.

    Returns:
        list: Array of property names that have changed since the specified timestamp

    Example response:
    ```json
    [
        "EQUATORIAL_EOD_COORD"
    ]
    ```

    Example request:
    ```
    GET /api/devices/CCD Simulator/poll?since=1641024000.5
    ```

    Raises:
        503: INDI client not connected to server
    """
    client = get_indi_client()
    if not client.is_connected():
        raise HTTPException(status_code=503, detail="INDI client not connected")

    dirty_props = client.get_dirty_properties(device_name, since)
    return JSONResponse(content=dirty_props)


@app.post('/api/devices/{device_name}/properties/batch', tags=["Devices"])
async def get_changed_properties(device_name: str, request: Request):
    """
    Retrieve current values for multiple properties in a single request.

    This batch endpoint allows efficient retrieval of multiple property values
    at once, reducing the number of HTTP requests needed for UI updates.
    Particularly useful when updating dashboard displays or status panels.

    Args:
        device_name (str): The exact name of the INDI device
        request: JSON request body containing the list of property names to fetch

    Request body schema:
    ```json
    {
        "properties": ["property1", "property2", "property3"]
    }
    ```

    Returns:
        dict: Current values for the specified properties, keyed by property name

    Example request:
    ```json
    {
        "properties": ["CCD_TEMPERATURE", "CCD_EXPOSURE"]
    }
    ```

    Example response:
    ```json
    {
        "CCD_TEMPERATURE": {
            "type": "Number",
            "state": "Ok",
            "elements": {
                "CCD_TEMPERATURE_VALUE": {"value": -10.5}
            }
        },
        "CCD_EXPOSURE": {
            "type": "Number",
            "state": "Busy",
            "elements": {
                "CCD_EXPOSURE_VALUE": {"value": 30.0}
            }
        }
    }
    ```

    Raises:
        400: No property names provided in request,
        503: INDI client not connected to server
    """
    client = get_indi_client()
    if not client.is_connected():
        raise HTTPException(status_code=503, detail="INDI client not connected")

    data = await request.json()
    property_names = data.get('properties', [])

    if not property_names:
        raise HTTPException(status_code=400, detail="No property names provided")

    properties = client.get_changed_properties(device_name, property_names)
    return JSONResponse(content=properties)


@app.get('/api/devices/{device_name}/groups', tags=["Devices"])
async def get_device_groups(device_name: str):
    """
    Retrieve property groups and their associated properties for a device.

    This endpoint provides a simplified view of device properties organized by
    functional groups (e.g., "Main Control", "Image Settings", "Cooler").
    Useful for creating tabbed interfaces or organizing device controls.

    Args:
        device_name (str): The exact name of the INDI device

    Returns:
        dict: Property groups with arrays of property names in each group

    Example response:
    ```json
    {
        "Main Control": [
            "CONNECTION",
            "ON_COORD_SET",
            "EQUATORIAL_EOD_COORD",
            ...
        ],
        "Connection": [
            "DRIVER_INFO",
            CONNECTION_MODE",
            ...
        ],
        ...
    }
    ```

    Raises:
        404: Device not found
        503: INDI client not connected to server
    """
    client = get_indi_client()
    if not client.is_connected():
        raise HTTPException(status_code=503, detail="INDI client not connected")

    properties = client.get_device_properties(device_name)
    if not properties:
        raise HTTPException(status_code=404, detail="Device not found")

    # Group properties by group name
    groups = {}
    for prop_name, prop_data in properties.items():
        group_name = prop_data.get('group', 'Main')
        if group_name not in groups:
            groups[group_name] = []
        groups[group_name].append(prop_name)

    return JSONResponse(content=groups)


@app.get('/api/devices/{device_name}/properties/{property_name}', tags=["Devices"])
async def get_device_property(device_name: str, property_name: str):
    """
    Retrieve detailed information for a specific device property.

    This endpoint provides metadata and current values for a single
    property, including type information, permissions, state, and all elements
    with their current values and constraints.

    Args:
        device_name (str): The exact name of the INDI device
        property_name (str): The exact name of the property to retrieve

    Returns:
        dict: Complete property information including metadata and current values

    Example response for a Number property:
    ```json
    {
        "name": "TELESCOPE_TRACK_RATE",
        "label": "Track Rates",
        "group": "Main Control",
        "type": "number",
        "state": "idle",
        "perm": "rw",
        "rule": null,
        "elements": {
            "TRACK_RATE_RA": {
            "name": "TRACK_RATE_RA",
            "label": "RA (arcsecs/s)",
            "value": "15.041067178670204",
            "min": "-16384.0",
            "max": "16384.0",
            "step": "1e-06",
            "format": "%.6f",
            "formatted_value": "15.041067"
        },
        ...
    }
    ```
    
    Example response for a Switch property:
    ```json
	{
        "name": "CONNECTION",
        "label": "Connection",
        "group": "Main Control",
        "type": "switch",
        "state": "ok",
        "perm": "rw",
        "rule": "OneOfMany",
        "elements": {
            "CONNECT": { "name": "CONNECT", "label": "Connect", "value": "On" },
            "DISCONNECT": { "name": "DISCONNECT", "label": "Disconnect", "value": "Off" 
        },
        "device": "Telescope Simulator"
    }
    ```

    Raises:
        404: Property not found on the specified device
        503: INDI client not connected to server
    """
    client = get_indi_client()
    if not client.is_connected():
        raise HTTPException(status_code=503, detail="INDI client not connected")

    property_data = client.get_property(device_name, property_name)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property not found")

    return JSONResponse(content=property_data)


@app.post('/api/devices/{device_name}/properties/{property_name}/set', tags=["Devices"])
async def set_device_property(device_name: str, property_name: str, request: Request):
    """
    Set new values for elements within a specific device property.

    This endpoint allows modification of property element values, such as changing
    exposure time, connecting/disconnecting devices, or adjusting temperature setpoints.
    The property must be writable (permission 'rw' or 'wo') for the operation to succeed.

    Args:
        device_name (str): The exact name of the INDI device
        property_name (str): The exact name of the property to modify
        request: JSON request body containing element values to set

    Request body schema:
    ```json
    {
        "elements": {
            "element_name1": "value1",
            "element_name2": "value2"
        }
    }
    ```

    Returns:
        dict: Operation result with success status and details

    Example request (setting exposure time):
    ```json
    {
        "elements": {
            "CCD_EXPOSURE_VALUE": 30.0
        }
    }
    ```

    Example request (connecting device):
    ```json
    {
        "elements": {
            "CONNECT": "On",
            "DISCONNECT": "Off"
        }
    }
    ```

    Example success response:
    ```json
    {
        "success": true,
        "message": "Property set successfully",
        "device": "CCD Simulator",
        "property": "CCD_EXPOSURE",
        "elements": {
            "CCD_EXPOSURE_VALUE": 30.0
        }
    }
    ```

    Example error response:
    ```json
    {
        "success": false,
        "error": "Property is read-only",
        "error_type": "permission_denied"
    }
    ```

    Raises:
        400: No element values provided or invalid values
        404: Property or element not found
        422: Property is read-only or validation failed
        503: INDI client not connected to server
    """
    client = get_indi_client()
    if not client.is_connected():
        raise HTTPException(status_code=503, detail="INDI client not connected")

    try:
        data = await request.json()
        elements = data.get('elements', {})

        if not elements:
            raise HTTPException(status_code=400, detail="No element values provided")

        # Log the received values
        logging.warning(f"Setting property {device_name}.{property_name} with values: {elements}")

        # Set the property using the INDI client
        result = client.set_property(device_name, property_name, elements)

        if result['success']:
            # Success - property setting command was sent
            logging.info(f"Property {device_name}.{property_name} set successfully")
            return JSONResponse(content={
                "success": True,
                "message": result['message'],
                "device": device_name,
                "property": property_name,
                "elements": elements
            })
        else:
            # Error occurred during property setting
            error_msg = result['error']
            error_type = result.get('error_type', 'unknown_error')

            logging.error(f"Failed to set property {device_name}.{property_name}: {error_msg}")

            # Map error types to appropriate HTTP status codes
            if error_type in ['property_not_found', 'element_not_found']:
                status_code = 404
            elif error_type == 'permission_denied':
                status_code = 403
            elif error_type in ['invalid_value', 'unsupported_type']:
                status_code = 400
            elif error_type == 'communication_error':
                status_code = 503
            else:
                status_code = 500

            raise HTTPException(status_code=status_code, detail=error_msg)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except HTTPException:
        # Re-raise HTTP exceptions (these are our expected errors)
        raise
    except Exception as e:
        logging.error(f"Unexpected error setting property {device_name}.{property_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



###############################################################################
# WebSocket endpoints
###############################################################################

@app.websocket('/evt_device/{device_name}')
async def evt_device_websocket(websocket: WebSocket, device_name: str):
    """
    WebSocket endpoint for real-time device property updates.

    This endpoint provides a persistent connection for receiving real-time updates
    from INDI devices. Events are pushed to clients as soon as properties change,
    eliminating the need for polling.

    Args:
        websocket: The WebSocket connection
        device_name: The exact name of the INDI device to monitor

    Events sent to client:
        - property_updated: When a property value changes
        - property_defined: When a new property is created
        - property_deleted: When a property is removed
        - message: When the device sends a message

    Example event:
    ```json
    {
        "event": "property_updated",
        "device": "CCD Simulator",
        "data": {
            "name": "CCD_TEMPERATURE",
            "type": "number",
            "state": "ok",
            "elements": {...}
        }
    }
    ```
    """
    manager = get_websocket_manager()
    await manager.connect(websocket, device_name)

    try:
        # Keep the connection alive and listen for client messages
        while True:
            # Wait for any message from client (used for keepalive)
            data = await websocket.receive_text()
            # Echo back for keepalive confirmation
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for device: {device_name}")
    except Exception as e:
        logging.error(f"WebSocket error for device {device_name}: {e}")
    finally:
        await manager.disconnect(websocket, device_name)


###############################################################################
# System control endpoints
###############################################################################


@app.post('/api/system/reboot', tags=["System"])
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


@app.post('/api/system/poweroff', tags=["System"])
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
