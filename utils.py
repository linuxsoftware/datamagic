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
import ssl
import urlparse
from cStringIO import StringIO
from email.parser import HeaderParser
import logging
from cPickle import dump, load
import signal
SignalNames = dict([(y,x) for x,y in signal.__dict__.items() if x.startswith("SIG")])
del signal

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


def compact_traceback():
    t, v, tb = sys.exc_info()
    tbinfo = []
    if not tb: # Must have a traceback
        raise AssertionError("traceback does not exist")
    while tb:
        tbinfo.append((
            tb.tb_frame.f_code.co_filename,
            tb.tb_frame.f_code.co_name,
            str(tb.tb_lineno)
            ))
        tb = tb.tb_next

    # just to be safe
    del tb

    file, function, line = tbinfo[-1]
    info = ' '.join(['[%s|%s|%s]' % x for x in tbinfo])
    return (file, function, line), t, v, info


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

    def shuttingDown(self, sigNum, frame):
        self.log.debug("got signal %s" % SignalNames.get(sigNum, str(sigNum)))
        # save the cache before exiting
        with file(self.cachePath, "w") as fileOut:
            dump(self.cache, fileOut)

    def addURL(self, url, callback, name=None, cachePeriod=0,
               maxBytes=None, extraHeaders=None):
        """
        adds a request to read a web page
        url:          the url of another page to be read
        callback:     function to be called when data is available
        name:         alternative to the url (for caching and debugging)
        cachePeriod:  the data is cached for cachePeriod seconds
        maxBytes:     complete read even if unfinished once maxBytes is reached
        extraHeaders: just for the bizarre authentication used by highwayinfo
        """
        self.log.debug("add request for %s" % url)
        if not name:
            name = url
        else:
            self.log.debug("named %s" % name)
        prevRequest = self.requests.get(name, None)
        if prevRequest is not None:
            self.log.debug("overwriting previous request %s" % prevRequest.url)
            #if prevRequest.socket:
            #    prevRequest.close()
        if url.startswith("https:"):
            self.requests[name] = AsyncHttpsRequest(url, name, callback, cachePeriod,
                                                   maxBytes, extraHeaders)
        else:
            self.requests[name] = AsyncHttpRequest(url, name, callback, cachePeriod,
                                                  maxBytes, extraHeaders)

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
class AsyncHttpRequest(asyncore.dispatcher_with_send):
    def __init__(self, url, name, callback, cachePeriod=0, maxBytes=None, extraHeaders=None):
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
        self.scheme      = scheme
        try:
            host, port = host.split(":", 1)
            port = int(port)
        except (TypeError, ValueError):
            if scheme == "https":
                port = 443
            else:
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
        self.request = "GET %s HTTP/1.0\r\nHost: %s\r\n" % (path, host)
        if extraHeaders:
            for extraHeader in extraHeaders.items():
                self.request += "%s: %s\r\n" % extraHeader
        self.request += "\r\n"

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
        requestLine1 = self.request.split("\r\n", 2)[0]
        self.log.debug("connection succeded, send %s..." % requestLine1)
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
        nil, t, v, tbinfo = compact_traceback()

        # sometimes a user repr method will crash.
        try:
            self_repr = repr(self)
        except:
            self_repr = '<__repr__(self) failed for object at %0x>' % id(self)

        self.log_error(
            'uncaptured python exception, closing channel %s (%s:%s %s)' % (
                self_repr,
                t,
                v,
                tbinfo
                ),
            'error'
            )
        self.handle_close()

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
            status = ("%s %s" % tuple(self.status[1:])) if self.status else ""
            self.log.error("closed on error %s" % status)

    def handle_expt(self):
        self.log.debug("ignoring out of band traffic")
        pass

    def getData(self):
        self.data.seek(self.hdrEnd)
        return self.data.read()

    def __str__(self):
        return self.getData()


# TODO check out
# http://bugs.python.org/file20752/asyncore_ssl_v1.patch
class AsyncHttpsRequest(AsyncHttpRequest):
    HandshakeDone, HandshakeRead, HandshakeWrite = range(3)
    
    def __init__(self, url, name, callback, cachePeriod=0, maxBytes=None, extraHeaders=None):
        AsyncHttpRequest.__init__(self, url, name, callback, cachePeriod, maxBytes, extraHeaders)
        self.doHandshake = AsyncHttpsRequest.HandshakeDone

    def handle_connect(self):
        self.log.debug("connect succeded")
        self.socket = ssl.wrap_socket(self.socket, do_handshake_on_connect=False)
        self.do_handshake()

    def do_handshake(self):
        try: 
            self.socket.do_handshake() 
        except ssl.SSLError, err: 
            if err.args[0] == ssl.SSL_ERROR_WANT_READ: 
                self.doHandshake = AsyncHttpsRequest.HandshakeRead
                self.log.debug("HandshakeRead pending")
            elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE: 
                self.doHandshake = AsyncHttpsRequest.HandshakeWrite
                self.log.debug("HandshakeWrite pending")
            elif err.args[0] == ssl.SSL_ERROR_EOF:
                return self.handle_close()
            else: 
                raise 
        else: 
            self.doHandshake = AsyncHttpsRequest.HandshakeDone
            self.log.debug("SSL handshake succeded, send %s" % self.request[:-2])
            self.send(self.request)

    def handle_read_event(self):
        if self.doHandshake == AsyncHttpsRequest.HandshakeRead:
            self.do_handshake()
        if self.doHandshake == AsyncHttpsRequest.HandshakeDone:
            AsyncHttpRequest.handle_read_event(self)

    def recv(self, buffer_size):
        try: 
            data = AsyncHttpRequest.recv(self, buffer_size)
            return data
        except ssl.SSLError, err: 
            if err.args[0] == ssl.SSL_ERROR_WANT_READ: 
                self.log.debug("SSL read pending")
                return ""
            else: 
                raise 
        except:
            raise 

    def handle_write_event(self):
        if self.doHandshake == AsyncHttpsRequest.HandshakeWrite:
            self.do_handshake()
        if self.doHandshake == AsyncHttpsRequest.HandshakeDone:
            AsyncHttpRequest.handle_write_event(self)

    def send(self, data):
        try:
            result = AsyncHttpRequest.send(self, data)
            return result
        except ssl.SSLError, err: 
            if err.args[0] == ssl.SSL_ERROR_WANT_WRITE: 
                self.log.debug("SSL write pending")
                return 0
            else: 
                raise 
        except:
            raise 


class AsyncWebData(object):
    def addURL(self, url, pathVar='', cachePeriod=5,
               maxBytes=None, extraHeaders=None):
        self.fetchURL  = url
        self.fetchName = self.nameFromURL(url, pathVar)
        AsyncWebFetcher.addURL(url, self.parse, self.fetchName, cachePeriod, 
                               maxBytes, extraHeaders)

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


