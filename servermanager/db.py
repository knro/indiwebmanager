import sqlite3, json, os

dirname, filename = os.path.split(os.path.abspath(__file__))

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

conn = sqlite3.connect(dirname+"/profiles.db")
conn.row_factory = dict_factory

# Get auto start profile        
def get_autoprofile():
    cursor = conn.execute("SELECT profile FROM autostart")
    result = cursor.fetchone()
    if result:
        return result['profile']
    else:
        return ''
    
# Get all profiles from database        
def get_profiles():
    cursor = conn.execute("SELECT * FROM profile")
    results = cursor.fetchall()    
    return results

# Get all drivers labels for a specific profile from database
def get_profile_drivers_labels(profile_name):
    #print ("SELECT label FROM driver WHERE profile=(SELECT id FROM profile WHERE name='" + profile_name + "')");
    cursor     = conn.execute("SELECT label FROM driver WHERE profile=(SELECT id FROM profile WHERE name='" + profile_name + "')")
    results = cursor.fetchall()
    return results

# Get custom drivers list for a specific profile
def get_profile_custom_drivers(profile_name):
    cursor     = conn.execute("SELECT drivers FROM custom WHERE profile=(SELECT id FROM profile WHERE name='" + profile_name + "')")
    results = cursor.fetchone()
    return results

# Delete Profile
def delete_profile(profile_name):   
    try:
        conn.execute("DELETE FROM driver WHERE profile=(SELECT id FROM profile WHERE name='" + profile_name + "')")
        conn.execute("DELETE FROM profile WHERE name='" + profile_name + "'");        
    except Exception:
        return "Error deleting profile"
    else:
        conn.commit()
        
# Add Profile
def add_profile(profile_name):
    try:
        conn.execute("INSERT INTO profile (name) VALUES('" + profile_name + "')");
    except Exception:
        return "Error adding profile. Profile already exists."
    else:
        conn.commit();

# Get profile info
def get_profile(name):
    cursor = conn.execute("SELECT * FROM profile WHERE name='" + name + "'");
    result = cursor.fetchone();
    return result

# Update profile info
def update_profile(name, data):
    # If we have a driver with autostart, reset everyone to 0
    autostart=-1
    port = -1
    if "autostart" in data:
        autostart = data["autostart"]
    if "port" in data:
        port = data["port"]

    if (autostart == 1):
        conn.execute("UPDATE profile SET autostart=0");
        conn.commit();
        
    cursor = conn.execute("SELECT id FROM profile WHERE name='" + name + "'");
    result = cursor.fetchone();
    # Return if no profile exists
    if (result == None):
        return

    profile_id = result['id'];
    try:
        if (autostart != -1):
            conn.execute("UPDATE profile SET autostart=" + str(autostart) + " WHERE id =" + str(profile_id));
        if (port != -1):
            conn.execute("UPDATE profile SET port=" + str(port) + " WHERE id =" + str(profile_id));
    except Exception:
        return "Error updating profile info ", Exception.message
    else:
        conn.commit();
     
# Save profile drivers
def save_profile_drivers(profile_name, drivers):   
    cursor = conn.execute("SELECT id FROM profile WHERE name='" + profile_name + "'");
    result = cursor.fetchone();
    # Add profile if it doesn't exist yet
    if (result == None):
        add_profile(profile_name)
        cursor = conn.execute("SELECT id FROM profile WHERE name='" + profile_name + "'");
        result = cursor.fetchone();

    profile_id = result['id'];    
    cursor = conn.execute("DELETE FROM driver WHERE profile =" + str(profile_id));
    cursor = conn.execute("DELETE FROM custom WHERE profile =" + str(profile_id));
    for driver in drivers:  
        print (driver)
        try:
            if "label" in driver:
                conn.execute("INSERT INTO driver (label, profile) VALUES('" + driver["label"] + "'," + str(profile_id) + ")");
            elif "custom" in driver:
                conn.execute("INSERT INTO custom (drivers, profile) VALUES('" + driver["custom"] + "'," + str(profile_id) + ")");
        except Exception:
            return "Error adding a driver"
        else:
            conn.commit();   

