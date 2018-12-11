import os
import errno
import sqlite3
import logging
from . import __version__


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

        self.__conn = sqlite3.connect(filename, check_same_thread=False)
        self.__conn.row_factory = dict_factory

        # update table for version and any schema updates
        self.update()
        # create new tables if they doesn't exist
        self.create(filename)

    def update(self):
        c = self.__conn.cursor()
        # Check if we have a version table.
        try:
            c.execute('SELECT version FROM Version')
            result = c.fetchone()
            # Add autoconnect to profile before 0.1.6
            if result['version'] < '0.1.6':
                c.execute('ALTER TABLE profile ADD COLUMN autoconnect INTEGER DEFAULT 0')
        except sqlite3.Error:
            pass

        try:
            c.execute('UPDATE Version SET version=?', __version__)
        except sqlite3.Error:
            pass

    def create(self, filename):
        c = self.__conn.cursor()
        # Check if we have a version table. If not, then the scheme is too old and needs updating
        try:
            c.execute('SELECT version FROM Version')
        except sqlite3.Error:
            # We need to drop old table before this new schema starting with version 0.1.5
            try:
                c.execute('DROP TABLE custom')
            except sqlite3.Error:
                pass
            c.execute('CREATE TABLE Version (version TEXT)')
            c.execute('INSERT INTO Version (version) values(?)', (__version__,))

        c.execute('CREATE TABLE IF NOT EXISTS '
                  'driver (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'label TEXT, profile INTEGER)')
        # JM 2018-07-23: Adding custom drivers table
        c.execute('CREATE TABLE IF NOT EXISTS '
                  'custom (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'label TEXT UNIQUE, name TEXT, family TEXT, exec TEXT, version TEXT)')
        # JM 2018-07-23: Renaming custom drivers to remote since this is what they really are.
        c.execute('CREATE TABLE IF NOT EXISTS '
                  'remote (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'drivers TEXT, profile INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS '
                  'profile (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                  'name TEXT UNIQUE, port INTEGER DEFAULT 7624, '
                  'autostart INTEGER DEFAULT 0, '
                  'autoconnect INTEGER DEFAULT 0)')
        c.execute('UPDATE Version SET version=?', (__version__,))

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

    def get_custom_drivers(self):
        """Get all custom drivers from database"""

        cursor = self.__conn.execute('SELECT * FROM custom')
        return cursor.fetchall()

    def get_profile_drivers_labels(self, name):
        """Get all drivers labels for a specific profile from database"""

        cursor = self.__conn.execute(
            'SELECT label FROM driver '
            'WHERE profile=(SELECT id FROM profile WHERE name=?)', (name,))
        return cursor.fetchall()

    def get_profile_remote_drivers(self, name):
        """Get remote drivers list for a specific profile"""

        cursor = self.__conn.execute(
            'SELECT drivers FROM remote '
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
        try:
            c.execute('INSERT INTO profile (name) VALUES(?)', (name,))
        except sqlite3.IntegrityError:
            logging.warning("Profile name %s already exists.", name)
        return c.lastrowid

    def get_profile(self, name):
        """Get profile info"""

        cursor = self.__conn.execute('SELECT * FROM profile WHERE name=?',
                                     (name,))
        return cursor.fetchone()

    def update_profile(self, name, port, autostart=False, autoconnect=False):
        """Update profile info"""

        c = self.__conn.cursor()
        if autostart:
            # If we have a profile with autostart=1, reset everyone else to 0
            c.execute('UPDATE profile SET autostart=0')
        c.execute('UPDATE profile SET port=?, autostart=?, autoconnect=? WHERE name=?',
                  (port, autostart, autoconnect, name))
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
        c.execute('DELETE FROM remote WHERE profile=?', (pid,))

        for driver in drivers:
            if 'label' in driver:
                c.execute('INSERT INTO driver (label, profile) VALUES(?, ?)',
                          (driver['label'], pid))
            elif 'remote' in driver:
                c.execute('INSERT INTO remote (drivers, profile) VALUES(?, ?)',
                          (driver['remote'], pid))
        self.__conn.commit()
        c.close()

    def save_profile_custom_driver(self, driver):
        """Save custom profile driver"""

        c = self.__conn.cursor()
        try:
            c.execute('INSERT INTO custom (label, name, family, exec, version)'
                      ' VALUES(?, ?, ?, ?, ?)',
                      (driver['Label'], driver['Name'], driver['Family'], driver['Exec'], driver['Version']))
            self.__conn.commit()
        # Ignore duplicates
        except sqlite3.Error:
            pass
        c.close()
