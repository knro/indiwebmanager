#!/usr/bin/env python

import argparse
import asyncio
import json
import logging
import os
import platform
import socket
import subprocess
from threading import Timer

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from importlib_metadata import version

from . import __version__
from .database import Database
from .device import Device
from .driver import INDI_DATA_DIR, DeviceDriver, DriverCollection
from .indi_server import INDI_CONFIG_DIR, INDI_FIFO, INDI_PORT, IndiServer

# default settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 8624
WEB_CORS = ["http://localhost", "http://127.0.0.1"]

pkg_path, _ = os.path.split(os.path.abspath(__file__))
views_path = os.path.join(pkg_path, 'views')


def _build_parser():
    """Build and return the argument parser."""
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
    parser.add_argument('--cors', '-C', default=list(WEB_CORS), nargs='+',
                        help='Allowed domain for cross-origin policy (default: %s)' %
                        WEB_CORS)
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
    return parser


def parse_args(argv=None):
    """Parse command line arguments. If argv is None, uses sys.argv."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Add origins with current port if they don't exist
    extra_origins = []
    for origin in args.cors:
        if ":" not in origin.replace("http://", "").replace("https://", ""):
            port_origin = f"{origin}:{args.port}"
            if port_origin not in args.cors:
                extra_origins.append(port_origin)
    args.cors.extend(extra_origins)
    return args


def create_app(argv=None):
    """
    Create and configure the FastAPI application.
    If argv is None, parses from sys.argv. Call this from main() or from
    the WSGI entry point after setting sys.argv as needed.
    """
    if argv is None:
        args = parse_args()
    elif isinstance(argv, list):
        args = parse_args(argv)
    else:
        args = argv  # argv is already parsed args (e.g. from main())

    logging_level = logging.DEBUG if args.verbose else logging.WARNING
    if args.logfile:
        logging.basicConfig(filename=args.logfile,
                            format='%(asctime)s - %(levelname)s: %(message)s',
                            level=logging_level)
    else:
        logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                            level=logging_level)
    logging.debug("command line arguments: " + str(vars(args)))

    collection = DriverCollection(args.xmldir)
    indi_server = IndiServer(args.fifo, args.conf)
    indi_device = Device()
    db_path = os.path.join(args.conf, 'profiles.db')
    db = Database(db_path)
    collection.parse_custom_drivers(db.get_custom_drivers())

    templates = Jinja2Templates(directory=views_path)
    app = FastAPI(title="INDI Web Manager", version=__version__)

    # Store state in app.state for use in route handlers
    app.state.collection = collection
    app.state.db = db
    app.state.indi_server = indi_server
    app.state.indi_device = indi_device
    app.state.args = args
    app.state.templates = templates
    app.state.hostname = socket.gethostname()
    app.state.saved_profile = None
    app.state.active_profile = ""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=args.cors,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.mount("/static", StaticFiles(directory=views_path), name="static")
    app.mount("/favicon.ico", StaticFiles(directory=views_path), name="favicon.ico")

    _register_routes(app)
    return app


def _start_profile(state, profile):
    """
    Starts the INDI server with the specified profile.

    Args:
        state: App state (request.app.state) with db, collection, indi_server.
        profile (str): The name of the profile to start.

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


