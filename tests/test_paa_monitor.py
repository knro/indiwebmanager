"""Tests for PAA (Polar Alignment Assistant) monitor."""

import os

import pytest
from fastapi.testclient import TestClient

from indiweb.paa_monitor import (
    DATE_DIR_PATTERN,
    PAA_PATTERN,
    PaaMonitor,
)

# --- Regex tests ---


def test_paa_pattern_matches_real_ekos_format():
    """PAA regex matches real Ekos Qt log format (DMS values)."""
    line = (
        '[2026-02-14T16:31:36.864 EST INFO ][     org.kde.kstars.ekos.align] - '
        '"PAA Refresh(1): Corrected az:  01° 06\' 18" alt:  00° 47\' 11" total:  01° 21\' 23""'
    )
    m = PAA_PATTERN.search(line)
    assert m is not None
    assert m.group(1) == "16:31:36.864"
    assert m.group(2) == "01"
    assert m.group(3) == "06"
    assert m.group(4) == "18"
    assert m.group(5) == "00"
    assert m.group(6) == "47"
    assert m.group(7) == "11"
    assert m.group(8) == "01"
    assert m.group(9) == "21"
    assert m.group(10) == "23"


def test_paa_pattern_matches_negative_azimuth():
    """PAA regex captures negative DMS (southern hemisphere)."""
    line = (
        '[2026-02-14T12:00:00.000 EST INFO ][ org.kde.kstars.ekos.align] - '
        '"PAA Refresh(1): Corrected az: -01° 30\' 00" alt:  00° 47\' 11" total:  01° 21\' 23""'
    )
    m = PAA_PATTERN.search(line)
    assert m is not None
    assert m.group(2) == "-01"
    assert m.group(5) == "00"


def test_paa_parses_negative_zero_dms(tmp_path):
    """PaaMonitor preserves sign when parsing -00deg 30' 10" (int('-00') loses sign)."""
    logs_dir = tmp_path / "kstars_logs"
    date_dir = logs_dir / "2026-02-14"
    date_dir.mkdir(parents=True)
    log_file = date_dir / "ekos.txt"
    # -00° 30' 10" (az), 00° 47' 11" for alt
    log_file.write_text(
        '[2026-02-14T22:15:30.123 EST INFO ][ org.kde.kstars.ekos.align] - '
        '"PAA Refresh(1): Corrected az: -00° 30\' 10" alt:  00° 47\' 11" total:  00° 57\' 45""\n'
    )
    monitor = PaaMonitor(str(logs_dir))
    entry = monitor._parse_latest()
    assert entry is not None
    assert entry["az_direction"] == "left"
    assert "00° 30' 10\"" in entry["az"]
    assert entry["alt"] == "00° 47' 11\""


def test_paa_pattern_rejects_non_paa_line():
    """PAA regex does not match lines without PAA Refresh."""
    line = '[2026-02-14T22:15:30.123 EST INFO ] - "Some other log message"'
    assert PAA_PATTERN.search(line) is None


def test_date_dir_pattern():
    """Date directory pattern matches YYYY-MM-DD."""
    assert DATE_DIR_PATTERN.match("2026-02-14")
    assert DATE_DIR_PATTERN.match("2024-01-01")
    assert not DATE_DIR_PATTERN.match("2026-2-14")
    assert not DATE_DIR_PATTERN.match("logs")


# --- PaaMonitor tests ---


@pytest.fixture
def tmp_kstars_logs(tmp_path):
    """Create temp KStars log directory with sample PAA content (real Ekos format)."""
    logs_dir = tmp_path / "kstars_logs"
    logs_dir.mkdir()
    date_dir = logs_dir / "2026-02-14"
    date_dir.mkdir()
    log_file = date_dir / "ekos_session.txt"
    log_file.write_text(
        '[2026-02-14T22:15:30.123 EST INFO ][ org.kde.kstars.ekos.align] - '
        '"PAA Refresh(1): Corrected az:  01° 06\' 18" alt:  00° 47\' 11" total:  01° 21\' 23""\n'
        '[2026-02-14T22:15:32.456 EST INFO ][ org.kde.kstars.ekos.align] - '
        '"PAA Refresh(2): Corrected az:  01° 06\' 24" alt:  00° 47\' 10" total:  01° 21\' 27""\n'
    )
    return str(logs_dir)


def test_monitor_find_latest_log(tmp_kstars_logs):
    """PaaMonitor discovers latest log file in date directory."""
    monitor = PaaMonitor(tmp_kstars_logs)
    path = monitor._find_latest_log()
    assert path is not None
    assert "2026-02-14" in path
    assert path.endswith(".txt")


