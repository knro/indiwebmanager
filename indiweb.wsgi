import sys

# add this, if you have the indiwebmanager installed in a separate place
# sys.path.insert(0, '<path to indiwebmanager>')

sys.argv += ['-v', '--server', 'apache', '-l', '/tmp/wsgi.log']

# Create the FastAPI app. sys.argv was augmented above with apache/wsgi options.
from a2wsgi import ASGIMiddleware

from indiweb.main import create_app

app = create_app()
application = ASGIMiddleware(app)
