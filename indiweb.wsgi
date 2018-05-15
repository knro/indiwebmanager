import sys
import bottle

# add this, if you have the indiwebmanager installed in a separate place
# sys.path.insert(0, '<path to indiwebmanager')

application = bottle.default_app()

import indiweb.main