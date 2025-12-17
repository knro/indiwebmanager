import sys

# add this, if you have the indiwebmanager installed in a separate place
# sys.path.insert(0, '<path to indiwebmanager>')

sys.argv += ['-v', '--server', 'apache', '-l', '/tmp/wsgi.log']

# Import the FastAPI app from main.py
from indiweb.main import app

# FastAPI is an ASGI application, but Apache mod_wsgi expects WSGI
# Use asgiref's WsgiToAsgi adapter to bridge ASGI to WSGI
from asgiref.wsgi import WsgiToAsgi

# Wrap the FastAPI (ASGI) app for WSGI compatibility
application = WsgiToAsgi(app)
