#
# BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2005 Michael "ThorN" Thornton
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# CHANGELOG
# 11/30/2005 - 1.3.0 - ThorN
#    * Added PluginCronTab
# 10/24/2010 - 1.4.0 - Courgette
#    * make the cron able to run command every second (was limited to every 15 seconds before)
#    * more cron syntax accepted. '5-12/2, 30, 40-42' is now a valid syntax to specify [5,7,9,11,30,40,41,42]
#    * add tests
# 11/16/2010 - 1.4.1 - Courgette
#    * removing a non existing crontab does not raise a KeyError anymore
#
__author__  = 'ThorN, Courgette'
__version__ = '1.4.1a'

import re, thread, threading, time, traceback, sys

class ReMatcher:
    _re = None
    def match(self, regexp, value):
        self._re = re.match(regexp, value)
        return self._re

    def _get_match(self):
        return self._re

    results = property(_get_match)

class CronTab(object):
    _second = None
    _minute = None
    _hour = None
    _day = None
    _month = None
    _dow = None
    command = None
    maxRuns = 0
    numRuns = 0

    def __init__(self, command, second=0, minute='*', hour='*', day='*', month='*', dow='*'):
        self.second = second
        self.minute = minute
        self.hour = hour
        self.day = day
        self.month = month
        self.dow = dow
        self.command = command

    def run(self):
        self.command()

    def _set_second(self, value):
        self._second = self._getRate(value, 60)
    def _get_second(self):
        return self._second
    second = property(_get_second, _set_second)

    def _set_minute(self, value):
        self._minute = self._getRate(value, 60)
    def _get_minute(self):
        return self._minute
    minute = property(_get_minute, _set_minute)

    def _set_hour(self, value):
        self._hour = self._getRate(value, 24)
    def _get_hour(self):
        return self._hour
    hour = property(_get_hour, _set_hour)

    def _set_day(self, value):
        self._day = self._getRate(value, 31)
    def _get_day(self):
        return self._day
    day = property(_get_day, _set_day)

    def _set_month(self, value):
        self._month = self._getRate(value, 12)
    def _get_month(self):
        return self._month
    month = property(_get_month, _set_month)

    def _set_dow(self, value):
        self._dow = self._getRate(value, 7)
    def _get_dow(self):
        return self._dow
    dow = property(_get_dow, _set_dow)

    def _getRate(self, rate, max=None):
        if type(rate) == str:
            if ',' in rate:
                # 10,20,30 = [10, 20, 30]
                # 5,6,7,20,30 = [5-7, 20, 30]
                # 5,7,9,11,30,40,41,42 = [5-12/2, 30, 40-42]
                myset = {}
                for fragment in rate.split(','):
                    result = self._getRateFromFragment(fragment.strip(), max) 
                    if type(result) == int:
                        myset[result] = None
                    else:
                        for val in result:
                            myset[int(val)] = None
                mylist = myset.keys()
                mylist.sort()
                return mylist
            else:
                return self._getRateFromFragment(rate, max)
        elif type(rate) == int:
            if rate < 0 or rate >= max:
                raise ValueError('accepted range is 0-%s' % (max-1))
            return rate
        elif type(rate) == float:
            if int(rate) < 0 or int(rate) >= max:
                raise ValueError('accepted range is 0-%s' % (max-1))
            return int(rate)

        raise TypeError('"%s" is not a known cron rate type' % rate)
    
    def _getRateFromFragment(self, rate, max):
        r = ReMatcher()
        if rate == '*':
            return -1
        elif r.match(r'^([0-9]+)$', rate):
            if int(rate) >= max:
                raise ValueError('%s cannot be over %s' % (rate, max-1))
            return int(rate)
        elif r.match(r'^\*/([0-9]+)$', rate):
            # */10 = [0, 10, 20, 30, 40, 50]
            step = int(r.results.group(1))
            if step > max:
                raise ValueError('%s cannot be over every %s' % (rate, max-1))
            return range(0, max, step)
        elif r.match(r'^(?P<lmin>[0-9]+)-(?P<lmax>[0-9]+)(/(?P<step>[0-9]+))?$', rate):
            # 10-20 = [0, 10, 20, 30, 40, 50]
            lmin = int(r.results.group('lmin'))
            lmax = int(r.results.group('lmax'))
            step = r.results.group('step')
            if step is None:
                step = 1
            else:
                step = int(step)
            if step > max:
                raise ValueError('%s is out of accepted range 0-%s' % (step, max))
            if lmin < 0 or lmax > max:
                raise ValueError('%s is out of accepted range 0-%s' % (rate, max-1))
            if lmin > lmax:
                raise ValueError('%s cannot be greater than %s in %s' % (lmin, lmax, rate))
            return range(lmin, lmax + 1, step)
        raise TypeError('"%s" is not a known cron rate type' % rate)
    
    def _match(self, unit, value):
        if type(unit) == int:
            if unit == -1 or unit == value:
                return True
        elif value in unit:
            return True
        return False

    def match(self, timetuple):
        # See if the cron entry matches the current time
        # second
        timeMatch = self._match(self.second, timetuple[5] - (timetuple[5] % 1))
        # minute
        timeMatch = timeMatch and self._match(self.minute, timetuple[4])
        # hour
        timeMatch = timeMatch and self._match(self.hour, timetuple[3])
        # day
        timeMatch = timeMatch and self._match(self.day, timetuple[2])
        # month
        timeMatch = timeMatch and self._match(self.month, timetuple[1])
        # weekday (in crontab 0 is Mon)
        timeMatch = timeMatch and self._match(self.dow, timetuple[6])
        return timeMatch

