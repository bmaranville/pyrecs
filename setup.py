#!/usr/bin/env python

from distutils.core import setup

setup(name='PyReCS',
      version='1.0',
      description='Python Reflectometer Control System',
      author='Brian Ben Maranville',
      author_email='brian.maranville@nist.gov',
      url='http://ncnr.nist.gov/instruments/magik',
      packages=['pyrecs',
        'pyrecs.gui',
        'pyrecs.gui.wx',
        'pyrecs.gui.web',
        'pyrecs.drivers', 
        'pyrecs.extras',
        'pyrecs.mixins',
        'pyrecs.icp_compat',
        'pyrecs.publishers',
        'pyrecs.lib'],
     )
