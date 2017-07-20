import sqlite3


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class Database(object):
    def __init__(self, filename):
        self.__conn = sqlite3.connect(filename)
        self.__conn.row_factory = dict_factory

    def get_autoprofile(self):
        """Get auto start profile"""
        cursor = self.__conn.execute("SELECT profile FROM autostart")
        result = cursor.fetchone()
        return result['profile'] if result else ''

    def get_profiles(self):
        """Get all profiles from database"""
        cursor = self.__conn.execute("SELECT * FROM profile")
        return cursor.fetchall()

    def get_profile_drivers_labels(self, profile_name):
        """Get all drivers labels for a specific profile from database"""
        cursor = self.__conn.execute(
            "SELECT label FROM driver "
            "WHERE profile=(SELECT id FROM profile WHERE name=?)",
            (profile_name,))
        return cursor.fetchall()

    def get_profile_custom_drivers(self, profile_name):
        """Get custom drivers list for a specific profile"""
        cursor = self.__conn.execute(
            "SELECT drivers FROM custom "
            "WHERE profile=(SELECT id FROM profile WHERE name=?)",
            (profile_name,))
        return cursor.fetchone()

    def delete_profile(self, profile_name):
        """Delete Profile"""
        try:
            self.__conn.execute(
                "DELETE FROM driver WHERE "
                "profile=(SELECT id FROM profile WHERE name=?)",
                (profile_name,))
            self.__conn.execute("DELETE FROM profile WHERE name=?",
                                (profile_name,))
        except Exception:
            return "Error deleting profile"
        else:
            self.__conn.commit()

    def add_profile(self, profile_name):
        """Add Profile"""
        try:
            self.__conn.execute("INSERT INTO profile (name) VALUES(?)",
                                (profile_name,))
        except Exception:
            return "Error adding profile. Profile already exists."
        else:
            self.__conn.commit()

    def get_profile(self, name):
        """Get profile info"""
        cursor = self.__conn.execute("SELECT * FROM profile WHERE name=?",
                                     (name,))
        return cursor.fetchone()

    def update_profile(self, name, data):
        """Update profile info"""

        # If we have a driver with autostart, reset everyone to 0
        autostart = data.get('autostart', None)
        port = data.get('port', None)

        if autostart == 1:
            self.__conn.execute("UPDATE profile SET autostart=0")
            self.__conn.commit()

        cursor = self.__conn.execute("SELECT id FROM profile WHERE name=?",
                                     (name,))
        result = cursor.fetchone()
        # Return if no profile exists
        if result is None:
            return

        profile_id = result['id']
        try:
            if autostart is not None:
                self.__conn.execute(
                    "UPDATE profile SET autostart=? WHERE id=?",
                    autostart, profile_id)
            if port is not None:
                self.__conn.execute("UPDATE profile SET port=? WHERE id=?",
                                    (port, profile_id))
        except Exception:
            return "Error updating profile info ", Exception.message
        else:
            self.__conn.commit()

    def save_profile_drivers(self, profile_name, drivers):
        """Save profile drivers"""

        while True:
            cursor = self.__conn.execute("SELECT id FROM profile WHERE name=?",
                                         (profile_name,))
            result = cursor.fetchone()
            if result is None:
                # Add profile if it doesn't exist yet
                self.add_profile(profile_name)
            else:
                break

        profile_id = result['id']
        self.__conn.execute("DELETE FROM driver WHERE profile=?",
                            (profile_id,))
        self.__conn.execute("DELETE FROM custom WHERE profile=?",
                            (profile_id,))

        for driver in drivers:
            try:
                if "label" in driver:
                    self.__conn.execute(
                        "INSERT INTO driver (label, profile) VALUES(?, ?)",
                        (driver['label'], profile_id))
                elif "custom" in driver:
                    self.__conn.execute(
                        "INSERT INTO custom (drivers, profile) VALUES(?, ?)",
                        (driver["custom"], profile_id))
            except Exception:
                return "Error adding a driver"
            else:
                self.__conn.commit()
