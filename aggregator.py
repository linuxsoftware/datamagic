#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
from utils import AsyncWebData
import feedparser


class Feed(AsyncWebData):
    """just an AsyncWebData wrapper for feedparser"""
    def __init__(self, url):
        self.addURL(url, cachePeriod=3*3600, maxBytes=16384)
        self.info    = {}
        self.title   = ""
        self.entries = {}

    def parse(self, data):
        self.info    = {}
        self.title   = ""
        self.entries = {}
        d = feedparser.parse(data)
        if d.entries:
            self.info    = d.feed
            self.title   = d.feed.title
            self.entries = d.entries


if __name__ == "__main__":
    sandfly = Feed("http://feeds.feedburner.com/LifeOfAndrew")
    AsyncWebData.fetch(sandfly)
    print sandfly.entries[0].summary

