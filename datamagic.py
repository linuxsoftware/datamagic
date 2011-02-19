#!/usr/bin/python
import os
from os import path
import time
from wsgiref.simple_server import demo_app
from wsgiref.simple_server import make_server
from mako.lookup import TemplateLookup
from mako import exceptions
import password
import logging

from flup.server.fcgi import WSGIServer
#from flup.server.fcgi_fork import WSGIServer

from utils import AsyncWebFetcher

class SaveYourselfServer(WSGIServer):
    def _hupHandler(self, signum, frame):
        AsyncWebFetcher.shuttingDown(signum, frame)
        WSGIServer._hupHandler(self, signum, frame)

    def _intHandler(self, signum, frame):
        AsyncWebFetcher.shuttingDown(signum, frame)
        WSGIServer._intHandler(self, signum, frame)

#import wingdbstub
#if wingdbstub.debugger != None:
#   wingdbstub.debugger.StopDebug()
#   time.sleep(1)
#   wingdbstub.debugger.StartDebug()

here = path.abspath(path.dirname(__file__))
def setupLogging(level=logging.DEBUG):
    hdlr = logging.FileHandler(path.join(here, "var", "datamagic.log"))
    format = "%(asctime)s %(name)s %(levelname)s %(message)s"
    log = logging.getLogger()
    hdlr.setFormatter(logging.Formatter(format))
    log.addHandler(hdlr)
    log.setLevel(level)

templates = path.join(here, "templates")
modules = path.join(templates, "modules")
lookup = TemplateLookup(directories=[templates],
                        input_encoding='utf-8',
                        output_encoding='utf-8',
                        filesystem_checks=True,
                        module_directory=modules)
def getTemplateName(path):
    base = "/portal"
    if path.startswith(base):
        path = path[len(base):]
    if not path or path == "/":
        path = "index.html"
    return path

def app(environ, start_response):
    """serves requests using the WSGI callable interface."""
    path = environ.get('PATH_INFO', '/')
    templateName = getTemplateName(path)
    if templateName == "/demo":
        return demo_app(environ, start_response)
    try:
        template = lookup.get_template(templateName)
        start_response("200 OK", [('Content-type','text/html')])
        try:
            return [template.render(path=path)]
        except:
            return [exceptions.html_error_template().render()]
    except exceptions.TopLevelLookupException:
        start_response("404 Not Found", [])
        return ["Cant find template '%s' for '%s'" % (templateName, path)]
    except:
        start_response("500 Server Error", [('Content-type','text/html')])
        return [exceptions.html_error_template().render()]
        

if __name__ == "__main__":
    make_server('', 8000, app).serve_forever()