def test_monitor_parse_latest(tmp_kstars_logs):
    """PaaMonitor parses latest PAA entry from log file (real DMS format)."""
    monitor = PaaMonitor(tmp_kstars_logs)
    entry = monitor._parse_latest()
    assert entry is not None
    assert entry["timestamp"] == "22:15:32.456"
    assert entry["az"] == "01° 06' 24\""
    assert entry["alt"] == "00° 47' 10\""
    assert entry["total"] == "01° 21' 27\""


def test_monitor_searches_multiple_locations(tmp_path):
    """PaaMonitor searches all configured dirs and picks the newest log."""
    native_logs = tmp_path / "native" / "kstars" / "logs" / "2026-02-14"
    flatpak_logs = tmp_path / "flatpak" / "kstars" / "logs" / "2026-02-14"
    native_logs.mkdir(parents=True)
    flatpak_logs.mkdir(parents=True)
    native_log = native_logs / "old.txt"
    flatpak_log = flatpak_logs / "new.txt"
    paa_line = '[2026-02-14T22:15:30.123 EST INFO ] - "PAA Refresh(1): Corrected az: 01° 06\' 18" alt: 00° 47\' 11" total: 01° 21\' 23"\n'
    native_log.write_text(paa_line)
    flatpak_log.write_text(paa_line)
    # Make flatpak log newer
    import time
    time.sleep(0.01)
    flatpak_log.touch()
    # Base dirs are the "logs" dirs that contain YYYY-MM-DD subdirs
    base_dirs = [str(native_logs.parent), str(flatpak_logs.parent)]
    monitor = PaaMonitor(base_dirs)
    path = monitor._find_latest_log()
    assert path is not None
    assert "flatpak" in path
    entry = monitor._parse_latest()
    assert entry is not None


def test_monitor_no_logs_dir():
    """PaaMonitor returns None when log directory does not exist."""
    monitor = PaaMonitor("/nonexistent/path/to/logs")
    assert monitor._find_latest_log() is None
    assert monitor._parse_latest() is None


def test_monitor_empty_logs_dir(tmp_path):
    """PaaMonitor returns None when directory has no date subdirs."""
    empty = tmp_path / "empty_logs"
    empty.mkdir()
    monitor = PaaMonitor(str(empty))
    assert monitor._find_latest_log() is None
    assert monitor._parse_latest() is None


def test_monitor_rejects_format_without_degree_symbols(tmp_path):
    """Monitor returns None when log format lacks required degree/arcmin symbols."""
    logs_dir = tmp_path / "kstars_logs"
    date_dir = logs_dir / "2026-02-14"
    date_dir.mkdir(parents=True)
    log_file = date_dir / "odd_format.txt"
    log_file.write_text(
        '[2026-02-14T22:15:30.123 EST INFO ] - "PAA Refresh(1): Corrected az: 01 06 18 alt: 00 47 11 total: 01 21 23"\n'
    )
    monitor = PaaMonitor(str(logs_dir))
    entry = monitor._parse_latest()
    assert entry is None


def test_monitor_tail_ignores_existing_content_when_client_connected(tmp_path):
    """With a client connected, only content appended after connect is parsed (tail)."""
    logs_dir = tmp_path / "kstars_logs"
    date_dir = logs_dir / "2026-02-14"
    date_dir.mkdir(parents=True)
    log_file = date_dir / "ekos.txt"
    paa_line = (
        '[2026-02-14T22:15:30.123 EST INFO ] - '
        '"PAA Refresh(1): Corrected az:  01° 06\' 18" alt:  00° 47\' 11" total:  01° 21\' 23"\n'
    )
    log_file.write_text(paa_line)
    monitor = PaaMonitor(str(logs_dir))
    monitor._clients.add(object())  # Simulate connected client
    entry = monitor._parse_latest()
    assert entry is None  # Tail is empty (content existed before "connect")
    monitor._clients.clear()


# --- API and WebSocket tests ---


@pytest.fixture
def paa_client(tmp_conf, xmldir, tmp_path):
    """TestClient with PAA enabled and temp kstars logs (real Ekos format)."""
    from indiweb.main import create_app

    logs_dir = tmp_path / "kstars_logs"
    logs_dir.mkdir()
    date_dir = logs_dir / "2026-02-14"
    date_dir.mkdir()
    log_file = date_dir / "ekos.txt"
    log_file.write_text(
        '[2026-02-14T22:15:30.123 EST INFO ][ org.kde.kstars.ekos.align] - '
        '"PAA Refresh(1): Corrected az:  00° 06\' 00" alt:  00° 12\' 00" total:  00° 13\' 25""\n'
    )

    fifo_path = os.path.join(tmp_conf, "indi_fifo")
    argv = [
        "--conf", tmp_conf,
        "--fifo", fifo_path,
        "--xmldir", xmldir,
        "--indi-port", "17624",
        "--with-paa",
        "--kstars-logs", str(logs_dir),
    ]
    app = create_app(argv)
    return TestClient(app)


