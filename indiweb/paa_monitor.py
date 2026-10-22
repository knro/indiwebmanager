"""Polar Alignment Assistant (PAA) live monitor for Ekos/KStars logs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from .routes import get_state, get_state_ws
from .state import AppState

# KStars Qt log format. Arcseconds: " or \"
# Groups: 1=ts, 2-4=az dms, 5-7=alt dms, 8-10=total dms
PAA_PATTERN = re.compile(r"""
    \[ \d{4}-\d{2}-\d{2} T                          # [YYYY-MM-DDT
    (\d{2}:\d{2}:\d{2}\.\d{3})                      # (1) HH:MM:SS.mmm timestamp
    \s+ [^\]]+ \]                                    # rest of bracket header ]
    .* PAA\ Refresh                                  # PAA Refresh marker
    .* Corrected\ az: \s*                            # azimuth label
    (-?\d{1,2}) [°] \s* (\d{1,2}) ' \s* (\d{1,2})   # (2-4) az DMS: deg° min' sec
    (?:" | \\")                                      # arcsec terminator: " or \"
    .* alt: \s*                                      # altitude label
    (-?\d{1,2}) [°] \s* (\d{1,2}) ' \s* (\d{1,2})   # (5-7) alt DMS: deg° min' sec
    (?:" | \\")                                      # arcsec terminator
    .* total: \s*                                    # total label
    (\d{1,2}) [°] \s* (\d{1,2}) ' \s* (\d{1,2})     # (8-10) total DMS: deg° min' sec
    (?:" | \\")                                      # arcsec terminator
