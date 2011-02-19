# ===========================================================================
# Copyright 2007-2010, D J Moore
# ===========================================================================

import os
import os.path
import sys
import urllib
import time
import asyncore
import socket
import urlparse
from cStringIO import StringIO
from email.parser import HeaderParser
import logging
from cPickle import dump, load
import signal
SignalNames = dict([(y,x) for x,y in signal.__dict__.items() if x.startswith("SIG")])
del signal
from signal import signal, SIGINT, SIGTERM, SIGHUP


def readPage(url):
    """Reads a web page off a website"""
    net = None
    page = ''
    for retry in range(2):
        if retry:
            print "Retrying #", retry
            time.sleep(0.50)
        try:
            net = urllib.urlopen(url)
            page = net.read()
            break
        except:
            pass
    if net is not None:
        net.close()
    return page


class __AsyncWebFetcher(object):
    """Reads a bunch of web pages asynchronously"""
    FromWeb, FromDisk, FromMem = range(3)

    def __init__(self):
        self.requests = {}
        self.log  = logging.getLogger("AsyncWebFetcher")
        # stats
        self.initStart   = \
        self.fetchStart  = \
        self.loopStart   = \
        self.fetchFinish = time.time()
        self.fromStats   = [0, 0, 0]
        # cache
        here = os.path.abspath(os.path.dirname(__file__))
        self.cachePath = os.path.join(here, "var", "datamagic.cache")
        self.cache = {}
        if os.path.exists(self.cachePath):
            with file(self.cachePath, "r") as fileIn:
                self.cache = load(fileIn)
        self.cacheLoaded = time.time()
        #self.oldSignals = {}
        #for sigNum in (SIGINT, SIGTERM, SIGHUP):
        #    oldHandler = signal(sigNum, self.shuttingDown)
        #    if oldHandler:
        #        self.oldSignals[sigNum] = oldHandler

    def shuttingDown(self, sigNum, frame):
        self.log.debug("got signal %s" % SignalNames.get(sigNum, str(sigNum)))
        # save the cache before exiting
        with file(self.cachePath, "w") as fileOut:
            dump(self.cache, fileOut)
        #self.oldSignals.get(sigNum, lambda:None)(sigNum, frame)


    def addURL(self, url, callback, name=None, cachePeriod=0, maxBytes=None):
        self.log.debug("add request for %s" % url)
        if not name:
            name = url
        else:
            self.log.debug("named %s" % name)
        prevRequest = self.requests.get(name, None)
        if prevRequest is not None:
            self.log.debug("overwriting previous request %s" % prevRequest.url)
            if prevRequest.socket:
                prevRequest.close()
        self.requests[name] = AsyncWebRequest(url, name, callback,
                                              cachePeriod, maxBytes)

    def removeURL(self, name=None):
        self.log.debug("remove request for %s" % name)
        if name in self.requests:
            self.requests[name].close()
            del self.requests[name]
        else:
            self.log.debug("not found")

    def fetch(self):
        self.log.debug("fetch all")
        self.fetchStart = time.time()
        self.fromStats   = [0, 0, 0]
        fetchAll = {}
        for request in self.requests.values():
            retval = request.load(fetchAll, self.cache)
            self.fromStats[retval] += 1
        self.loopStart = time.time()
        self.log.debug("loop")
        asyncore.loop(map=fetchAll)
        self.fetchFinish = time.time()

    def fetchJust(self, names):
        self.log.debug("fetch just")
        self.fetchStart = time.time()
        self.fromStats   = [0, 0, 0]
        self.numFetched  = \
        self.numLoaded   = \
        self.numCached   = 0
        justThese = {}
        for name in names:
            request = self.requests.get(name, None)
            if request is not None:
                retval = request.load(justThese, self.cache)
                self.fromStats[retval] += 1
        self.loopStart = time.time()
        self.log.debug("loop")
        if justThese:
            asyncore.loop(map=justThese)
        self.fetchFinish = time.time()

#TODO I should probably be more worried about thread saftey
AsyncWebFetcher = __AsyncWebFetcher()


