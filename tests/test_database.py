"""Layer 1: Database unit tests. Uses real SQLite, no mocking."""

import os

import pytest

from indiweb.database import Database


@pytest.fixture
def db_path(tmp_path):
    """Path to a temporary database file."""
    return os.path.join(tmp_path, "profiles.db")


@pytest.fixture
def db(db_path):
    """Database instance with fresh schema."""
    return Database(db_path)


def test_database_creates_schema(db):
    """Database create() creates tables and default Simulators profile."""
    profiles = db.get_profiles()
    assert len(profiles) >= 1
    names = [p["name"] for p in profiles]
    assert "Simulators" in names


def test_database_simulators_has_three_drivers(db):
    """Default Simulators profile has Telescope, CCD, Focuser simulators."""
    labels = db.get_profile_drivers_labels("Simulators")
    label_names = [d["label"] for d in labels]
    assert "Telescope Simulator" in label_names
    assert "CCD Simulator" in label_names
    assert "Focuser Simulator" in label_names
    assert len(label_names) == 3


def test_database_add_profile(db):
    """add_profile creates a new profile."""
    rowid = db.add_profile("TestProfile")
    assert rowid is not None
    profile = db.get_profile("TestProfile")
    assert profile is not None
    assert profile["name"] == "TestProfile"


def test_database_get_profile_not_found(db):
    """get_profile returns None for missing profile."""
    assert db.get_profile("Nonexistent") is None


def test_database_delete_profile(db):
    """delete_profile removes profile and its drivers."""
    db.add_profile("ToDelete")
    db.save_profile_drivers("ToDelete", [{"label": "CCD Simulator"}])
    db.delete_profile("ToDelete")
    assert db.get_profile("ToDelete") is None
    assert db.get_profile_drivers_labels("ToDelete") == []


def test_database_save_profile_drivers(db):
    """save_profile_drivers updates drivers for a profile."""
    db.add_profile("CustomProfile")
    db.save_profile_drivers(
        "CustomProfile",
        [
            {"label": "CCD Simulator"},
            {"label": "Telescope Simulator"},
        ],
    )
    labels = db.get_profile_drivers_labels("CustomProfile")
    assert len(labels) == 2
    label_names = [d["label"] for d in labels]
    assert "CCD Simulator" in label_names
    assert "Telescope Simulator" in label_names


def test_database_update_profile(db):
    """update_profile updates port, autostart, autoconnect, scripts."""
    db.add_profile("UpdateMe")
    db.update_profile("UpdateMe", port=9999, autostart=True, autoconnect=True, scripts='[]')
    profile = db.get_profile("UpdateMe")
    assert profile["port"] == 9999
    assert profile["autostart"] == 1
    assert profile["autoconnect"] == 1


def test_database_get_custom_drivers_empty(db):
    """get_custom_drivers returns empty list for fresh database."""
    assert db.get_custom_drivers() == []


def test_database_add_profile_duplicate(db):
    """add_profile with duplicate name catches IntegrityError, does not raise."""
    db.add_profile("DupProfile")
    db.add_profile("DupProfile")  # duplicate, should not raise
    profile = db.get_profile("DupProfile")
    assert profile is not None
    assert profile["name"] == "DupProfile"
    # Only one profile with that name
    profiles = [p for p in db.get_profiles() if p["name"] == "DupProfile"]
    assert len(profiles) == 1


def test_database_save_profile_drivers_with_remote(db):
    """save_profile_drivers with remote driver stores in remote table."""
    db.add_profile("RemoteProfile")
    db.save_profile_drivers("RemoteProfile", [{"remote": "remote@host.example"}])
    remotes = db.get_profile_remote_drivers("RemoteProfile")
    assert len(remotes) == 1
    assert remotes[0]["drivers"] == "remote@host.example"


def test_database_save_profile_custom_driver(db):
    """save_profile_custom_driver inserts custom driver, get_custom_drivers returns it."""
    db.save_profile_custom_driver(
        {
            "Label": "Custom Driver",
            "Name": "Custom",
            "Family": "Custom",
            "Exec": "/usr/bin/custom",
            "Version": "1.0",
        }
    )
    customs = db.get_custom_drivers()
    assert len(customs) == 1
    assert customs[0]["label"] == "Custom Driver"
    assert customs[0]["exec"] == "/usr/bin/custom"


def test_database_save_profile_drivers_creates_profile_if_missing(db):
    """save_profile_drivers for non-existent profile creates profile via add_profile."""
    db.save_profile_drivers("AutoCreated", [{"label": "CCD Simulator"}])
    profile = db.get_profile("AutoCreated")
    assert profile is not None
    assert profile["name"] == "AutoCreated"
    labels = db.get_profile_drivers_labels("AutoCreated")
    assert len(labels) == 1
    assert labels[0]["label"] == "CCD Simulator"


def test_database_init_with_existing_directory(tmp_path):
    """Database init with existing directory does not raise EEXIST."""
    db_dir = os.path.join(tmp_path, "existing")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "profiles.db")
    db = Database(db_path)
    assert db.get_profiles() is not None
