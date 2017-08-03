import os
import errno
import sqlite3
import logging


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class Database(object):
    def __init__(self, filename):
        # create the directory if it does not exist
        db_dir = os.path.dirname(filename)
        try:
            os.makedirs(db_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        else:
            logging.info("Created directory %s" % db_dir)

        self.__conn = sqlite3.connect(filename)
        self.__conn.row_factory = dict_factory

        # create new tables if they doesn't exist
        self.create(filename)

    def create(self, filename):
        c = self.__conn.cursor()

        c.execute('CREATE TABLE IF NOT EXISTS '
                  'driver (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'label TEXT, profile INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS '
                  'custom (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'drivers TEXT, profile INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS '
                  'profile (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'name TEXT UNIQUE, port INTEGER DEFAULT 7624, '
                  'autostart INTEGER DEFAULT 0)')
        self.__conn.commit()

        c.execute('SELECT id FROM profile')
        if not c.fetchone():
            c.execute('INSERT INTO profile (name) VALUES ("Simulators")')
            c.execute('INSERT INTO driver (profile, label) VALUES (1, "Telescope Simulator")')
            c.execute('INSERT INTO driver (profile, label) VALUES (1, "CCD Simulator")')
            c.execute('INSERT INTO driver (profile, label) VALUES (1, "Focuser Simulator")')
            self.__conn.commit()
        c.close()

    def get_autoprofile(self):
        """Get auto start profile"""

        cursor = self.__conn.execute('SELECT profile FROM autostart')
        result = cursor.fetchone()
        return result['profile'] if result else ''

    def get_profiles(self):
        """Get all profiles from database"""

        cursor = self.__conn.execute('SELECT * FROM profile')
        return cursor.fetchall()

    def get_profile_drivers_labels(self, name):
        """Get all drivers labels for a specific profile from database"""

        cursor = self.__conn.execute(
            'SELECT label FROM driver '
            'WHERE profile=(SELECT id FROM profile WHERE name=?)', (name,))
        return cursor.fetchall()

    def get_profile_custom_drivers(self, name):
        """Get custom drivers list for a specific profile"""

        cursor = self.__conn.execute(
            'SELECT drivers FROM custom '
            'WHERE profile=(SELECT id FROM profile WHERE name=?)', (name,))
        return cursor.fetchone()

    def delete_profile(self, name):
        """Delete Profile"""

        c = self.__conn.cursor()
        c.execute('DELETE FROM driver WHERE profile='
                  '(SELECT id FROM profile WHERE name=?)', (name,))
        c.execute('DELETE FROM profile WHERE name=?', (name,))
        self.__conn.commit()
        c.close()

    def add_profile(self, name):
        """Add Profile"""

        c = self.__conn.cursor()
        c.execute('INSERT INTO profile (name) VALUES(?)', (name,))
        return c.lastrowid

    def get_profile(self, name):
        """Get profile info"""

        cursor = self.__conn.execute('SELECT * FROM profile WHERE name=?',
                                     (name,))
        return cursor.fetchone()

    def update_profile(self, name, port, autostart=False):
        """Update profile info"""

        c = self.__conn.cursor()
        if autostart:
            # If we have a profile with autostart=1, reset everyone else to 0
            c.execute('UPDATE profile SET autostart=0')
        c.execute('UPDATE profile SET port=?, autostart=? WHERE name=?',
                  (port, autostart, name))
        self.__conn.commit()
        c.close()

    def save_profile_drivers(self, name, drivers):
        """Save profile drivers"""

        c = self.__conn.cursor()
        c.execute('SELECT id FROM profile WHERE name=?', (name,))
        result = c.fetchone()
        if result:
            pid = result['id']
        else:
            pid = self.add_profile(name)

        c.execute('DELETE FROM driver WHERE profile=?', (pid,))
        c.execute('DELETE FROM custom WHERE profile=?', (pid,))

        for driver in drivers:
            if 'label' in driver:
                c.execute('INSERT INTO driver (label, profile) VALUES(?, ?)',
                          (driver['label'], pid))
            elif 'custom' in driver:
                c.execute('INSERT INTO custom (drivers, profile) VALUES(?, ?)',
                          (driver['custom'], pid))
        self.__conn.commit()
        c.close()
