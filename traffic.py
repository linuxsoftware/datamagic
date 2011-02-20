#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
import re
from utils import AsyncWebData
from xml.etree.cElementTree import fromstring
import logging


class MotorwayTraffic(AsyncWebData):
    def __init__(self, motorwayName):
        self.motorwayName = motorwayName
        self.updated  = ""
        self.segments = []
        #self.addURL("http://www.trafficnz.info/xml/traffic", cachePeriod=45)
        self.addURL("https://infoconnect1.highwayinfo.govt.nz/ic/jbi/TrafficConditions/REST/FeedService/",
                    cachePeriod=45,
                    extraHeaders={"username": self.username,
                                  "password": self.password})

    def parse(self, data):
        tns = "https://infoconnect.highwayinfo.govt.nz/schemas/traffic"
        tree = fromstring(data)
        root = tree.find("{%s}trafficConditions" % tns)
        if not root: return
        lastUpdated = root.find("{%s}lastUpdated" % tns)
        if lastUpdated:
            self.updated = lastUpdated.text
        for motorway in root.getiterator("{%s}motorway" % tns):
            name = motorway.findtext("{%s}name" % tns, "")
            if name == self.motorwayName:
                break
        else:
            return
        locations = motorway.findall("{%s}location" % tns)
        numSegments = len(locations) // 2
        self.segments = [["", "", ""] for i in range(numSegments)]
        for location in locations:
            order = int(location.findtext("{%s}order" % tns, "0"))
            if order <= 0 or order > numSegments:
                continue
            inOut = location.findtext("{%s}inOut" % tns, "")
            if inOut == "Out":
                segment = self.segments[numSegments - order]
                segment[0] = location.findtext('{%s}congestion' % tns, '')
            elif inOut == "In":
                segment = self.segments[order - 1]
                segment[1] = location.findtext('{%s}name' % tns, '')
                segment[2] = location.findtext('{%s}congestion' % tns, '')

if __name__ == "__main__":
    from pprint import pprint
    from password import MotorwayTraffic
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)
    traffic = MotorwayTraffic('North-Western Motorway')
    AsyncWebData.fetch(traffic)
    pprint(traffic.segments)

