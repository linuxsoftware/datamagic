#!/usr/bin/python
# ===========================================================================
# Copyright 2010-2011, D J Moore
# ===========================================================================

"""
This utility is intended to be run from a cron job every few hours
it will go through the list of Blogs and grab the latest posts.
The widget will know when a post is read because the links go firstly
to the server then are redirected to the destination URL.
"""

Blogs = ["http://www.asciimation.co.nz/bb/feed/atom",
         "http://alweb.homeip.net/blog/?feed=atom",
         "http://www.ctrlaltboutique.com/canada/?feed=rss2",
         "http://blog.core-ed.net/derek/feed",
         "http://feeds.feedburner.com/LifeOfAndrew",
         "http://pedagogyofthecompressed.blogspot.com/feeds/posts/default",
         "http://lorenz.co.nz/feed/atom",
         "http://blog.loaz.com/timwang/index.php?tempskin=_atom"]

import sys
from utils import AsyncWebData
import feedparser

class BlogReader(object):
    """Presents the blogs"""
    pass

class Aggregator(object):
    """Looks for new blog posts"""
    def __init__(self, blogs):
        #self.feeds = zip(blogs, 
        pass

class Feed(object):
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
    print sandfly.entries[0].summary

