"""Route handlers for the INDI Web Manager application."""

import asyncio
import json
import logging
import platform
import socket
import subprocess
from threading import Timer
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from importlib_metadata import version

from .database import Database
from .device import Device
from .driver import DeviceDriver, DriverCollection
from .indi_server import IndiServer
from .state import AppState

router = APIRouter()


# --- Dependency injection ---


def get_state(request: Request) -> AppState:
    """Extract typed app state from request. Single cast at framework boundary."""
    return cast(AppState, request.app.state)


def get_state_ws(websocket: WebSocket) -> AppState:
    """Extract typed app state from WebSocket."""
    return cast(AppState, websocket.app.state)


def get_db(request: Request) -> Database:
    state: AppState = get_state(request)
    return state.db


def get_indi_server(request: Request) -> IndiServer:
    state: AppState = get_state(request)
    return state.indi_server


def get_collection(request: Request) -> DriverCollection:
    state: AppState = get_state(request)
    return state.collection


def get_indi_device(request: Request) -> Device:
    state: AppState = get_state(request)
    return state.indi_device


def get_args(request: Request):
    return get_state(request).args


# --- Profile startup logic ---


def start_profile(state: AppState, profile: str) -> None:
    """
    Starts the INDI server with the specified profile.

    Args:
        state: Typed app state with db, collection, indi_server.
        profile: The name of the profile to start.

    Handles:
        json.JSONDecodeError: If the scripts JSON is invalid.
        Exception: For other errors during script processing.
    """
    db = state.db
    collection = state.collection
    indi_server = state.indi_server

    info = db.get_profile(profile)

    if info is None:
        logging.warning(f"Profile '{profile}' not found in the database.")
        raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")

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


# --- Web Interface ---


@router.get("/", response_class=HTMLResponse, tags=["Web Interface"])
async def main_form(request: Request,
                    db: Database = Depends(get_db),
                    collection: DriverCollection = Depends(get_collection),
                    state: AppState = Depends(get_state)):
    """Renders the main form page."""
    state.saved_profile = request.cookies.get('indiserver_profile') or 'Simulators'
    drivers = collection.get_families()
    profiles = db.get_profiles()
    logging.debug(f"Profiles retrieved from DB: {profiles}")
    return state.templates.TemplateResponse(
        request,
        "form.tpl",
        {"profiles": profiles,
         "drivers": drivers,
         "saved_profile": state.saved_profile,
         "hostname": state.hostname,
         "sorted": sorted}
    )


# --- Profiles ---


@router.get('/api/profiles', tags=["Profiles"])
async def get_json_profiles(db: Database = Depends(get_db)):
    """Gets all profiles from the database as JSON."""
    results = db.get_profiles()
    return JSONResponse(content=results)


@router.get('/api/profiles/{item}', tags=["Profiles"])
async def get_json_profile(item: str, db: Database = Depends(get_db)):
    """Gets information for a specific profile as JSON."""
    results = db.get_profile(item)
    if results:
        return JSONResponse(content=results)
    raise HTTPException(status_code=404, detail="Profile not found")


@router.post('/api/profiles/{name}', tags=["Profiles"])
async def add_profile(name: str, db: Database = Depends(get_db)):
    """Adds a new profile to the database."""
    db.add_profile(name)
    return {"message": f"Profile {name} added"}


@router.delete('/api/profiles/{name}', tags=["Profiles"])
async def delete_profile(name: str, db: Database = Depends(get_db)):
    """Deletes a profile from the database."""
    db.delete_profile(name)
    return {"message": f"Profile {name} deleted"}


@router.put('/api/profiles/{name}', tags=["Profiles"])
async def update_profile(request: Request, response: Response, name: str,
                         db: Database = Depends(get_db),
                         args=Depends(get_args)):
    """Updates the information for a specific profile."""
    response.set_cookie(key="indiserver_profile", value=name, max_age=3600000, path='/')
    data = await request.json()
    port = data.get('port', args.indi_port)
    scripts = data.get('scripts', "")
    autostart = bool(data.get('autostart', 0))
    autoconnect = bool(data.get('autoconnect', 0))
    db.update_profile(name, port, autostart, autoconnect, scripts)
    return {"message": f"Profile {name} updated"}


