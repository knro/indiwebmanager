#!/usr/bin/env python

import argparse
import logging
import os
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .database import Database
from .device import Device
from .driver import INDI_DATA_DIR, DriverCollection
from .indi_server import INDI_CONFIG_DIR, INDI_FIFO, INDI_PORT, IndiServer
from .paa_monitor import PaaMonitor, _default_kstars_log_dirs, paa_router
from .routes import router, start_profile
from .state import AppState, IndiWebApp

# default settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 8624
WEB_CORS = ["http://localhost", "http://127.0.0.1"]

pkg_path, _ = os.path.split(os.path.abspath(__file__))
views_path = os.path.join(pkg_path, 'views')


def _build_parser():
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description='INDI Web Manager. '
        'A simple web application to manage an INDI server')
    parser.add_argument('--indi-port', '-p', type=int, default=INDI_PORT,
                        help='indiserver port (default: %d)' % INDI_PORT)
    parser.add_argument('--port', '-P', type=int, default=WEB_PORT,
                        help='Web server port (default: %d)' % WEB_PORT)
    parser.add_argument('--host', '-H', default=WEB_HOST,
                        help='Bind web server to this interface (default: %s)' %
                        WEB_HOST)
    parser.add_argument('--cors', '-C', default=list(WEB_CORS), nargs='+',
                        help='Allowed domain for cross-origin policy (default: %s)' %
                        WEB_CORS)
    parser.add_argument('--fifo', '-f', default=INDI_FIFO,
                        help='indiserver FIFO path (default: %s)' % INDI_FIFO)
    parser.add_argument('--conf', '-c', default=INDI_CONFIG_DIR,
                        help='INDI config. directory (default: %s)' % INDI_CONFIG_DIR)
    parser.add_argument('--xmldir', '-x', default=INDI_DATA_DIR,
                        help='INDI XML directory (default: %s)' % INDI_DATA_DIR)
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print more messages')
    parser.add_argument('--logfile', '-l', help='log file name')
    parser.add_argument('--server', '-s', default='standalone',
                        help='HTTP server [standalone|apache] (default: standalone')
    parser.add_argument('--sudo', '-S', action='store_true',
                        help='Run poweroff/reboot commands with sudo')
    parser.add_argument('--kstars-logs', default=None, nargs='+',
                        help='KStars/Ekos log directory/ies. Default: search native and Flatpak locations')
    parser.add_argument('--with-paa', action='store_true',
                        help='Enable the PAA (Polar Alignment Assistant) live monitor')
    return parser


def parse_args(argv=None):
    """Parse command line arguments. If argv is None, uses sys.argv."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Add origins with current port if they don't exist
    extra_origins = []
    for origin in args.cors:
        if ":" not in origin.replace("http://", "").replace("https://", ""):
            port_origin = f"{origin}:{args.port}"
            if port_origin not in args.cors:
                extra_origins.append(port_origin)
    args.cors.extend(extra_origins)
    return args


@asynccontextmanager
async def _lifespan(app: IndiWebApp):
    """Application lifespan: clean up PAA monitor on shutdown."""
    yield
    if app.state.paa_monitor is not None:
        await app.state.paa_monitor.shutdown()


def create_app(argv=None):
    """
    Create and configure the FastAPI application.
    If argv is None, parses from sys.argv. Call this from main() or from
    the WSGI entry point after setting sys.argv as needed.
    """
    if argv is None:
        args = parse_args()
    elif isinstance(argv, list):
        args = parse_args(argv)
    else:
        args = argv  # argv is already parsed args (e.g. from main())

    logging_level = logging.DEBUG if args.verbose else logging.WARNING
    if args.logfile:
        logging.basicConfig(filename=args.logfile,
                            format='%(asctime)s - %(levelname)s: %(message)s',
                            level=logging_level)
    else:
        from uvicorn.logging import DefaultFormatter
        handler = logging.StreamHandler()
        handler.setFormatter(DefaultFormatter("%(levelprefix)s %(message)s"))
        logging.root.addHandler(handler)
        logging.root.setLevel(logging_level)
    logging.debug("command line arguments: " + str(vars(args)))

    collection = DriverCollection(args.xmldir)
    indi_server = IndiServer(args.fifo, args.conf)
    indi_device = Device()
    db_path = os.path.join(args.conf, 'profiles.db')
    db = Database(db_path)
    collection.parse_custom_drivers(db.get_custom_drivers())

    templates = Jinja2Templates(directory=views_path)
    paa_monitor = None
    if getattr(args, 'with_paa', False):
        kstars_log_dirs = args.kstars_logs or [str(d) for d in _default_kstars_log_dirs()]
        paa_monitor = PaaMonitor(kstars_log_dirs)
    app = IndiWebApp(title="INDI Web Manager", version=__version__, lifespan=_lifespan)
    app.state = AppState(
        db=db,
        collection=collection,
        indi_server=indi_server,
        indi_device=indi_device,
        args=args,
        templates=templates,
        hostname=socket.gethostname(),
        saved_profile=None,
        active_profile="",
        paa_monitor=paa_monitor,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=args.cors,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.mount("/static", StaticFiles(directory=views_path), name="static")
    app.mount("/favicon.ico", StaticFiles(directory=views_path), name="favicon.ico")

    app.include_router(router)
    if paa_monitor is not None:
        app.include_router(paa_router)
    return app


def main():
    """
    Main function to start the indiwebmanager application.
    Starts the autostart profile if configured and runs the web server.
    """
    args = parse_args()
    app = create_app(args)

    for profile in app.state.db.get_profiles():
        if profile['autostart']:
            start_profile(app.state, profile['name'])
            app.state.active_profile = profile['name']
            break

    uvicorn.run(app, host=args.host, port=args.port)
    logging.info("Exiting")


# JM 2018-12-24: Added __main__ so I can debug this as a module in PyCharm
# Otherwise, I couldn't get it to run main as all
if __name__ == '__main__':
    main()
