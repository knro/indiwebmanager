"""Layer 3: Integration tests. Requires real indiserver and simulator drivers."""

import shutil

import pytest

pytestmark = pytest.mark.integration


def indiserver_available():
    """Check if indiserver is installed and in PATH."""
    return shutil.which("indiserver") is not None


@pytest.mark.skipif(not indiserver_available(), reason="indiserver not installed")
def test_start_simulators_profile_returns_all_drivers(client):
    """Start Simulators profile and verify all 3 drivers are running."""
    r = client.post("/api/server/start/Simulators")
    assert r.status_code == 200, r.text
    assert "started" in r.json()["message"].lower()

    r2 = client.get("/api/server/drivers")
    assert r2.status_code == 200
    drivers = r2.json()
    labels = [d["label"] for d in drivers]

    assert "Telescope Simulator" in labels
    assert "CCD Simulator" in labels
    assert "Focuser Simulator" in labels
    assert len(labels) >= 3

    r3 = client.post("/api/server/stop")
    assert r3.status_code == 200


@pytest.mark.skipif(not indiserver_available(), reason="indiserver not installed")
def test_server_status_online_after_start(client):
    """Server status reports online after start, offline after stop."""
    r0 = client.get("/api/server/status")
    assert r0.json()[0]["status"] == "False"

    client.post("/api/server/start/Simulators")
    r1 = client.get("/api/server/status")
    assert r1.json()[0]["status"] == "True"
    assert r1.json()[0]["active_profile"] == "Simulators"

    client.post("/api/server/stop")
    r2 = client.get("/api/server/status")
    assert r2.json()[0]["status"] == "False"


@pytest.mark.skipif(not indiserver_available(), reason="indiserver not installed")
def test_get_devices_after_start(client):
    """GET /api/devices returns device list when server is running."""
    client.post("/api/server/start/Simulators")
    r = client.get("/api/devices")
    assert r.status_code == 200
    devices = r.json()
    assert isinstance(devices, list)
    if devices:
        assert "device" in devices[0]
        assert "connected" in devices[0]
    client.post("/api/server/stop")
