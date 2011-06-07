#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
import re
from utils import AsyncWebData
from BeautifulSoup import BeautifulSoup

APoDSite = "apod.nasa.gov"

class PictureOfTheDay(AsyncWebData):
    """Gets the latest Astronomical picture of the day"""
    def __init__(self):
        self.addURL("http://%s/apod/astropix.html" % APoDSite,
                    cachePeriod=2*3600)
        self.url         = ""
        self.link        = ""
        self.title       = ""
        self.explanation = ""

    def parse(self, data):
        self.url         = ""
        self.link        = ""
        self.title       = ""
        self.explanation = ""
        soup = BeautifulSoup(data)
        img = soup.img
        if img:
            path = img.get("src", "")
            if path:
                self.url = "http://%s/apod/%s" % (APoDSite, path)
            imgp = img.parent
            if imgp and imgp.name == "a":
                path = imgp.get("href", "")
                if path:
                    self.link = "http://%s/apod/%s" % (APoDSite, path)
        b0 = soup.b
        if b0:
            self.title = b0.string.strip()
        #xpl = soup.find(text=re.compile("Explanation"))
        #if xpl:
        #    xplpp = xpl.parent.parent
        #    explanation = " ".join(x.string for x in xplpp)
        #    explanation = re.sub("\\s+", " ", explanation)
        #    self.explanation = explanation.strip()



if __name__ == "__main__":
    apod = PictureOfTheDay()
    AsyncWebData.fetch(apod)
    print apod.url
    print apod.title
    print apod.link
    print apod.explanation