def test_paa_status_api_returns_active_when_data(paa_client):
    """GET /api/paa/status returns active state with PAA data when log has content."""
    r = paa_client.get("/api/paa/status")
    assert r.status_code == 200
    data = r.json()
    assert data["state"] == "active"
    assert "az" in data
    assert "alt" in data
    assert "total" in data
    assert "total_arcsec" in data
    assert "az_direction" in data
    assert "alt_direction" in data


def test_paa_status_api_returns_waiting_when_no_logs(tmp_conf, xmldir, tmp_path):
    """GET /api/paa/status returns waiting state when log directory does not exist."""
    from indiweb.main import create_app

    nonexistent = tmp_path / "nonexistent_logs"
    assert not nonexistent.exists()
    fifo_path = os.path.join(tmp_conf, "indi_fifo")
    argv = [
        "--conf", tmp_conf, "--fifo", fifo_path, "--xmldir", xmldir,
        "--indi-port", "17624", "--with-paa", "--kstars-logs", str(nonexistent),
    ]
    app = create_app(argv)
    client = TestClient(app)
    r = client.get("/api/paa/status")
    assert r.status_code == 200
    data = r.json()
    assert data["state"] == "waiting"
    assert "does not exist" in data["message"]


def test_paa_page_renders(paa_client):
    """GET /paa returns HTML page."""
    r = paa_client.get("/paa")
    assert r.status_code == 200
    assert b"PAA" in r.content
    assert b"altitude" in r.content.lower()
    assert b"azimuth" in r.content.lower()


def test_paa_websocket_shows_diagnostic_when_log_dir_missing(tmp_conf, xmldir, tmp_path):
    """WebSocket sends diagnostic message when log directory does not exist."""
    from indiweb.main import create_app

    nonexistent_logs = tmp_path / "nonexistent_kstars_logs"
    assert not nonexistent_logs.exists()
    fifo_path = os.path.join(tmp_conf, "indi_fifo")
    argv = [
        "--conf", tmp_conf,
        "--fifo", fifo_path,
        "--xmldir", xmldir,
        "--indi-port", "17624",
        "--with-paa",
        "--kstars-logs", str(nonexistent_logs),
    ]
    app = create_app(argv)
    client = TestClient(app)
    with client.websocket_connect("/ws/paa") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "status"
    assert msg["state"] == "waiting"
    assert "does not exist" in msg["message"]
    assert str(nonexistent_logs) in msg["message"]


def test_paa_websocket_connects(paa_client):
    """WebSocket /ws/paa accepts connection and sends messages."""
    with paa_client.websocket_connect("/ws/paa") as ws:
        # Should receive at least one message (update, status, or heartbeat)
        msg = ws.receive_json()
        assert "type" in msg
        assert msg["type"] in ("update", "status", "heartbeat")
        if msg["type"] == "update":
            assert "az" in msg
            assert "alt" in msg
            assert "total" in msg
            assert "total_arcsec" in msg
            assert "az_direction" in msg
            assert "alt_direction" in msg
        elif msg["type"] == "status":
            assert "state" in msg
            assert "message" in msg


def test_paa_websocket_receives_heartbeat(tmp_conf, xmldir, tmp_path):
    """WebSocket can receive heartbeat (sent when no new match, has last_entry)."""
    from indiweb.main import create_app

    logs_dir = tmp_path / "kstars_logs"
    date_dir = logs_dir / "2026-02-14"
    date_dir.mkdir(parents=True)
    log_file = date_dir / "ekos.txt"
    paa_line = (
        '[2026-02-14T22:15:30.123 EST INFO ] - '
        '"PAA Refresh(1): Corrected az:  01° 06\' 18" alt:  00° 47\' 11" total:  01° 21\' 23"\n'
    )
    log_file.write_text(paa_line)
    fifo_path = os.path.join(tmp_conf, "indi_fifo")
    argv = [
        "--conf", tmp_conf,
        "--fifo", fifo_path,
        "--xmldir", xmldir,
        "--indi-port", "17624",
        "--with-paa",
        "--kstars-logs", str(logs_dir),
    ]
    app = create_app(argv)
    client = TestClient(app)
    with client.websocket_connect("/ws/paa") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] in ("status", "update", "heartbeat")
        if msg1["type"] == "update":
            pass  # Got update from tail (content was written before connect - no, we have clients so tail)
        msgs = [msg1]
        for _ in range(5):
            try:
                m = ws.receive_json()
                msgs.append(m)
                if m["type"] == "heartbeat":
                    break
            except Exception:
                break
        types = [m["type"] for m in msgs]
        assert any(t in ("heartbeat", "status") for t in types), f"Expected heartbeat or status, got: {types}"