@router.post('/api/profiles/{name}/drivers', tags=["Profiles"])
async def save_profile_drivers(request: Request, name: str, db: Database = Depends(get_db)):
    """Saves the drivers associated with a profile."""
    data = await request.json()
    db.save_profile_drivers(name, data)
    return {"message": f"Drivers saved for profile {name}"}


@router.post('/api/profiles/custom/add', tags=["Profiles"])
async def save_profile_custom_driver(request: Request,
                                     db: Database = Depends(get_db),
                                     collection: DriverCollection = Depends(get_collection)):
    """Adds a custom driver to the database and updates the driver collection."""
    data = await request.json()
    db.save_profile_custom_driver(data)
    collection.clear_custom_drivers()
    collection.parse_custom_drivers(db.get_custom_drivers())
    return {"message": "Custom driver saved and collection updated"}


@router.get('/api/profiles/{item}/labels', tags=["Profiles"])
async def get_json_profile_labels(item: str, db: Database = Depends(get_db)):
    """Gets the driver labels for a specific profile as JSON."""
    results = db.get_profile_drivers_labels(item)
    return JSONResponse(content=results)


@router.get('/api/profiles/{item}/remote', tags=["Profiles"])
async def get_remote_drivers(item: str, db: Database = Depends(get_db)):
    """Gets the remote drivers for a specific profile as JSON."""
    results = db.get_profile_remote_drivers(item)
    if results and isinstance(results, list) and len(results) > 0:
        return JSONResponse(content=results[0])
    return JSONResponse(content={})


# --- Server ---


@router.get('/api/server/status', tags=["Server"])
async def get_server_status(indi_server: IndiServer = Depends(get_indi_server),
                            state: AppState = Depends(get_state)):
    """Gets the status of the INDI server and the active profile as JSON."""
    status = [{'status': str(indi_server.is_running()), 'active_profile': state.active_profile}]
    return JSONResponse(content=status)


@router.get('/api/server/drivers', tags=["Server"])
async def get_server_drivers(indi_server: IndiServer = Depends(get_indi_server)):
    """Lists the currently running server drivers as JSON."""
    drivers = []
    if indi_server.is_running() is True:
        for driver in indi_server.get_running_drivers().values():
            drivers.append(driver.__dict__)
    return JSONResponse(content=drivers)


@router.post('/api/server/start/{profile}', tags=["Server"])
async def start_server(response: Response, profile: str,
                       indi_server: IndiServer = Depends(get_indi_server),
                       state: AppState = Depends(get_state)):
    """Starts the INDI server for a specific profile."""
    state.saved_profile = profile
    state.active_profile = profile
    response.set_cookie(key="indiserver_profile", value=profile, max_age=3600000, path='/')
    start_profile(state, profile)
    # Wait for driver starter thread so getActiveDrivers sees all drivers when frontend polls
    await asyncio.to_thread(indi_server.wait_for_drivers_started, 5)
    return {"message": f"INDI server started for profile {profile}"}


@router.post('/api/server/stop', tags=["Server"])
async def stop_server(request: Request):
    """Stops the INDI server."""
    state = get_state(request)
    state.indi_server.stop()
    state.active_profile = ""
    return {"message": "INDI server stopped"}


# --- Info ---


@router.get('/api/info/version', tags=["Info"])
async def get_version():
    """Gets the version of indiwebmanager."""
    return {"version": version("indiweb")}


@router.get('/api/info/arch', tags=["Info"])
async def get_arch():
    """Gets the architecture of the system."""
    arch = platform.machine()
    if arch == "aarch64":
        arch = "arm64"
    elif arch == "armv7l":
        arch = "armhf"
    return arch


@router.get('/api/info/hostname', tags=["Info"])
async def get_hostname():
    """Gets the hostname of the system."""
    return {"hostname": socket.gethostname()}


# --- Drivers ---