""", re.VERBOSE)

# Date directory pattern YYYY-MM-DD
DATE_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Re-discovery: when cached file hasn't been modified for this long, check for newer files
REDISCOVER_AFTER_SEC = 60

# Age after which PAA data is considered stale (no new updates)
STALE_THRESHOLD_SEC = 30

logger = logging.getLogger(__name__)

# Default KStars log locations (native and Flatpak)
def _default_kstars_log_dirs() -> list[Path]:
    """Return default KStars log directories to search (native first, then Flatpak)."""
    home = Path.home()
    return [
        home / ".local" / "share" / "kstars" / "logs",
        home / ".var" / "app" / "org.kde.kstars" / "data" / "kstars" / "logs",
    ]


def _match_to_dict(match: tuple, file_mtime: float) -> dict:
    """Build PAA result dict from regex match groups. Passes DMS as display strings."""
    az_deg_str = match[1]
    alt_deg_str = match[4]
    az_direction = "left" if az_deg_str.lstrip().startswith("-") else "right"
    alt_direction = "down" if alt_deg_str.lstrip().startswith("-") else "up"
    # Format DMS display strings: DD° MM' SS"
    az = f"{abs(int(az_deg_str)):02d}° {int(match[2]):02d}' {int(match[3]):02d}\""
    alt = f"{abs(int(alt_deg_str)):02d}° {int(match[5]):02d}' {int(match[6]):02d}\""
    total = f"{int(match[7]):02d}° {int(match[8]):02d}' {int(match[9]):02d}\""
    total_arcsec = int(match[7]) * 3600 + int(match[8]) * 60 + int(match[9])
    return {
        "timestamp": match[0],
        "az": az,
        "alt": alt,
        "total": total,
        "total_arcsec": total_arcsec,
        "az_direction": az_direction,
        "alt_direction": alt_direction,
        "file_mtime": file_mtime,
    }


class PaaMonitor:
    """Log watcher and WebSocket manager for PAA live updates."""

    def __init__(self, log_base_dirs: str | list[str]) -> None:
        """Initialize with one or more log base directories to search.
        When a list, searches all and uses the most recently modified log.
        Supports native (~/.local/share/kstars/logs) and Flatpak
        (~/.var/app/org.kde.kstars/data/kstars/logs) locations.
        """
        if isinstance(log_base_dirs, str):
            self._log_base_dirs = [Path(log_base_dirs).expanduser()]
        else:
            self._log_base_dirs = [Path(d).expanduser() for d in log_base_dirs]
        self._clients: set[WebSocket] = set()
        self._monitor_task: asyncio.Task | None = None
        self._cached_log_path: str | None = None
        self._last_entry_mtime: float = 0
        self._last_no_match_log: tuple[str, float] = ("", 0)  # (path, time) for throttling
        self._last_diagnostic: str = ""  # User-facing message when discovery/parse fails
        self._tail_path: str | None = None  # path for which _tail_offset applies
        self._tail_offset: int = 0  # byte offset: only read lines after this (set on first connect)

    def _find_latest_log_in_dir(self, base_dir: Path) -> tuple[str | None, str]:
        """Find the most recent .txt log in a single base directory.
        Returns (path, diagnostic). path is None on failure.
        """
        if not base_dir.exists():
            return None, f"Log directory does not exist: {base_dir}"

        date_dirs = []
        for entry in base_dir.iterdir():
            if entry.is_dir() and DATE_DIR_PATTERN.match(entry.name):
                date_dirs.append(entry)
        date_dirs.sort(key=lambda d: d.name, reverse=True)

        if not date_dirs:
            return None, f"No date subdirectories (YYYY-MM-DD) in {base_dir}"

        latest_dir = date_dirs[0]
        txt_files = list(latest_dir.glob("*.txt"))
        if not txt_files:
            return None, f"No .txt files in {latest_dir}"

        latest_file = max(txt_files, key=os.path.getmtime)
        return str(latest_file), ""

    def _find_latest_log(self) -> str | None:
        """Discover the most recent Ekos log file across all configured base directories.
        Searches native and Flatpak locations, picks the newest by mtime.
        """
        candidates: list[tuple[str, float]] = []  # (path, mtime)
        diagnostics: list[str] = []

        for base_dir in self._log_base_dirs:
            path, diag = self._find_latest_log_in_dir(base_dir)
            if path:
                try:
                    mtime = os.path.getmtime(path)
                    candidates.append((path, mtime))
                except OSError:
                    pass
            elif diag:
                diagnostics.append(diag)

        if candidates:
            path = max(candidates, key=lambda x: x[1])[0]
            self._last_diagnostic = ""
            return path

        if len(self._log_base_dirs) == 1:
            self._last_diagnostic = diagnostics[0] if diagnostics else f"Log directory does not exist: {self._log_base_dirs[0]}"
        else:
            checked = ", ".join(str(d) for d in self._log_base_dirs)
            self._last_diagnostic = f"No KStars log directory found. Checked: {checked}"
        logger.info("PAA monitor: %s", self._last_diagnostic)
        return None

    def _should_rediscover(self) -> bool:
        """Check if we should re-run log discovery (new session, etc)."""
        if self._cached_log_path is None:
            return True
        if not os.path.exists(self._cached_log_path):
            return True
        mtime = os.path.getmtime(self._cached_log_path)
        age = time.time() - mtime
        if age > REDISCOVER_AFTER_SEC:
            return True
        return False

    def _get_current_log_path(self) -> str | None:
        """Get the log file to read, using cache when appropriate."""
        if self._should_rediscover():
            path = self._find_latest_log()
            if path:
                self._cached_log_path = path
            else:
                self._cached_log_path = None
                self._tail_path = None
        return self._cached_log_path

    def _parse_latest(self) -> dict | None:
        """Read the discovered log file and extract the latest PAA entry from tail only.
        Only considers lines after connection (tail).
        """
        path = self._get_current_log_path()
        if not path:
            return None  # _last_diagnostic already set by _find_latest_log

        try:
            if self._tail_path is None or self._tail_path != path:
                self._tail_path = path
                if self._clients:
                    self._tail_offset = os.path.getsize(path) if os.path.exists(path) else 0
                else:
                    self._tail_offset = 0
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._tail_offset)
                content = f.read()
                self._tail_offset = f.tell()  # Next poll reads from here

            if not content:
                return None  # No new data written since last poll -- expected during tail

            matches = PAA_PATTERN.findall(content)

            if not matches:
                # Content was written but contained no PAA lines.
                # Throttle: log at most once per 30s per path to avoid flooding.
                now = time.time()
                if self._last_no_match_log[0] != path or (now - self._last_no_match_log[1]) > 30:
                    self._last_diagnostic = (
                        f"No PAA data in {path}. Enable Ekos 'Log to file' and run PAA."
                    )
                    logger.debug(
                        "PAA monitor: no regex match in %s (pattern: PAA Refresh, Corrected az: DD° MM' SS\", alt:, total:)",
                        path,
                    )
                    self._last_no_match_log = (path, now)
                return None

            self._last_diagnostic = ""
            last_match = matches[-1]
            file_mtime = os.path.getmtime(path)
            logger.debug(
                "PAA monitor: parsed ts=%s az=%s alt=%s",
                last_match[0], last_match[1], last_match[4],
            )
            return _match_to_dict(last_match, file_mtime)
        except (OSError, ValueError) as e:
            self._last_diagnostic = f"Error reading log: {e}"
            logger.warning("PAA monitor: parse error reading %s: %s", path, e)
            return None

    async def _broadcast(self, message: dict) -> None:
        """Send JSON message to all connected clients, remove dead connections."""
        dead = set()
        payload = json.dumps(message)
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception:
                logger.debug("Dropping dead PAA WebSocket client")
                dead.add(ws)
        for ws in dead:
            self._clients.discard(ws)

    def _entry_payload(self, entry: dict) -> dict:
        """Copy entry for client (exclude file_mtime)."""
        return {k: v for k, v in entry.items() if k != "file_mtime"}

    async def _monitor_loop(self) -> None:
        """Poll logs periodically and broadcast updates to WebSocket clients.
        Only broadcasts full update when a new PAA match is found; otherwise sends heartbeat.
        Poll interval adapts: 1.5s active, 3s stale, 5s waiting.
        """
        last_entry: dict | None = None
        while self._clients:
            entry = self._parse_latest()
            now = time.time()
            poll_delay = 1.5  # default: active

            if entry:
                age = now - entry["file_mtime"]
                last_entry = entry
                self._last_entry_mtime = entry["file_mtime"]
                msg = self._entry_payload(entry)

                if age > STALE_THRESHOLD_SEC:
                    msg.update(type="status", state="stale", message=f"No new PAA data for {int(age)}s")
                    await self._broadcast(msg)
                    poll_delay = 3.0
                else:
                    msg.update(type="update", state="active")
                    await self._broadcast(msg)
            else:
                if last_entry:
                    age = now - self._last_entry_mtime
                    if age > STALE_THRESHOLD_SEC:
                        msg = self._entry_payload(last_entry)
                        msg.update(type="status", state="stale", message=f"No new PAA data for {int(age)}s")
                        await self._broadcast(msg)
                        poll_delay = 3.0
                    else:
                        await self._broadcast({"type": "heartbeat"})
                else:
                    message_text = (
                        self._last_diagnostic if self._last_diagnostic else "Waiting for PAA data..."
                    )
                    await self._broadcast({
                        "type": "status",
                        "state": "waiting",
                        "message": message_text,
                    })
                    poll_delay = 5.0

            await asyncio.sleep(poll_delay)

    def connect(self, ws: WebSocket) -> None:
        """Register a WebSocket client and start monitor loop if first client."""
        self._clients.add(ws)
        if len(self._clients) == 1 and (self._monitor_task is None or self._monitor_task.done()):
            self._tail_path = None  # Force fresh tail offset for new connection
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    def disconnect(self, ws: WebSocket) -> None:
        """Unregister a WebSocket client."""
        self._clients.discard(ws)

    async def shutdown(self) -> None:
        """Cancel the monitor task if running. Call from app shutdown/lifespan."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self._clients.clear()

    def get_status(self) -> dict:
        """Return current PAA status as a serializable dict (read-only, no tail mutation).

        Unlike ``_parse_latest`` this performs a standalone full-file read so it
        can be called safely from the REST endpoint without interfering with the
        WebSocket tail state.
        """
        path = self._find_latest_log()
        if not path:
            return {
                "state": "waiting",
                "message": self._last_diagnostic or "Waiting for PAA data...",
            }
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            matches = PAA_PATTERN.findall(content)
            if not matches:
                return {
                    "state": "waiting",
                    "message": f"No PAA data in {path}. Enable Ekos 'Log to file' and run PAA.",
                }
            last_match = matches[-1]
            file_mtime = os.path.getmtime(path)
            entry = _match_to_dict(last_match, file_mtime)
            payload = {k: v for k, v in entry.items() if k != "file_mtime"}
            return {"state": "active", **payload}
        except (OSError, ValueError) as e:
            return {"state": "waiting", "message": f"Error reading log: {e}"}


paa_router = APIRouter()


@paa_router.get("/paa", response_class=HTMLResponse)
async def paa_page(request: Request, state: AppState = Depends(get_state)):
    """Render the PAA monitor page."""
    return state.templates.TemplateResponse(request, "paa.tpl", {})


@paa_router.get("/api/paa/status", tags=["PAA"])
async def paa_status(state: AppState = Depends(get_state)):
    """Get current PAA status (REST API)."""
    monitor = state.paa_monitor
    if monitor is None:
        return JSONResponse({"state": "disabled"})
    return JSONResponse(monitor.get_status())


@paa_router.websocket("/ws/paa")
async def paa_websocket(websocket: WebSocket, state: AppState = Depends(get_state_ws)):
    """WebSocket endpoint for live PAA updates."""
    monitor = state.paa_monitor
    if monitor is None:
        await websocket.close()
        return
    await websocket.accept()
    monitor.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("PAA WebSocket connection error", exc_info=True)
    finally:
        monitor.disconnect(websocket)
