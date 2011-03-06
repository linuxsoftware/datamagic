#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
import re
from utils import AsyncWebData
from BeautifulSoup import BeautifulSoup
from datetime import datetime, time, date, timedelta
import logging

TimeRE = re.compile("(\d+):(\d+)")
def strToDateTime(s):
    retval = None
    hhmm = TimeRE.search(s)
    if hhmm:
        hh = int(hhmm.group(1))
        mm = int(hhmm.group(2))
        retval = datetime.combine(date.today(), time(hh, mm))
    return retval

class Bus(object):
    def __init__(self, route, destination, dueIn):
        self.route = route
        self.destination = destination
        self.dueIn = self.timeDue = dueIn
        self.road  = ""

    def setRoad(self):
        try:
            number = int(self.route)
        except ValueError:
            number = 0
        if number // 100 == 1:
            self.road = "GreatNorthRoad"
        elif number // 10 in (21, 22):
            self.road = "NewNorthRoad"
        else:
            self.road = ""

    def setTimeDue(self, asAtTime):
        timeDue = strToDateTime(self.dueIn)
        if timeDue:
            self.timeDue = self.dueIn
            delta = timeDue - asAtTime
            if delta < timedelta(0):
                delta += timedelta(days=1)
            minutes = delta.days * 1440 + (delta.seconds + 30) // 60
            hours = minutes // 60
            minutes %= 60
            if hours:
                self.dueIn = "%dhr %dmin" % (hours, minutes)
            else:
                self.dueIn = "%dmin" % minutes
        elif self.dueIn.endswith("min"):
            delta = timedelta(minutes=int(self.dueIn[:-3]))
            timeDue = asAtTime + delta
            self.timeDue = timeDue.strftime("%H:%M")
        else:
            self.timeDue = self.dueIn

class BusStop(AsyncWebData):
    def __init__(self, stopNumber):
        self.address  = ""
        self.asAt     = ""
        self.buses    = []
        self.accuracy = "error"
        maxResults    = 10
        if not stopNumber: stopNumber = "7074"
        self.stopNumber = stopNumber
        self.log = logging.getLogger("BusStop "+stopNumber)
        self.log.debug("init")
        self.addURL("http://www.maxx.co.nz/_vpid.cfm?maxresults=%d&"
                    "stopNumber=%s" % (maxResults, stopNumber),
                    pathVar=stopNumber)
#        self.addURL("http://www.maxx.co.nz/_vpid.cfm?maxresults=%d&"
#                    "stopNumber=%s&fmsEnabled=false&saveStopNumber=true&"
#                    "standalone=false&showScheduledOnly=false" %
#                    (maxResults, stopNumber), pathVar=stopNumber)

    def parse(self, data):
        print data
        self.log.debug("parse %d bytes" % len(data))
        self.address  = ""
        self.asAt     = ""
        self.buses    = []
        self.accuracy = "error"
        soup = BeautifulSoup(data)
        stopName = soup.find("span", "stopName")
        if stopName and stopName.contents:
            self.address = stopName.contents[0]
        currTime = soup.find("span", "currTime")
        if currTime and currTime.contents:
            self.asAt = currTime.contents[0]
            asAtTime = strToDateTime(self.asAt) or datetime.now()

        results = soup.find("table", "results")
        if results:
            self.log.debug("found results table")
            rows = results.findAll("tr")

            self.accuracy = "scheduled"
            if rows and rows[0].find(text="REAL"):
                self.accuracy = "real-time"

            for row in rows[2:]:
                data = [td.contents[0].strip() for td in row.findAll("td")]
                if len(data) == 3:
                    self.log.debug("add bus %s" % data)
                    bus = Bus(*data)
                    bus.setRoad()
                    if bus.road:
                        # only add buses on my routes
                        bus.setTimeDue(asAtTime)
                        self.buses.append(bus)
        else:
            self.log.debug("no results table")


if __name__ == "__main__":
    from pprint import pprint
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)
    busstop = BusStop('8143')
    AsyncWebData.fetch(busstop)
    print busstop.accuracy
    for bus in busstop.buses:
        print bus.road, bus.route, bus.destination, bus.timeDue, bus.dueIn
