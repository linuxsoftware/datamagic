#!/usr/bin/python
# ===========================================================================
# Copyright 2010, D J Moore
# ===========================================================================

import sys
from utils import AsyncWebData
from json import loads

MetserviceSite = "metservice.com"

class RainRadar(AsyncWebData):
    def __init__(self, region):
        self.url       = ""
        self.validFrom = ""
        if not region: region = "Auckland"
        region = region[0].upper() + region[1:]
        self.addURL("http://%s/publicData/rainRadarLocL0%s" %
                    (MetserviceSite, region), 
                    pathVar="rainRadarLocL0%s" % region, cachePeriod=40)

    def parse(self, data):
        try:
            results = loads(data)
        except ValueError:
            results = {}
        radarURL = results.get('url', '')
        if radarURL:
            radarURL = "http://%s%s" % (MetserviceSite, radarURL)
        self.url       = radarURL
        self.validFrom = results.get('validFrom', '')


class WeatherForecast(AsyncWebData):
    def __init__(self, region):
        self.weather = []
        if not region: region = "Auckland"
        region = region[0].upper() + region[1:]
        self.addURL("http://%s/publicData/localForecast%s" %
                    (MetserviceSite, region), 
                    pathVar="localForecast%s" % region, cachePeriod=3600)

    def parse(self, data):
        try:
            results = loads(data)
        except ValueError:
            results = {}
        days = results.get('days', [])
        self.weather = []
        for daysWeather in days[:7]:
            day     = daysWeather.get('dowTLA', '')
            icon    = daysWeather.get('forecastWord', '').lower().replace(' ', '')
            minTemp = daysWeather.get('min', '')
            maxTemp = daysWeather.get('max', '')
            descr   = daysWeather.get('forecast', '')
            text    = "%.1f&deg;C %.1f&deg;C %s" % (minTemp, maxTemp, descr)
            self.weather.append((day, icon, text))

    def __getitem__(self, day):
        return self.weather[day]

    def __len__(self):
        return len(self.weather)

if __name__ == "__main__":
    from pprint import pprint
    forecast = WeatherForecast('Auckland')
    radar = RainRadar("auckland")
    AsyncWebData.fetch(forecast, radar)
    pprint(forecast.weather)
    print radar.url