@router.get('/api/drivers/groups', tags=["Drivers"])
async def get_json_groups(collection: DriverCollection = Depends(get_collection)):
    """Gets all driver families as JSON."""
    families = collection.get_families()
    return JSONResponse(content=sorted(families.keys()))


@router.get('/api/drivers', tags=["Drivers"])
async def get_json_drivers(collection: DriverCollection = Depends(get_collection)):
    """Gets all drivers as JSON."""
    return JSONResponse(content=[ob.__dict__ for ob in collection.drivers])


@router.post('/api/drivers/start/{label}', tags=["Drivers"])
async def start_driver(label: str,
                      collection: DriverCollection = Depends(get_collection),
                      indi_server: IndiServer = Depends(get_indi_server)):
    """Starts an INDI driver by label."""
    driver = collection.by_label(label)
    if driver:
        indi_server.start_driver(driver)
        logging.info('Driver "%s" started.' % label)
        return {"message": f"Driver {label} started"}
    raise HTTPException(status_code=404, detail="Driver not found")


@router.post('/api/drivers/start_remote/{label}', tags=["Drivers"])
async def start_remote_driver(label: str,
                              indi_server: IndiServer = Depends(get_indi_server)):
    """Starts a remote INDI driver."""
    driver = DeviceDriver(label, label, "1.0", label, "Remote", None, False, None)
    indi_server.start_driver(driver)
    logging.info('Driver "%s" started.' % label)
    return {"message": f"Remote driver {label} started"}


@router.post('/api/drivers/stop/{label}', tags=["Drivers"])
async def stop_driver(label: str,
                     collection: DriverCollection = Depends(get_collection),
                     indi_server: IndiServer = Depends(get_indi_server)):
    """Stops an INDI driver by label."""
    driver = collection.by_label(label)
    if driver:
        indi_server.stop_driver(driver)
        logging.info('Driver "%s" stopped.' % label)
        return {"message": f"Driver {label} stopped"}
    raise HTTPException(status_code=404, detail="Driver not found")


@router.post('/api/drivers/stop_remote/{label}', tags=["Drivers"])
async def stop_remote_driver(label: str,
                             indi_server: IndiServer = Depends(get_indi_server)):
    """Stops a remote INDI driver."""
    driver = DeviceDriver(label, label, "1.0", label, "Remote", None, False, None)
    indi_server.stop_driver(driver)
    logging.info('Driver "%s" stopped.' % label)
    return {"message": f"Remote driver {label} stopped"}


@router.post('/api/drivers/restart/{label}', tags=["Drivers"])
async def restart_driver(label: str,
                         collection: DriverCollection = Depends(get_collection),
                         indi_server: IndiServer = Depends(get_indi_server)):
    """Restarts an INDI driver by label."""
    driver = collection.by_label(label)
    if driver:
        indi_server.stop_driver(driver)
        indi_server.start_driver(driver)
        logging.info('Driver "%s" restarted.' % label)
        return {"message": f"Driver {label} restarted"}
    raise HTTPException(status_code=404, detail="Driver not found")


# --- Devices ---


@router.get('/api/devices', tags=["Devices"])
async def get_devices(indi_device: Device = Depends(get_indi_device)):
    """Gets a list of connected INDI devices as JSON."""
    return JSONResponse(content=indi_device.get_devices())


# --- System ---


@router.post('/api/system/reboot', tags=["System"])
async def system_reboot(request: Request, args=Depends(get_args)):
    """Reboots the system running indi-web."""
    logging.info('System reboot, stopping server...')
    await stop_server(request)
    logging.info('rebooting...')
    sudo = args.sudo
    subprocess.run(["sudo", "reboot"] if sudo else ["reboot"])
    return {"message": "System is rebooting"}


@router.post('/api/system/poweroff', tags=["System"])
async def system_poweroff(request: Request, args=Depends(get_args)):
    """Powers off the system."""
    logging.info('System poweroff, stopping server...')
    await stop_server(request)
    logging.info('poweroff...')
    sudo = args.sudo
    subprocess.run(["sudo", "poweroff"] if sudo else ["poweroff"])
    return {"message": "System is powering off"}
