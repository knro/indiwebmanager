"""IndiServer unit tests. Mocks only subprocess.call/check_output at boundary."""

from unittest.mock import patch

import pytest

from indiweb.driver import DeviceDriver
from indiweb.indi_server import IndiServer


@pytest.fixture
def fifo_path(tmp_path):
    """Temporary FIFO path for tests."""
    return str(tmp_path / "indi_fifo")


@pytest.fixture
def indi_server(fifo_path):
    """IndiServer instance with temp fifo."""
    return IndiServer(fifo=fifo_path)


@pytest.fixture
def sample_driver():
    """Sample DeviceDriver for tests."""
    return DeviceDriver(
        name="CCD Simulator",
        label="CCD Simulator",
        version="1.0",
        binary="indi_simulator_ccd",
        family="CCDs",
    )


@patch("indiweb.indi_server.call")
def test_start_driver_builds_fifo_command(mock_call, indi_server, sample_driver):
    """start_driver builds correct echo command and calls subprocess."""
    indi_server.start_driver(sample_driver)
    mock_call.assert_called_once()
    call_args = mock_call.call_args[0][0]
    assert "echo" in call_args
    assert "start" in call_args
    assert "indi_simulator_ccd" in call_args
    assert "CCD Simulator" in call_args
    assert indi_server.get_running_drivers()["CCD Simulator"] == sample_driver


@patch("indiweb.indi_server.call")
def test_stop_driver_builds_stop_command(mock_call, indi_server, sample_driver):
    """stop_driver builds correct stop command."""
    indi_server.start_driver(sample_driver)
    mock_call.reset_mock()
    indi_server.stop_driver(sample_driver)
    call_args = mock_call.call_args[0][0]
    assert "stop" in call_args
    assert "indi_simulator_ccd" in call_args
    assert "CCD Simulator" in call_args


@patch("indiweb.indi_server.call")
def test_start_driver_missing_binary_returns_early(mock_call, indi_server):
    """start_driver returns early when driver has no binary attribute."""
    driver_no_binary = type("DriverNoBinary", (), {"label": "BadDriver"})()
    indi_server.start_driver(driver_no_binary)
    mock_call.assert_not_called()


@patch("indiweb.indi_server.call")
def test_get_running_drivers_after_start(mock_call, indi_server, sample_driver):
    """get_running_drivers returns drivers added by start_driver."""
    assert indi_server.get_running_drivers() == {}
    indi_server.start_driver(sample_driver)
    drivers = indi_server.get_running_drivers()
    assert "CCD Simulator" in drivers
    assert drivers["CCD Simulator"].label == "CCD Simulator"


def test_is_running_false_when_not_started(indi_server):
    """is_running returns False when server was never started."""
    assert indi_server.is_running() is False
