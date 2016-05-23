#!/usr/bin/python

from bottle import Bottle, run, template, static_file, request
from servermanager import startServer, stopServer, isServerRunning, getRunningDrivers
from parsedrivers import *
import db, json, os

dirname, filename = os.path.split(os.path.abspath(__file__))
os.chdir(dirname)

app = Bottle()

# Server static files  
@app.route('/static/<path:path>')
def callback(path):
    return static_file(path, root="./views")

@app.route('/favicon.ico', method='GET')
def get_favicon():
    return static_file('favicon.ico', root='./')

# Main Page
@app.route('/')
def form(): 
    families = get_driver_families()
    allDrivers = {}
    for family in families:
        drivers = [ob.label for ob in driversList if ob.family==family]
        allDrivers[family] = drivers
    
    port = request.get_cookie("indiserver_port")
    #print ("cooke port is " + port)
    if not port:
        port = 7624;
        
    saved_profile = request.get_cookie("indiserver_profile")
    if not saved_profile:
        saved_profile = "Simualtors"
            
    allProfiles = get_profiles()
    return template('form.tpl', allProfiles=allProfiles, allDrivers=allDrivers, port=port, saved_profile=saved_profile)

''' Profile Operations '''

# Get all profiles
def get_profiles():
    return db.get_profiles()

# Add new profile        
@app.post('/api/profiles/<item>')
def add_profile(item):
    db.add_profile(item)

# Delete Profile        
@app.delete('/api/profiles/<item>')
def delete_profile(item):
    db.delete_profile(item)
        
# Add drivers to existing profile
@app.post('/api/profiles/<item>/')
def save_profile_drivers(item):   
    data = request.json;
    db.save_profile_drivers(item, data) 

''' Server Options '''
# Server Status
@app.get('/api/server/status')
def get_server_status():
    status = [ { 'status' : str(isServerRunning()) } ]
    json_string = json.dumps(status)
    return json_string

# Server Drivers
@app.get('/api/server/drivers')
def get_server_status():
    status = []
    for driver in getRunningDrivers():
        status.append({'driver' : driver })        
    json_string = json.dumps(status)
    return json_string    
    

# Start INDI Server
@app.post('/api/server/start')
def start_server():
    from bottle import response
    #print ("start server called....")
    drivers    = request.json
    port       = 7624
    alldrivers = []
    profile    = ""
    for driver in drivers:
        if "port" in driver:            
            port = driver['port']
            response.set_cookie("indiserver_port", port, None, max_age=3600000, path='/')
            #print("driver port is " + driver['port'])
        elif "profile" in driver:
            profile = driver['profile']
            response.set_cookie("indiserver_profile", profile, None, max_age=3600000, path='/')
        elif "name" in driver:            
            oneDriver = findDriverByName(driver['name'])
            alldrivers.append(oneDriver)
        elif "label" in driver:            
            oneDriver = findDriverByLabel(driver['label'])
            alldrivers.append(oneDriver)
        elif "binary" in driver:            
            oneDriver = findDriverByBinary(driver['binary'])
            alldrivers.append(oneDriver)
            
    # If we don't have any driver list but we have a profile name
    # we fetch labels from database for this profile
    if (not alldrivers and profile):
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
            
    #print ("calling start server internal function")
    if alldrivers:
        startServer(port, alldrivers)
    
            
    

# Stop INDI Server
@app.post('/api/server/stop')
def stop_server():   
    stopServer()

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
    from json import dumps
    families = [ob.family for ob in driversList]
    families = sorted(list(set(families)))
    json_string = json.dumps(families)
    response.content_type = 'application/json'
    return json_string

# Get all drivers (JSON)
@app.get('/api/drivers')
def get_json_drivers():
    from bottle import response
    from json import dumps
    json_string = json.dumps([ob.__dict__ for ob in driversList])
    response.content_type = 'application/json'
    return json_string

# Get all profiles (JSON)
@app.get('/api/profiles')
def get_json_profiles():
    from bottle import response
    from json import dumps
    results = db.get_profiles()
    json_string = json.dumps(results)
    return json_string 

# Get driver labels of specific profile
@app.get('/api/profiles/<item>')
def get_profile(item):
    from json import dumps
    results = db.get_profile_drivers_labels(item)
    json_string = json.dumps(results)
    return json_string

# Get custom drivers of specific profile
@app.get('/api/profiles/<item>/custom')
def get_profile(item):
    from json import dumps
    results = db.get_profile_custom_drivers(item)
    json_string = json.dumps(results)
    if (json_string == "null"):
        return []
    else:
        return json_string


#run(app, host='0.0.0.0', port=8080, debug=True, reloader=True)
run(app, host='0.0.0.0', port=8080, debug=True)

