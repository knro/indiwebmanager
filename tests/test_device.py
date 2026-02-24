"""Device unit tests. Mocks only subprocess.check_output to test real parsing logic."""

from unittest.mock import patch

from indiweb.device import Device


def test_device_get_devices_parses_indi_getprop_output():
    """get_devices parses indi_getprop-style output into device list."""
    fake_output = (
        "Telescope Simulator.CONNECTION.CONNECT=On\n"
        "CCD Simulator.CONNECTION.CONNECT=Off\n"
        "Focuser Simulator.CONNECTION.CONNECT=On\n"
    )
    with patch("indiweb.device.check_output", return_value=fake_output.encode("utf-8")):
        devices = Device.get_devices()
    assert len(devices) == 3
    labels = [d["device"] for d in devices]
    assert "Telescope Simulator" in labels
    assert "CCD Simulator" in labels
    assert "Focuser Simulator" in labels
    connected = {d["device"]: d["connected"] for d in devices}
    assert connected["Telescope Simulator"] is True
    assert connected["CCD Simulator"] is False
    assert connected["Focuser Simulator"] is True


def test_device_get_devices_empty_output():
    """get_devices returns empty list when output has no devices."""
    with patch("indiweb.device.check_output", return_value=b""):
        devices = Device.get_devices()
    assert devices == []


def test_device_get_devices_exception_returns_empty():
    """get_devices returns empty list on check_output exception."""
    with patch("indiweb.device.check_output", side_effect=OSError("indi_getprop not found")):
        devices = Device.get_devices()
    assert devices == []


def test_device_init_defaults():
    """Device init sets default host and port."""
    d = Device()
    assert d.host == "localhost"
    assert d.port == 7624
