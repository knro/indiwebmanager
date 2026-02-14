"""Layer 2: API tests. Uses TestClient with temp conf, no indiserver."""


def test_get_profiles(client):
    """GET /api/profiles returns list of profiles."""
    r = client.get("/api/profiles")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(p["name"] == "Simulators" for p in data)


def test_get_profile_simulators(client):
    """GET /api/profiles/Simulators returns profile info."""
    r = client.get("/api/profiles/Simulators")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Simulators"
    assert "port" in data
    assert "autostart" in data
    assert "autoconnect" in data


def test_get_profile_not_found(client):
    """GET /api/profiles/Nonexistent returns 404."""
    r = client.get("/api/profiles/Nonexistent")
    assert r.status_code == 404


def test_add_profile(client):
    """POST /api/profiles/{name} adds a new profile."""
    r = client.post("/api/profiles/TestProfile")
    assert r.status_code == 200
    assert r.json()["message"] == "Profile TestProfile added"
    r2 = client.get("/api/profiles/TestProfile")
    assert r2.status_code == 200
    assert r2.json()["name"] == "TestProfile"


def test_delete_profile(client):
    """DELETE /api/profiles/{name} removes profile."""
    client.post("/api/profiles/ToDelete")
    r = client.delete("/api/profiles/ToDelete")
    assert r.status_code == 200
    r2 = client.get("/api/profiles/ToDelete")
    assert r2.status_code == 404


def test_get_profile_labels(client):
    """GET /api/profiles/Simulators/labels returns driver labels."""
    r = client.get("/api/profiles/Simulators/labels")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    labels = [d["label"] for d in data]
    assert "Telescope Simulator" in labels
    assert "CCD Simulator" in labels
    assert "Focuser Simulator" in labels


def test_get_profile_remote(client):
    """GET /api/profiles/Simulators/remote returns remote drivers (empty by default)."""
    r = client.get("/api/profiles/Simulators/remote")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_server_status_offline(client):
    """GET /api/server/status returns status when server is offline."""
    r = client.get("/api/server/status")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["status"] == "False"


def test_server_drivers_empty_when_offline(client):
    """GET /api/server/drivers returns empty list when server is offline."""
    r = client.get("/api/server/drivers")
    assert r.status_code == 200
    assert r.json() == []


def test_info_version(client):
    """GET /api/info/version returns version."""
    r = client.get("/api/info/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "." in data["version"]


def test_info_hostname(client):
    """GET /api/info/hostname returns hostname."""
    r = client.get("/api/info/hostname")
    assert r.status_code == 200
    data = r.json()
    assert "hostname" in data


def test_info_arch(client):
    """GET /api/info/arch returns architecture."""
    r = client.get("/api/info/arch")
    assert r.status_code == 200
    arch = r.json()
    assert isinstance(arch, str)
    assert arch in ("x86_64", "arm64", "armhf", "aarch64", "amd64")


def test_update_profile(client):
    """PUT /api/profiles/{name} updates profile settings."""
    client.post("/api/profiles/UpdateMe")
    r = client.put(
        "/api/profiles/UpdateMe",
        json={
            "port": 9999,
            "autostart": 1,
            "autoconnect": 1,
            "scripts": "[]",
        },
    )
    assert r.status_code == 200
    r2 = client.get("/api/profiles/UpdateMe")
    assert r2.json()["port"] == 9999
    assert r2.json()["autostart"] == 1
    assert r2.json()["autoconnect"] == 1


def test_save_profile_drivers(client):
    """POST /api/profiles/{name}/drivers saves drivers for profile."""
    client.post("/api/profiles/DriverTest")
    r = client.post(
        "/api/profiles/DriverTest/drivers",
        json=[{"label": "CCD Simulator"}, {"label": "Telescope Simulator"}],
    )
    assert r.status_code == 200
    r2 = client.get("/api/profiles/DriverTest/labels")
    labels = [d["label"] for d in r2.json()]
    assert "CCD Simulator" in labels
    assert "Telescope Simulator" in labels


def test_get_main_form(client):
    """GET / returns main form HTML with profiles and drivers."""
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    html = r.text
    assert "Simulators" in html
    assert "CCD Simulator" in html or "Telescope Simulator" in html


def test_post_profiles_custom_add(client):
    """POST /api/profiles/custom/add adds custom driver to db and collection."""
    r = client.post(
        "/api/profiles/custom/add",
        json={
            "Label": "My Custom Driver",
            "Name": "Custom",
            "Family": "Custom",
            "Exec": "/usr/bin/custom_driver",
            "Version": "1.0",
        },
    )
    assert r.status_code == 200
    assert "Custom driver saved" in r.json()["message"]
    r2 = client.get("/api/drivers")
    drivers = r2.json()
    labels = [d["label"] for d in drivers]
    assert "My Custom Driver" in labels


def test_get_profile_remote_with_drivers(client):
    """GET /api/profiles/{item}/remote returns remote drivers when present."""
    client.post("/api/profiles/RemoteProfile")
    client.post(
        "/api/profiles/RemoteProfile/drivers",
        json=[{"remote": "remote@host.example"}],
    )
    r = client.get("/api/profiles/RemoteProfile/remote")
    assert r.status_code == 200
    data = r.json()
    assert data == {"drivers": "remote@host.example"}


def test_get_drivers_groups(client):
    """GET /api/drivers/groups returns sorted family names."""
    r = client.get("/api/drivers/groups")
    assert r.status_code == 200
    groups = r.json()
    assert isinstance(groups, list)
    assert groups == sorted(groups)
    assert "CCDs" in groups
    assert "Telescopes" in groups
    assert "Focusers" in groups


def test_get_drivers(client):
    """GET /api/drivers returns all drivers from collection."""
    r = client.get("/api/drivers")
    assert r.status_code == 200
    drivers = r.json()
    assert isinstance(drivers, list)
    assert len(drivers) >= 3
    labels = [d["label"] for d in drivers]
    assert "CCD Simulator" in labels
    assert "Telescope Simulator" in labels
    assert "Focuser Simulator" in labels


def test_drivers_start_404(client):
    """POST /api/drivers/start/{label} returns 404 when driver not found."""
    r = client.post("/api/drivers/start/NonexistentDriver")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_drivers_stop_404(client):
    """POST /api/drivers/stop/{label} returns 404 when driver not found."""
    r = client.post("/api/drivers/stop/NonexistentDriver")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_drivers_restart_404(client):
    """POST /api/drivers/restart/{label} returns 404 when driver not found."""
    r = client.post("/api/drivers/restart/NonexistentDriver")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()
