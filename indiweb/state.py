"""Application state types for INDI Web Manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from .paa_monitor import PaaMonitor

from .database import Database
from .device import Device
from .driver import DriverCollection
from .indi_server import IndiServer


@dataclass
class AppState:
    """Typed application state stored on the FastAPI app."""

    db: Database
    collection: DriverCollection
    indi_server: IndiServer
    indi_device: Device
    args: Any  # argparse.Namespace from parse_args()
    templates: Jinja2Templates
    hostname: str
    saved_profile: str | None
    active_profile: str
    paa_monitor: PaaMonitor | None = None


class IndiWebApp(FastAPI):
    """FastAPI application with typed AppState."""

    state: AppState  # type: ignore[assignment]