def _register_routes(app):
    """Register all route handlers on the app."""
    @app.get("/", response_class=HTMLResponse, tags=["Web Interface"])
    async def main_form(request: Request):
        """Renders the main form page."""
        state = request.app.state
        state.saved_profile = request.cookies.get('indiserver_profile') or 'Simulators'
        drivers = state.collection.get_families()
        profiles = state.db.get_profiles()
        logging.debug(f"Profiles retrieved from DB: {profiles}")
        return state.templates.TemplateResponse(
            "form.tpl",
            {"request": request,
             "profiles": profiles,
             "drivers": drivers,
             "saved_profile": state.saved_profile,
             "hostname": state.hostname,
             "sorted": sorted}
        )

    @app.get('/api/profiles', tags=["Profiles"])
    async def get_json_profiles(request: Request):
        """Gets all profiles from the database as JSON."""
        results = request.app.state.db.get_profiles()
        return JSONResponse(content=results)

    @app.get('/api/profiles/{item}', tags=["Profiles"])
    async def get_json_profile(request: Request, item: str):
        """Gets information for a specific profile as JSON."""
        results = request.app.state.db.get_profile(item)
        if results:
            return JSONResponse(content=results)
        raise HTTPException(status_code=404, detail="Profile not found")

    @app.post('/api/profiles/{name}', tags=["Profiles"])
    async def add_profile(request: Request, name: str):
        """Adds a new profile to the database."""
        request.app.state.db.add_profile(name)
        return {"message": f"Profile {name} added"}

    @app.delete('/api/profiles/{name}', tags=["Profiles"])
    async def delete_profile(request: Request, name: str):
        """Deletes a profile from the database."""
        request.app.state.db.delete_profile(name)
        return {"message": f"Profile {name} deleted"}

    @app.put('/api/profiles/{name}', tags=["Profiles"])
    async def update_profile(request: Request, response: Response, name: str):
        """Updates the information for a specific profile."""
        response.set_cookie(key="indiserver_profile", value=name, max_age=3600000, path='/')
        data = await request.json()
        port = data.get('port', request.app.state.args.indi_port)
        scripts = data.get('scripts', "")
        autostart = bool(data.get('autostart', 0))
        autoconnect = bool(data.get('autoconnect', 0))
        request.app.state.db.update_profile(name, port, autostart, autoconnect, scripts)
        return {"message": f"Profile {name} updated"}

    @app.post('/api/profiles/{name}/drivers', tags=["Profiles"])
    async def save_profile_drivers(request: Request, name: str):
        """Saves the drivers associated with a profile."""
        data = await request.json()
        request.app.state.db.save_profile_drivers(name, data)
        return {"message": f"Drivers saved for profile {name}"}

    @app.post('/api/profiles/custom/add', tags=["Profiles"])
    async def save_profile_custom_driver(request: Request):
        """Adds a custom driver to the database and updates the driver collection."""
        data = await request.json()
        state = request.app.state
        state.db.save_profile_custom_driver(data)
        state.collection.clear_custom_drivers()
        state.collection.parse_custom_drivers(state.db.get_custom_drivers())
        return {"message": "Custom driver saved and collection updated"}

    @app.get('/api/profiles/{item}/labels', tags=["Profiles"])
    async def get_json_profile_labels(request: Request, item: str):
        """Gets the driver labels for a specific profile as JSON."""
        results = request.app.state.db.get_profile_drivers_labels(item)
        return JSONResponse(content=results)

    @app.get('/api/profiles/{item}/remote', tags=["Profiles"])
    async def get_remote_drivers(request: Request, item: str):
        """Gets the remote drivers for a specific profile as JSON."""
        results = request.app.state.db.get_profile_remote_drivers(item)
        if results and isinstance(results, list) and len(results) > 0:
            return JSONResponse(content=results[0])
        return JSONResponse(content={})

    @app.get('/api/server/status', tags=["Server"])
    async def get_server_status(request: Request):
        """Gets the status of the INDI server and the active profile as JSON."""
        state = request.app.state
        status = [{'status': str(state.indi_server.is_running()), 'active_profile': state.active_profile}]
        return JSONResponse(content=status)

    @app.get('/api/server/drivers', tags=["Server"])
    async def get_server_drivers(request: Request):
        """Lists the currently running server drivers as JSON."""
        indi_server = request.app.state.indi_server
        drivers = []
        if indi_server.is_running() is True:
            for driver in indi_server.get_running_drivers().values():
                drivers.append(driver.__dict__)
        return JSONResponse(content=drivers)

    @app.post('/api/server/start/{profile}', tags=["Server"])
    async def start_server(request: Request, response: Response, profile: str):
        """Starts the INDI server for a specific profile."""
        state = request.app.state
        state.saved_profile = profile
        state.active_profile = profile
        response.set_cookie(key="indiserver_profile", value=profile, max_age=3600000, path='/')
        _start_profile(state, profile)
        # Wait for driver starter thread so getActiveDrivers sees all drivers when frontend polls
        await asyncio.to_thread(state.indi_server.wait_for_drivers_started, 5)
        return {"message": f"INDI server started for profile {profile}"}

    @app.post('/api/server/stop', tags=["Server"])
    async def stop_server(request: Request):
        """Stops the INDI server."""
        state = request.app.state
        state.indi_server.stop()
        state.active_profile = ""
        return {"message": "INDI server stopped"}

    @app.get('/api/info/version', tags=["Info"])
    async def get_version():
        """Gets the version of indiwebmanager."""
        return {"version": version("indiweb")}

    @app.get('/api/info/arch', tags=["Info"])
    async def get_arch():
        """Gets the architecture of the system."""
        arch = platform.machine()
        if arch == "aarch64":
            arch = "arm64"
        elif arch == "armv7l":
            arch = "armhf"
        return arch

    @app.get('/api/info/hostname', tags=["Info"])
    async def get_hostname():
        """Gets the hostname of the system."""
        return {"hostname": socket.gethostname()}

    @app.get('/api/drivers/groups', tags=["Drivers"])
    async def get_json_groups(request: Request):
        """Gets all driver families as JSON."""
        families = request.app.state.collection.get_families()
        return JSONResponse(content=sorted(families.keys()))

    @app.get('/api/drivers', tags=["Drivers"])
    async def get_json_drivers(request: Request):
        """Gets all drivers as JSON."""
        return JSONResponse(content=[ob.__dict__ for ob in request.app.state.collection.drivers])

    @app.post('/api/drivers/start/{label}', tags=["Drivers"])
    async def start_driver(request: Request, label: str):
        """Starts an INDI driver by label."""
        state = request.app.state
        driver = state.collection.by_label(label)
        if driver:
            state.indi_server.start_driver(driver)
            logging.info('Driver "%s" started.' % label)
            return {"message": f"Driver {label} started"}
        raise HTTPException(status_code=404, detail="Driver not found")

    @app.post('/api/drivers/start_remote/{label}', tags=["Drivers"])
    async def start_remote_driver(request: Request, label: str):
        """Starts a remote INDI driver."""
        driver = DeviceDriver(label, label, "1.0", label, "Remote", None, False, None)
        request.app.state.indi_server.start_driver(driver)
        logging.info('Driver "%s" started.' % label)
        return {"message": f"Remote driver {label} started"}

    @app.post('/api/drivers/stop/{label}', tags=["Drivers"])
    async def stop_driver(request: Request, label: str):
        """Stops an INDI driver by label."""
        state = request.app.state
        driver = state.collection.by_label(label)
        if driver:
            state.indi_server.stop_driver(driver)
            logging.info('Driver "%s" stopped.' % label)
            return {"message": f"Driver {label} stopped"}
        raise HTTPException(status_code=404, detail="Driver not found")

    @app.post('/api/drivers/stop_remote/{label}', tags=["Drivers"])
    async def stop_remote_driver(request: Request, label: str):
        """Stops a remote INDI driver."""
        driver = DeviceDriver(label, label, "1.0", label, "Remote", None, False, None)
        request.app.state.indi_server.stop_driver(driver)
        logging.info('Driver "%s" stopped.' % label)
        return {"message": f"Remote driver {label} stopped"}

    @app.post('/api/drivers/restart/{label}', tags=["Drivers"])
    async def restart_driver(request: Request, label: str):
        """Restarts an INDI driver by label."""
        state = request.app.state
        driver = state.collection.by_label(label)
        if driver:
            state.indi_server.stop_driver(driver)
            state.indi_server.start_driver(driver)
            logging.info('Driver "%s" restarted.' % label)
            return {"message": f"Driver {label} restarted"}
        raise HTTPException(status_code=404, detail="Driver not found")

    @app.get('/api/devices', tags=["Devices"])
    async def get_devices(request: Request):
        """Gets a list of connected INDI devices as JSON."""
        return JSONResponse(content=request.app.state.indi_device.get_devices())

    @app.post('/api/system/reboot', tags=["System"])
    async def system_reboot(request: Request):
        """Reboots the system running indi-web."""
        logging.info('System reboot, stopping server...')
        await stop_server(request)
        logging.info('rebooting...')
        sudo = request.app.state.args.sudo
        subprocess.run(["sudo", "reboot"] if sudo else ["reboot"])
        return {"message": "System is rebooting"}

    @app.post('/api/system/poweroff', tags=["System"])
    async def system_poweroff(request: Request):
        """Powers off the system."""
        logging.info('System poweroff, stopping server...')
        await stop_server(request)
        logging.info('poweroff...')
        sudo = request.app.state.args.sudo
        subprocess.run(["sudo", "poweroff"] if sudo else ["poweroff"])
        return {"message": "System is powering off"}


def main():
    """
    Main function to start the indiwebmanager application.
    Starts the autostart profile if configured and runs the web server.
    """
    args = parse_args()
    app = create_app(args)

    for profile in app.state.db.get_profiles():
        if profile['autostart']:
            _start_profile(app.state, profile['name'])
            app.state.active_profile = profile['name']
            break

    uvicorn.run(app, host=args.host, port=args.port)
    logging.info("Exiting")


# JM 2018-12-24: Added __main__ so I can debug this as a module in PyCharm
# Otherwise, I couldn't get it to run main as all
if __name__ == '__main__':
    main()
