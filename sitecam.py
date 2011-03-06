#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
from utils import AsyncWebData
from BeautifulSoup import BeautifulSoup

Sitecam = "sitecam.co.nz"

class AucklandWebcam(AsyncWebData):
    """Gets the latest Auckand webcam picture from sitecam.co.nz"""
    def __init__(self):
        self.addURL("http://%s/auckland_webcam/image.php?id=1" % Sitecam,
                    cachePeriod=3600)
        self.url = ""

    def parse(self, data):
        self.url = ""
        soup = BeautifulSoup(data)
        img = soup.img
        if img:
            path = img.get("src", "")
            if path:
                self.url = "http://%s/auckland_webcam/%s" % (Sitecam, path)



if __name__ == "__main__":
    aklcam = AucklandWebcam()
    AsyncWebData.fetch(aklcam)
    print aklcam.url

