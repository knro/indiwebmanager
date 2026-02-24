"""Layer 1: DriverCollection unit tests. Uses real XML from fixtures, no mocking."""

import os

import pytest

from indiweb.driver import DriverCollection

FIXTURE_XML_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "xml")


@pytest.fixture
def xmldir():
    """Use fixture XML for DriverCollection tests."""
    if os.path.isdir(FIXTURE_XML_DIR):
        return FIXTURE_XML_DIR
    pytest.skip("Fixture XML dir not found")


def test_driver_collection_parses_fixture_xml(xmldir):
    """DriverCollection parses fixture XML and finds simulator drivers."""
    collection = DriverCollection(xmldir)
    assert len(collection.drivers) >= 3


def test_driver_collection_by_label(xmldir):
    """by_label finds drivers by exact and partial match."""
    collection = DriverCollection(xmldir)
    for label in ("CCD Simulator", "Telescope Simulator", "Focuser Simulator"):
        driver = collection.by_label(label)
        assert driver is not None
        assert driver.label == label


def test_driver_collection_by_label_not_found(xmldir):
    """by_label returns None for unknown label."""
    collection = DriverCollection(xmldir)
    assert collection.by_label("Nonexistent Driver") is None


def test_driver_collection_get_families(xmldir):
    """get_families returns dict of family -> driver labels."""
    collection = DriverCollection(xmldir)
    families = collection.get_families()
    assert isinstance(families, dict)
    assert "CCDs" in families
    assert "Telescopes" in families
    assert "Focusers" in families
    assert "CCD Simulator" in families["CCDs"]
    assert "Telescope Simulator" in families["Telescopes"]
    assert "Focuser Simulator" in families["Focusers"]


def test_driver_collection_driver_has_binary(xmldir):
    """Parsed drivers have binary (executable name)."""
    collection = DriverCollection(xmldir)
    driver = collection.by_label("CCD Simulator")
    assert driver is not None
    assert driver.binary == "indi_simulator_ccd"


def test_driver_collection_parse_custom_drivers(xmldir):
    """parse_custom_drivers adds custom drivers to collection."""
    collection = DriverCollection(xmldir)
    initial_count = len(collection.drivers)
    collection.parse_custom_drivers(
        [
            {
                "label": "Custom Driver",
                "name": "Custom",
                "family": "Custom",
                "exec": "/usr/bin/custom_driver",
                "version": "1.0",
            }
        ]
    )
    assert len(collection.drivers) == initial_count + 1
    driver = collection.by_label("Custom Driver")
    assert driver is not None
    assert driver.custom is True
    assert driver.binary == "/usr/bin/custom_driver"


def test_driver_collection_clear_custom_drivers(xmldir):
    """clear_custom_drivers removes only custom drivers."""
    collection = DriverCollection(xmldir)
    collection.parse_custom_drivers(
        [
            {
                "label": "Custom Driver",
                "name": "Custom",
                "family": "Custom",
                "exec": "/usr/bin/custom",
                "version": "1.0",
            }
        ]
    )
    count_before = len(collection.drivers)
    collection.clear_custom_drivers()
    assert len(collection.drivers) == count_before - 1
    assert collection.by_label("Custom Driver") is None
    assert collection.by_label("CCD Simulator") is not None


def test_driver_collection_by_name(xmldir):
    """by_name finds driver by name."""
    collection = DriverCollection(xmldir)
    driver = collection.by_name("CCD Simulator")
    assert driver is not None
    assert driver.name == "CCD Simulator"
    assert driver.label == "CCD Simulator"


def test_driver_collection_by_name_not_found(xmldir):
    """by_name returns None for unknown name."""
    collection = DriverCollection(xmldir)
    assert collection.by_name("Nonexistent") is None


def test_driver_collection_by_binary(xmldir):
    """by_binary finds driver by binary path."""
    collection = DriverCollection(xmldir)
    driver = collection.by_binary("indi_simulator_ccd")
    assert driver is not None
    assert driver.binary == "indi_simulator_ccd"


def test_driver_collection_by_binary_not_found(xmldir):
    """by_binary returns None for unknown binary."""
    collection = DriverCollection(xmldir)
    assert collection.by_binary("/usr/bin/nonexistent") is None


def test_driver_collection_by_label_partial_match(xmldir):
    """by_label finds driver via partial match when label starts with driver label."""
    collection = DriverCollection(xmldir)
    # "CCD Simulator" is in collection. Search for longer string that starts with it.
    driver = collection.by_label("CCD Simulator")
    assert driver is not None
    # Partial match: label "CCD Simulator" matches search "CCD Simulator" (exact).
    # For true partial: search "CCD Simulator Pro" - no such driver exists.
    # Add custom driver "CCD Simulator Pro", then search "CCD Simulator Pro" = exact.
    # For partial we need: driver "CCD Simulator", search "CCD Simulator - Extended"
    # "CCD Simulator - Extended".startswith("CCD Simulator") is True.
    driver = collection.by_label("CCD Simulator - Extended")
    assert driver is not None
    assert driver.label == "CCD Simulator"


def test_driver_collection_apply_rules(xmldir):
    """apply_rules sets driver.rule for matching Driver key."""
    collection = DriverCollection(xmldir)
    rules = [
        {"Driver": "CCD Simulator", "PreDelay": 2, "PostScript": "/bin/true"},
    ]
    collection.apply_rules(rules)
    driver = collection.by_label("CCD Simulator")
    assert driver is not None
    assert driver.rule == rules[0]


def test_driver_collection_apply_rules_empty(xmldir):
    """apply_rules with empty list or None is a no-op."""
    collection = DriverCollection(xmldir)
    collection.apply_rules([])
    collection.apply_rules(None)
    driver = collection.by_label("CCD Simulator")
    assert driver is not None
    assert driver.rule is None
