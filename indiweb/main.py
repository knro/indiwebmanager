#!/usr/bin/env python

import os
import json
import logging
import argparse
from bottle import Bottle, run, template, static_file, request, response
from .indi_server import IndiServer, INDI_PORT, INDI_FIFO, INDI_CONFIG_DIR
from .driver import DeviceDriver, DriverCollection, INDI_DATA_DIR
from .database import Database

# default settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 8624

pkg_path, _ = os.path.split(os.path.abspath(__file__))
views_path = os.path.join(pkg_path, 'views')


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
args = parser.parse_args()


logging_level = logging.WARNING

if args.verbose:
    logging_level = logging.DEBUG

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging_level)

collection = DriverCollection(args.xmldir)
indi_server = IndiServer(args.fifo, args.conf)

db_path = os.path.join(args.conf, 'profiles.db')
db = Database(db_path)
app = Bottle()

saved_profile = None


def start_profile(profile):
    info = db.get_profile(profile)

    profile_drivers = db.get_profile_drivers_labels(profile)
    all_drivers = [collection.by_label(d['label']) for d in profile_drivers]

    # Find if we have any custom drivers
    custom_drivers = db.get_profile_custom_drivers(profile)
    if custom_drivers:
        drivers = custom_drivers['drivers'].split(',')
        for drv in drivers:
            all_drivers.append(DeviceDriver(drv, drv, "1.0", drv, "Custom"))

    if all_drivers:
        indi_server.start(info['port'], all_drivers)


@app.route('/static/<path:path>')
def callback(path):
    """Serve static files"""
    return static_file(path, root=views_path)


@app.route('/favicon.ico', method='GET')
def get_favicon():
    """Serve favicon"""
    return static_file('favicon.ico', root=views_path)


@app.route('/')
def main_form():
    """Main page"""
    global saved_profile
    drivers = collection.get_families()

    if not saved_profile:
        saved_profile = request.get_cookie('indiserver_profile') or 'Simulators'

    profiles = db.get_profiles()
    return template(os.path.join(views_path, 'form.tpl'), profiles=profiles,
                    drivers=drivers, saved_profile=saved_profile)


###############################################################################
# Profile endpoints
###############################################################################

@app.get('/api/profiles')
def get_json_profiles():
    """Get all profiles (JSON)"""
    results = db.get_profiles()
    return json.dumps(results)


@app.get('/api/profiles/<item>')
def get_json_profile(item):
    """Get one profile info"""
    results = db.get_profile(item)
    return json.dumps(results)


@app.post('/api/profiles/<name>')
def add_profile(name):
    """Add new profile"""
    db.add_profile(name)


@app.delete('/api/profiles/<name>')
def delete_profile(name):
    """Delete Profile"""
    db.delete_profile(name)


@app.put('/api/profiles/<name>')
def update_profile(name):
    """Update profile info (port & autostart)"""
    response.set_cookie("indiserver_profile", name,
                        None, max_age=3600000, path='/')
    data = request.json
    port = data.get('port', args.indi_port)
    autostart = bool(data.get('autostart', 0))
    db.update_profile(name, port, autostart)


@app.post('/api/profiles/<name>/drivers')
def save_profile_drivers(name):
    """Add drivers to existing profile"""
    data = request.json
    db.save_profile_drivers(name, data)


@app.get('/api/profiles/<item>/labels')
def get_json_profile_labels(item):
    """Get driver labels of specific profile"""
    results = db.get_profile_drivers_labels(item)
    return json.dumps(results)


@app.get('/api/profiles/<item>/custom')
def get_custom_drivers(item):
    """Get custom drivers of specific profile"""
    results = db.get_profile_custom_drivers(item)
    js = json.dumps(results)
    return [] if js == 'null' else js


###############################################################################
# Server endpoints
###############################################################################

@app.get('/api/server/status')
def get_server_status():
    """Server status"""
    status = [{'status': str(indi_server.is_running())}]
    return json.dumps(status)


@app.get('/api/server/drivers')
def get_server_drivers():
    """List server drivers"""
    status = []
    for driver in indi_server.get_running_drivers():
        status.append({'driver': driver})
    return json.dumps(status)


@app.post('/api/server/start/<profile>')
def start_server(profile):
    """Start INDI server for a specific profile"""
    global saved_profile
    saved_profile = profile
    response.set_cookie("indiserver_profile", profile,
                        None, max_age=3600000, path='/')
    start_profile(profile)


@app.post('/api/server/stop')
def stop_server():
    """Stop INDI Server"""
    indi_server.stop()

    # If there is saved_profile already let's try to reset it
    global saved_profile
    if saved_profile:
        saved_profile = request.get_cookie("indiserver_profile") or "Simulators"


###############################################################################
# Driver endpoints
###############################################################################

@app.get('/api/drivers/groups')
def get_json_groups():
    """Get all driver families (JSON)"""
    response.content_type = 'application/json'
    families = collection.get_families()
    return json.dumps(sorted(families.keys()))


@app.get('/api/drivers')
def get_json_drivers():
    """Get all drivers (JSON)"""
    response.content_type = 'application/json'
    return json.dumps([ob.__dict__ for ob in collection.drivers])


def main():
    """Start autostart profile if any"""
    for profile in db.get_profiles():
        if profile['autostart']:
            start_profile(profile['name'])
            break

    run(app, host=args.host, port=args.port, quiet=not args.verbose)
    logging.info("Exiting")


if __name__ == '__init__':
    main()
