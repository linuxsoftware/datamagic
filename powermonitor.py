#!/usr/bin/python2.6
#==============================================================================
# powermonitor.py
# Generates a power usage chart
# Copyright 2011, D J Moore (info@linuxsoftware.co.nz)
#==============================================================================

from urllib import urlencode
from json import loads
from datetime import date, datetime, timedelta
import calendar
from itertools import ifilter
import oauth2 as oauth
from CairoPlot import HORZ, VERT, other_direction, BarPlot
from itertools import chain
import cairo
import secret

#==============================================================================
class PowerMeter(object):
    PowerShop  = "https://secure.powershop.co.nz"

    def __init__(self, startDate):
        self.usage = []
        self.icpNumber = ""
        consumer = oauth.Consumer(secret.ApiKey, secret.ApiSecret)
        accessToken = oauth.Token(secret.UserToken, secret.UserSecret)
        self.client = oauth.Client(consumer, accessToken)
        self.__getCustomer()
        self.__getMeterReadings(startDate)

    def __getCustomer(self):
        details = self.__getData("customer")
        property0 = details["properties"][0]
        self.icpNumber = property0["icp_number"]
        dailyConsumption = float(property0["daily_consumption"])
        self.estimatedUsage = EstimatedUsage(dailyConsumption)

    def __getMeterReadings(self, startDate):
        params = {"icp_number" : self.icpNumber,
                  "start_date" : startDate.strftime("%Y-%m-%d"),
                  "end_date"   : date.today().strftime("%Y-%m-%d")}
        details = self.__getData("meter_readings", params)
        detailIter = ifilter(lambda d:d["reading_type"] == "actual",
                             reversed(details))
        for prevDetail in detailIter:
            break
        for detail in detailIter:
            dailyUsage = DailyUsage(detail, prevDetail)
            if dailyUsage.numDays > 0:
                self.usage.append(dailyUsage)
                prevDetail = detail

    def __getData(self, api, params=None):
        url = "%s/external_api/v1/%s.js" % (self.PowerShop, api)
        if params is not None:
            url += "?" + urlencode(params)

        response, content = self.client.request(url)
        try:
            details = loads(content).get('result', {})
        except ValueError:
            details = {}
        return details

#==============================================================================
class EstimatedUsage(object):
    isEstimated = True
    def __init__(self, usage):
        self.usage = usage

    def __repr__(self):
        return "                   %0.1f kWh" % (self.usage)

#==============================================================================
class DailyUsage(object):
    isEstimated = False
    @staticmethod
    def __getDate(ymdhms):
        """convert from a datetime string and round to nearest whole date"""
        dt = datetime.strptime(ymdhms, "%Y-%m-%d %H:%M:%S")
        return (dt - timedelta(hours=11)).date()

    def __init__(self, detail, prevDetail):
        prevDate  = DailyUsage.__getDate(prevDetail["read_at"])
        prevValue = float(prevDetail["reading_value"])
        self.startDate = prevDate + timedelta(days=1)
        self.endDate   = DailyUsage.__getDate(detail["read_at"])
        self.numDays   = (self.endDate - prevDate).days
        self.value     = float(detail["reading_value"])
        if self.numDays > 0:
            self.usage   = (self.value - prevValue) / self.numDays
        else:
            self.usage   = None

    def __repr__(self):
        return "%s %s %0.1f kWh" % (self.startDate.strftime("%F"),
                                    self.value,
                                    self.usage)

#==============================================================================
class WeeksUsage(object):
    def __init__(self, day = None):
        if not day:
            day = date.today()
        self.startDate = day - timedelta(days=day.weekday())
        self.endDate   = self.startDate + timedelta(days=6)
        self.usage     = [EstimatedUsage(0),]*7

    def setUsage(self, power):
        setDay = self.startDate
        for usage in power.usage:
            #print "usage %s - %s" % (usage.startDate, usage.endDate)
            while usage.startDate <= setDay <= usage.endDate:
                self.usage[setDay.weekday()] = usage
                setDay += timedelta(days=1)
                if setDay > self.endDate:
                    return
        while setDay <= date.today() and setDay <= self.endDate:
            self.usage[setDay.weekday()] = power.estimatedUsage
            setDay += timedelta(days=1)

    def __getitem__(self, n):
        if n < -6 or n > 6:
            raise IndexError("Week days must be 0..6 ")
        if n < 0:
            n += 6
        day = self.startDate + timedelta(days=n)
        return (day, self.usage[n])

    def __len__(self):
        return 7

    def __repr__(self):
        return "%s - %s" % (self.startDate.strftime("%F"),
                            self.endDate.strftime("%F"))

    def dump(self):
        print self
        for dow, usage in enumerate(self.usage):
            print calendar.day_abbr[dow], usage