class OneTimeCronTab(CronTab):
    def __init__(self, command, second=0, minute='*', hour='*', day='*', month='*', dow='*'):
        CronTab.__init__(self, command, second, minute, hour, day, month, dow)
        self.maxRuns = 1

class PluginCronTab(CronTab):
    plugin = None

    def __init__(self, plugin, command, second=0, minute='*', hour='*', day='*', month='*', dow='*'):
        CronTab.__init__(self, command, second, minute, hour, day, month, dow)
        self.plugin = plugin

    def match(self, timetuple):
        if self.plugin.isEnabled():
            return CronTab.match(self, timetuple)
        else:
            return False

    def run(self):
        if self.plugin.isEnabled():
            CronTab.run(self)

class Cron(object):
    def __init__(self, console):
        self._tabs = {}
        self.console = console

        # thread will stop if this event gets set
        self._stopEvent = threading.Event()

    def create(self, command, second='*', minute='*', hour='*', day='*', month='*', dow='*'):
        t = CronTab(command, second, minute, hour, day, month, dow)
        return self.add(t)

    def add(self, tab):
        self._tabs[id(tab)] = tab
        self.console.verbose('Added crontab %s (%s) - %ss %sm %sh %sd %sM %sDOW' % (tab.command, id(tab), tab.second, tab.minute, tab.hour, tab.day, tab.month, tab.dow))
        return id(tab)

    def __add__(self, tab):
        self.add(tab)

    def __sub__(self, tab):
        self.cancel(id(tab))

    def cancel(self, id):
        try:
            del self._tabs[id]
            self.console.verbose('Removed crontab %s' % id)
        except KeyError:
            self.console.verbose('crontab %s not found' % id)

    def start(self):
        #self.run()
        thread.start_new_thread(self.run, ())

    def time(self):
        return time.time()

    def stop(self):
        """Stop the cron scheduler"""
        self._stopEvent.set()

    def run(self):
        self.console.info("cron scheduler started")
        nextTime = self.getNextTime()
        while not self._stopEvent.isSet():
            now = self.time()

            if now < nextTime:
                self._stopEvent.wait(nextTime - now + .1)

            # Check if the time has changed by more than two minutes. This
            # case arises when the system clock is changed. We must reset the timer.
            if abs(self.time() - nextTime) > 120:
                nextTime = self.getNextTime()

            t = time.localtime(nextTime)
            for k,c in self._tabs.items():
                if c.match(t):
                    if c.maxRuns > 0 and c.numRuns + 1 > c.maxRuns:
                        # reached max executions, remove tab
                        del self._tabs[k]
                    else:
                        c.numRuns = c.numRuns + 1

                        try:
                            c.run()
                        except Exception, msg:
                            self.console.error('Error executing crontab %s: %s\n%s', c.command, msg, traceback.extract_tb(sys.exc_info()[2]))

            nextTime = nextTime + 1
        self.console.info("cron scheduler ended")


    def getNextTime(self):
        # store the time first, we don't want it to change on us
        t = time.time()

        # current time, minus it's 1 second remainder, plus 1 seconds
        # will round to the next nearest 1 seconds
        return (t - t % 1) + 1


