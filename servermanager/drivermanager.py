#!/usr/bin/python

from bottle import Bottle, run, template, static_file, request
from parsedrivers import driversList, findDriverByLabel
from servermanager import startServer, stopServer, isServerRunning, getRunningDrivers
import json
import db

app = Bottle()

# Server static files  
@app.route('/static/<path:path>')
def callback(path):
    return static_file(path, root="./views")

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
    print ("start server called....")
    drivers    = request.json
    port       = 7624
    alldrivers = []
    for driver in drivers:
        if "port" in driver:            
            port = driver['port']
            response.set_cookie("indiserver_port", port, None, max_age=3600000, path='/')
            #print("driver port is " + driver['port'])
        elif "profile" in driver:
            response.set_cookie("indiserver_profile", driver['profile'], None, max_age=3600000, path='/')
        else:            
            #print(driver['label'])
            oneDriver = findDriverByLabel(driver['label'])
            alldrivers.append(oneDriver)
            
    #print ("calling start server internal function")
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

# Get drivers of specific profile
@app.get('/api/profiles/<item>')
def get_profile(item):
    from json import dumps
    results = db.get_profile_drivers(item)
    json_string = json.dumps(results)
    return json_string


#run(app, host='0.0.0.0', port=8080, debug=True, reloader=True)
run(app, host='0.0.0.0', port=8080, debug=True)

