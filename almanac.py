#!/usr/bin/env python3
"""
Helper classes for scheduling actions around time of day etc.
"""
import datetime
import astral
import pickle
import logging

class AlmanacCallback:
    "Stores information about a callback for an almanac trigger"
    
    def __init__(self, after, before, callback):
        self.after    = after
        self.before   = before
        self.callback = callback
        self.done     = False
        self.logger   = logging.getLogger(repr(self))

    def __repr__(self):
        return "{0.__class__.__name__}(after={0.after!r}, before={0.before!r}, callback={0.callback!r})".format(self)

    def reset(self):
        self.done = False
    
    def run(self, a, now):
        if not self.done:
            after  = True if (self.after  is None) else (now > (a[self.after[0]]  + self.after[1]))
            before = True if (self.before is None) else (now < (a[self.before[0]] + self.before[1]))
            if after and before:
                self.logger.info("Running {0!s}".format(now))
                self.callback()
                self.done = True

class SunScheduler:
    "Allows scheduling activities based around the sun"
    
    def __init__(self, location, today=None):
        self.callbacks = []
        if hasattr(location, "read"): # Location is a file like object
            self.location = pickle.load(location)
        elif type(location) is astral.Location:
            self.location = location
        else:
            raise ValueError("Location must be either an astral.Location or file like object")
        self.logger = logging.getLogger(repr(self))
        self.updateDay(today)
    
    def __repr__(self):
        return "{0.__class__.__name__}({0.location!r})".format(self)
    
    def updateDay(self, today=None):
        if today is None:
            today = datetime.datetime.now(self.location.tz).date()
        self.today = today
        self.logger.info("Update day, today is now {0!s}".format(self.today))
        self.sun = self.location.sun(self.today)
        
    def addEvent(self, callback, after=None, before=None):
        "Register a new callback to trigger on sun time"
        acb = AlmanacCallback(after, before, callback)
        self.logger.debug("Regisered event: {0!r}".format(acb))
        self.callbacks.append(acb)
    
    def checkCallbacks(self, now=None):
        "Checks the callbacks to be run"
        if now is None:
            now = datetime.datetime.now(self.location.tz)
        if now.date() != self.today: # Rollover at midnight
            self.updateDay()
            for cb in self.callbacks:
                cb.reset()
        for cb in self.callbacks:
            cb.run(self.sun, now)
    
    def __next__(self):
        self.checkCallbacks()

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    # Unit tests for this module
    def dummyCallback(*args, **kwargs):
        print("Dummy called with: {!r}, {!r}".format(args, kwargs))
    def badCallback(*args, **kwargs):
        sys.exit("FAIL: Callback should not have been called")
    l = astral.Location()
    s = SunScheduler(l)
    s.addEvent(after  = ('noon', datetime.timedelta(hours=-7)),
               before = ('dawn', datetime.timedelta(0)), # Only turn on light if less than 14 hours of daylight
               callback = dummyCallback)
    s.checkCallbacks()
    noon = s.sun['noon']
    s.addEvent(after =  ('noon', datetime.timedelta(1)),  callback=badCallback)
    s.addEvent(after =  ('noon', datetime.timedelta(-1)), callback=dummyCallback)
    s.addEvent(before = ('noon', datetime.timedelta(1)),  callback=dummyCallback)
    s.addEvent(before = ('noon', datetime.timedelta(-1)), callback=badCallback)
    s.addEvent(before = ('sunrise', datetime.timedelta(0)), after = ('sunset', datetime.timedelta(0)), callback = badCallback)
    s.addEvent(before = ('sunset', datetime.timedelta(0)), after = ('sunrise', datetime.timedelta(0)), callback = dummyCallback)
    s.checkCallbacks(noon)