#==============================================================================
class UsageBarChart(BarPlot):
    #OutputDir = "/home8/dazedcon/www/datamagic/"
    #OutputDir = "www/html/datamagic/"
    OutputDir = ""
    def __init__(self, week1, week2):
        self.week1 = week1
        self.week2 = week2
        maximum = 0
        for day, daysUsage in chain(week1, week2):
            maximum = max(maximum, daysUsage.usage)
        maximum += maximum % 2
        self.vLabels = [str(x) if x%10==0 or x>=int(maximum) else ""
                        for x in range(0, int(maximum)+2, 2)]
        #width  = 250; height = 240
        #background = cairo.LinearGradient(width / 1.1, 0, width / 1.1, height)
        #background.add_color_stop_rgb(0.01,0.95,0.95,1.0)
        #background.add_color_stop_rgb(0.9,0.8,0.8,0.88)
        BarPlot.__init__(self,
                         surface  = self.OutputDir+"powermonitor.png", 
                         width    = 250,
                         height   = 240,
                         border   = 5,
                         grid     = True,
                         v_bounds = (0, maximum),
                         background = None)

    def load_series(self, data, h_labels, v_labels, series_colors):
        if data is not None:
            BarPlot.load_series(self, data, h_labels, v_labels, series_colors)

    def render(self):
        self.render_background()
        #self.render_bounding_box()
        self.height /= 2
        self.setWeek(self.week1)
        self.calc_horz_extents()
        self.calc_vert_extents()
        if self.grid:
            self.render_grid()
        self.render_labels()
        self.renderDates(self.week1)
        self.render_plot()

        self.context.translate(0, 110)
        if self.grid:
            self.render_grid()
        self.setWeek(self.week2)
        self.render_labels()
        self.renderDates(self.week2)
        self.render_plot()

    def setWeek(self, week):
        bars    = []
        colours = []
        labels  = calendar.day_abbr
        for day, daysUsage in week:
            bars.append(daysUsage.usage)
            if daysUsage.isEstimated:
                colours.append((0.55, 0.5, 0.5))
            elif day.weekday() < 5:
                colours.append((0.77, 0.31, 0.54))
            else:
                colours.append((0.75,0.08,0.08))
        self.labels[HORZ] = labels
        self.labels[VERT] = self.vLabels
        self.load_series(bars, labels, self.vLabels, colours)

    def calc_extents(self, direction):
        self.max_value[direction] = 0
        if self.labels[direction]:
            # This code crashes :(, so just pick the first
            #widest_word = max(self.labels[direction], key = lambda item: self.context.text_extents(item)[2])
            widest_word = self.labels[direction][0]
            self.max_value[direction] = self.context.text_extents(widest_word)[3 - direction]
            self.borders[other_direction(direction)] = (2-direction)*self.max_value[direction] + self.border + direction*(5)
        else:
            self.borders[other_direction(direction)] = self.border

    def render_vert_labels(self):
        # the original version of this function also crashes :(
        y = self.borders[VERT]
        step = (self.height - 2*self.borders[VERT])/(len(self.labels[VERT]) - 1)

        for item in reversed(self.labels[VERT]):
            self.context.set_source_rgb(*self.label_color)
            if item:
                width, height = self.context.text_extents(item)[2:4]
                self.context.move_to(self.borders[HORZ] - width - 5, y + height/2)
                self.context.show_text(item)
            y += step

    def renderDates(self, week):
        day1  = str(week[0][0].day)
        month = week[3][0].strftime("%B")
        day2  = str(week[6][0].day)
        cr = self.context
        cr.set_source_rgb(*self.label_color)
        step = (self.width - self.borders[HORZ] - self.border)/7
        x = self.borders[HORZ] + step*0.5 - cr.text_extents(day1)[2]/2
        cr.move_to(x, self.height - self.borders[VERT] + 20)
        cr.show_text(day1)
        x = self.borders[HORZ] + step*3.5 - cr.text_extents(month)[2]/2
        cr.move_to(x, self.height - self.borders[VERT] + 20)
        cr.show_text(month)
        x = self.borders[HORZ] + step*6.5 - cr.text_extents(day2)[2]/2
        cr.move_to(x, self.height - self.borders[VERT] + 20)
        cr.show_text(day2)

#==============================================================================
class PowerMonitor(object):
    """Gives the power usage for this week and the previous week"""

    def __init__(self):
        self.power = PowerMeter(date.today() - timedelta(days=30))
        self.thisWeek = WeeksUsage(date.today())
        self.thisWeek.setUsage(self.power)
        self.lastWeek = WeeksUsage(self.thisWeek.startDate - timedelta(weeks=1))
        self.lastWeek.setUsage(self.power)

    def save(self):
        chart = UsageBarChart(self.lastWeek, self.thisWeek)
        chart.render()
        chart.commit()

    def dump(self):
        self.lastWeek.dump()
        self.thisWeek.dump()

#==============================================================================
def main():
    pwrmon = PowerMonitor()
    #pwrmon.dump()
    pwrmon.save()

if __name__ == "__main__":
    main()
