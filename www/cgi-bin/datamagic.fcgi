#!/usr/bin/python2.6
import sys
import os
from os import path
import logging
home = "/home/djm/linuxsoftware/web"
sys.path.insert(0, path.join(home,'datamagic'))

from datamagic import setupLogging, app, SaveYourselfServer

from flup.server.fcgi import WSGIServer

if __name__ == '__main__':
    setupLogging(logging.ERROR)
    SaveYourselfServer(app).run()