# modified from example in http://effbot.org/librarybook/asyncore.htm
class AsyncWebRequest(asyncore.dispatcher_with_send):
    def __init__(self, url, name, callback, cachePeriod=0, maxBytes=None):
        asyncore.dispatcher_with_send.__init__(self)
        self.data        = StringIO()
        self.cachePeriod = cachePeriod
        self.maxBytes    = maxBytes
        self.lastFetched = 0
        self.url         = url
        self.name        = name
        self.callback    = callback
        self.cache       = None
        scheme, host, path, params, query, fragment = urlparse.urlparse(self.url)
        assert scheme == "http", "only supports HTTP requests"
        try:
            host, port = host.split(":", 1)
            port = int(port)
        except (TypeError, ValueError):
            port = 80 # default port
        self.host = host
        self.port = port
        self.log = logging.getLogger(self.name)
        self.log.debug("init %s" % self.url)

        if not path:
            path = "/"
        if params:
            path = path + ";" + params
        if query:
            path = path + "?" + query
        self.request = "GET %s HTTP/1.0\r\nHost: %s\r\n\r\n" % (path, host)

    def load(self, map, cache):
        self._map   = None
        self.cache  = cache
        self.data.truncate(0)
        self.hdrEnd = 0
        self.status = None
        self.header = None

        lastFetched = self.lastFetched
        if not self.lastFetched:
           lastFetched, data = self.cache.get(self.name, (0, ""))

        if lastFetched:
            self.log.debug("cached till %f, now %f" %
                           (lastFetched + self.cachePeriod, time.time()))

        if not lastFetched or time.time() > lastFetched + self.cachePeriod:
            self._map   = map
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            self.log.debug("connecting to %s:%s" % (self.host, self.port))
            self.connect((self.host, self.port))
            retval = AsyncWebFetcher.FromWeb
        elif not self.lastFetched:
            self.log.debug("loaded from cache %d bytes" % len(data))
            self.lastFetched = lastFetched
            self.data.write(data)
            self.callback(data)
            retval = AsyncWebFetcher.FromDisk
        else:
            # the object should still be up to date
            self.log.debug("no load needed")
            retval = AsyncWebFetcher.FromMem
        return retval

    def handle_connect(self):
        self.log.debug("connection succeded, send %s" % self.request[:-2])
        self.send(self.request)

    def handle_read(self):
        payload = self.recv(8192)
        self.log.debug("handle read: %d bytes" % len(payload))
        self.data.write(payload)
        if self.maxBytes is not None and self.data.tell() > self.maxBytes:
            # hopefully we have enough data
            self.handle_close()
        if not self.header:
            # parse header
            self.data.seek(0)
            try:
                self.hdrEnd = self.data.getvalue().index("\r\n\r\n") + 4
            except ValueError:
                return # continue until we have all the headers
            # status line is "HTTP/version status message"
            status = self.data.readline()
            self.status = status.split(" ", 2)
            # followed by a rfc822-style message header
            parser = HeaderParser()
            self.header = parser.parse(self.data)
            self.data.seek(0, os.SEEK_END)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug("version %s " % self.status[0])
                self.log.debug("status  %s %s " % tuple(self.status[1:]))
                for key, value in self.header.items():
                    self.log.debug("header  %s = %s" % (key, value))
            if self.status[1] != "200":
                self.log.error("status = %s %s" % tuple(self.status[1:]))
                self.close()

    def handle_error(self):
        self.log.error("handle error")
        self.close()

    def handle_close(self):
        self.log.debug("handle close")
        self.close()
        if self.status and self.status[1] == "200":
            self.lastFetched = time.time()
            data = self.getData()
            if self.cache is not None and self.cachePeriod > 20:
                self.cache[self.name] = (self.lastFetched, data)
            self.callback(data)
        else:
            status = "%s %s" % tuple(self.status[1:]) if self.status else ""
            self.log.error("closed on error %s" % status)

    def handle_expt(self):
        self.log.debug("ignoring out of band traffic")
        pass

    def getData(self):
        self.data.seek(self.hdrEnd)
        return self.data.read()

    def __str__(self):
        return self.getData()


class AsyncWebData(object):
    def addURL(self, url, pathVar='', cachePeriod=5, maxBytes=None):
        self.fetchURL  = url
        self.fetchName = self.nameFromURL(url, pathVar)
        AsyncWebFetcher.addURL(url, self.parse, self.fetchName, cachePeriod, maxBytes)

    def nameFromURL(self, url, pathVar):
        """
        names are a bit easier for humans to read than long urls
        they are made from the hostname and optional pathVar
        if you prefer to use the full url just pass in pathVar=None
        """
        host = urlparse.urlparse(url).netloc.split(":", 1)[0]
        if pathVar is None:
            name = url
        else:
            if pathVar:
                name = "%s(%s)" % (host, pathVar)
            else:
                name = host
        return name

    def parse(self, data):
        pass

    @staticmethod
    def fetch(*args):
        these = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                these.extend(arg)
            else:
                these.append(arg)
        if these:
            AsyncWebFetcher.fetchJust([this.fetchName for this in these])
        else:
            AsyncWebFetcher.fetch()


