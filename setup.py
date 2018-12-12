#!/usr/bin/env python

from setuptools import setup
from indiweb import __version__

LONG_DESCRIPTION = """
INDI Web Manager is a simple web application to manage
`INDI server <http://www.indilib.org/develop/developer-manual/92-indi-server.html>`_
"""


setup(
    name='indiweb',
    version=__version__,
    description='A simple web application to manage INDI server',
    long_description=LONG_DESCRIPTION,
    author='Jasem Mutlaq, Juan Menendez',
    author_email='mutlaqja@ikarustech.com, juanmb@gmail.com',
    url='http://www.indilib.org/',
    packages=['indiweb'],
    package_dir={'indiweb': 'indiweb'},
    include_package_data=True,
    install_requires=['requests', 'psutil', 'bottle'],
    license='LGPL',
    zip_safe=False,
    test_suite='tests',
    platforms=['any'],
    entry_points={
        'console_scripts': ['indi-web = indiweb.main:main']
    },
    classifiers=[
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Operating System :: OS Independent',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Astronomy',
    ],
)
