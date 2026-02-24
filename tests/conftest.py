"""Pytest fixtures for indiwebmanager tests."""

import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

# Path to fixture XML (used when /usr/share/indi is not available)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_XML_DIR = os.path.join(FIXTURES_DIR, "xml")


@pytest.fixture
def tmp_conf():
    """Temporary config directory for tests. Cleaned up after test."""
    d = tempfile.mkdtemp(prefix="indiweb_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def xmldir():
    """XML directory for DriverCollection. Uses fixture XML for portability."""
    if os.path.isdir(FIXTURE_XML_DIR):
        return FIXTURE_XML_DIR
    # Fallback to system INDI dir when running in Docker/CI with INDI installed
    system_dir = "/usr/share/indi"
    if os.path.isdir(system_dir):
        return system_dir
    return FIXTURE_XML_DIR


@pytest.fixture
def test_app(tmp_conf, xmldir):
    """FastAPI app configured for testing with temp conf and fixture XML."""
    from indiweb.main import create_app

    fifo_path = os.path.join(tmp_conf, "indi_fifo")
    argv = [
        "--conf",
        tmp_conf,
        "--fifo",
        fifo_path,
        "--xmldir",
        xmldir,
        "--indi-port",
        "17624",  # Avoid conflict with default 7624
    ]
    return create_app(argv)


@pytest.fixture
def client(test_app):
    """TestClient for API tests."""
    return TestClient(test_app)
