#!/usr/bin/env python

import os
import json
import logging
import argparse
from bottle import Bottle, run, template, static_file, request, response
from .indi_server import IndiServer, INDI_PORT, INDI_FIFO
from .driver import DriverCollection, INDI_DATA_DIR
from .database import Database

# default settings
HOST = '0.0.0.0'
PORT = 8624
DB_PATH = os.path.join(INDI_DATA_DIR, 'profiles.db')

pkg_path, _ = os.path.split(os.path.abspath(__file__))
views_path = os.path.join(pkg_path, 'views')


parser = argparse.ArgumentParser(
    description='Indi web manager. '
    'A simple web application to manage INDI server')

parser.add_argument('--indi-port', type=int, default=INDI_PORT,
                    help='indiserver port (default: %d)' % INDI_PORT)
parser.add_argument('--port', type=int, default=PORT,
                    help='Web server port (default: %d)' % PORT)
parser.add_argument('--host', default=HOST,
                    help='Bind web server to this interface (default: %s)' %
                    HOST)
parser.add_argument('--fifo', default=INDI_FIFO,
                    help='indiserver FIFO path (default: %s)' % INDI_FIFO)
parser.add_argument('--xmldir', default=INDI_DATA_DIR,
                    help='INDI XML directory (default: %s)' % INDI_DATA_DIR)
parser.add_argument('--db', default=DB_PATH,
                    help='Database path (default: %s)' % DB_PATH)
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Print more messages')
args = parser.parse_args()


logging_level = logging.DEBUG if args.verbose else logging.INFO
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging_level)

saved_profile = None
collection = DriverCollection(args.xmldir)
indi_server = IndiServer(args.fifo)
db = Database(args.db)
app = Bottle()


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
    info = db.get_profile(profile)
    port = info['port']

    profile_drivers = db.get_profile_drivers_labels(profile)
    all_drivers = [collection.by_label(d['label']) for d in profile_drivers]

    # Find if we have any custom drivers
    custom_drivers = db.get_profile_custom_drivers(profile)
    if custom_drivers:
        drivers = custom_drivers['drivers'].split(',')
        for drv in drivers:
            all_drivers.append(DeviceDriver(drv, drv, "1.0", drv, "Custom"))

    if all_drivers:
        indi_server.start(port, all_drivers)


@app.post('/api/server/autostart')
def autostart_server():
    """Start autostart profile if any"""
    profiles = db.get_profiles()
    for profile in profiles:
        if profile['autostart']:
            start_server(profile['name'])
            break


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
    run(app, host=args.host, port=args.port, debug=args.verbose)


if __name__ == '__init__':
    main()
