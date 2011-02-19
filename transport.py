#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
import re
from utils import AsyncWebData
from BeautifulSoup import BeautifulSoup
from datetime import datetime, time, date, timedelta
from xml.etree.cElementTree import fromstring
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
        self.addURL("http://www.maxx.co.nz/_vpid.cfm?maxresults=%d&mode=bus&"
                    "query=vpid&stopNumber=%s&stopText=%s" %
                    (maxResults, stopNumber, stopNumber), pathVar=stopNumber)

    def parse(self, data):
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
            if rows and rows[0].td.contents:
                if "REAL time" in rows[0].td.contents[0]:
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

class MotorwayTraffic(AsyncWebData):
    def __init__(self, motorwayName):
        self.motorwayName = motorwayName
        self.updated  = ""
        self.segments = []
        self.addURL("http://www.trafficnz.info/xml/traffic", cachePeriod=45)

    def parse(self, data):
        tree = fromstring(data)
        self.updated = tree.get('lastUpdated', '')
        for motorway in tree.getiterator('motorway'):
            if motorway.get('name') == self.motorwayName:
                break
        else:
            return
        locations = motorway.findall("location")
        numSegments = len(locations) // 2
        self.segments = [["", "", ""] for i in range(numSegments)]
        for location in locations:
            order = int(location.get('order', 0))
            if order <= 0 or order > numSegments:
                continue
            inOut = location.get('inOut', '')
            if inOut == "outbound":
                segment = self.segments[numSegments - order]
                segment[0] = location.get('congestion', '')
            elif inOut == "inbound":
                segment = self.segments[order - 1]
                segment[1] = location.get('name', '')
                segment[2] = location.get('congestion', '')


if __name__ == "__main__":
    from pprint import pprint
    traffic = MotorwayTraffic('North-Western Motorway')
    AsyncWebData.fetch(traffic)
    pprint(traffic.segments)

