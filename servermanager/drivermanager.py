#!/usr/bin/python

from bottle import Bottle, run, template, static_file, request
from servermanager import startServer, stopServer, isServerRunning, getRunningDrivers
from parsedrivers import driversList, findDriverByLabel
import db
import json
import os

dirname, filename = os.path.split(os.path.abspath(__file__))
os.chdir(dirname)

app = Bottle()

saved_profile = None


# Server static files
@app.route('/static/<path:path>')
def callback(path):
    return static_file(path, root="./views")


# Favicon
@app.route('/favicon.ico', method='GET')
def get_favicon():
    return static_file('favicon.ico', root='./')


# Main Page
@app.route('/')
def form():
    global saved_profile
    families = get_driver_families()
    allDrivers = {}
    for family in families:
        drivers = [ob.label for ob in driversList if ob.family == family]
        allDrivers[family] = drivers

    # port = request.get_cookie("indiserver_port")
    # print ("cooke port is " + port)
    # if not port:
    #    port = 7624;

    if not saved_profile:
        saved_profile = request.get_cookie("indiserver_profile")
        if not saved_profile:
            saved_profile = "Simulators"

    allProfiles = get_profiles()
    return template('form.tpl', allProfiles=allProfiles, allDrivers=allDrivers, saved_profile=saved_profile)

''' Profile Operations '''


# Get all profiles
def get_profiles():
    return db.get_profiles()


# Add new profile
@app.post('/api/profiles/<name>')
def add_profile(name):
    db.add_profile(name)


# Get one profile info
def get_profile(name):
    return db.get_profile(name)


# Delete Profile
@app.delete('/api/profiles/<name>')
def delete_profile(name):
    db.delete_profile(name)


# Update profile info (port & autostart)
@app.put('/api/profiles/<name>')
def update_profile(name):
    from bottle import response
    response.set_cookie("indiserver_profile", name,
                        None, max_age=3600000, path='/')
    data = request.json
    db.update_profile(name, data)


# Add drivers to existing profile
@app.post('/api/profiles/<name>/drivers')
def save_profile_drivers(name):
    data = request.json
    db.save_profile_drivers(name, data)

''' Server Options '''


# Server status
@app.get('/api/server/status')
def get_server_status():
    status = [{'status': str(isServerRunning())}]
    json_string = json.dumps(status)
    return json_string


# Server Driver
@app.get('/api/server/drivers')
def get_server_drivers():
    status = []
    for driver in getRunningDrivers():
        status.append({'driver': driver})
    json_string = json.dumps(status)
    return json_string


# Start autostart profile if any
@app.post('/api/server/autostart')
def autostart_server():
    profiles = get_profiles()
    for profile in profiles:
        if profile['autostart'] == 1:
            start_server(profile['name'])
            break


# Start INDI Server for a specific profile
@app.post('/api/server/start/<profile>')
def start_server(profile):
    global saved_profile
    from bottle import response
    alldrivers = []
    saved_profile = profile
    response.set_cookie("indiserver_profile", profile,
                        None, max_age=3600000, path='/')
    info = db.get_profile(profile)
    port = info['port']
    drivers = db.get_profile_drivers_labels(profile)
    for driver in drivers:
        oneDriver = findDriverByLabel(driver['label'])
        alldrivers.append(oneDriver)
        # Find if we have any custom drivers
    custom_drivers = db.get_profile_custom_drivers(profile)
    if (custom_drivers):
        custom_drivers = custom_drivers['drivers'].split(',')
        for driver in custom_drivers:
            newDriver = DeviceDriver(driver, driver, "1.0", driver, "Custom")
            alldrivers.append(newDriver)

    # print ("calling start server internal function")
    if alldrivers:
        startServer(port, alldrivers)


# Stop INDI Server
@app.post('/api/server/stop')
def stop_server():
    global saved_profile
    stopServer()
    # If there is saved_profile already let's try to reset it
    if saved_profile:
        saved_profile = request.get_cookie("indiserver_profile")
        if not saved_profile:
            saved_profile = "Simulators"


''' Driver Operations '''


# Get all drivers
def get_drivers():
    drivers = [ob.__dict__ for ob in driversList]
    return drivers


# Get all drivers families (groups)
def get_driver_families():
    families = [ob.family for ob in driversList]
    families = sorted(list(set(families)))
    return families

''' JSON REQUESTS '''


# Get all driver families (JSON)
@app.get('/api/drivers/groups')
def get_json_groups():
    from bottle import response
    families = [ob.family for ob in driversList]
    families = sorted(list(set(families)))
    json_string = json.dumps(families)
    response.content_type = 'application/json'
    return json_string


# Get all drivers (JSON)
@app.get('/api/drivers')
def get_json_drivers():
    from bottle import response
    json_string = json.dumps([ob.__dict__ for ob in driversList])
    response.content_type = 'application/json'
    return json_string


# Get one profile info
@app.get('/api/profiles/<item>')
def get_json_profile(item):
    results = db.get_profile(item)
    json_string = json.dumps(results)
    return json_string


# Get all profiles (JSON)
@app.get('/api/profiles')
def get_json_profiles():
    results = db.get_profiles()
    json_string = json.dumps(results)
    return json_string


# Get driver labels of specific profile
@app.get('/api/profiles/<item>/labels')
def get_json_profile_labels(item):
    results = db.get_profile_drivers_labels(item)
    json_string = json.dumps(results)
    return json_string


# Get custom drivers of specific profile
@app.get('/api/profiles/<item>/custom')
def get_custom_drivers(item):
    results = db.get_profile_custom_drivers(item)
    json_string = json.dumps(results)
    if (json_string == "null"):
        return []
    else:
        return json_string

# run(app, host='0.0.0.0', port=8080, debug=True, reloader=True)
run(app, host='0.0.0.0', port=8624, debug=True)
