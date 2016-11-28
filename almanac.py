#!/usr/bin/env python3
"""
Helper classes for scheduling actions around time of day etc.
"""
import datetime
import astral
import pickle

class AlmanacCallback:
    "Stores information about a callback for an almanac trigger"
    
    def __init__(self, after, before, callback):
        self.after    = after
        self.before   = before
        self.callback = callback
        self.done     = False

    def reset(self):
        self.done = False
    
    def run(self, a, now):
        if not self.done:
            after  = True if self.after  is True else a[self.after[0]]  + self.after[1]  > now
            before = True if self.before is True else a[self.before[0]] + self.before[1] < now
            if after and before:
                self.callback()
                self.done = True

class SunScheduler:
    "Allows scheduling activities based around the sun"
    
    def __init__(self, location):
        self.callbacks = []
        if hasattr(location, "read"): # Location is a file like object
            self.location = pickle.load(location)
        elif type(location) is astral.Location:
            self.location = location
        else:
            raise ValueError("Location must be either an astral.Location or file like object")
        self.updateDay()
    
    def updateDay(self):
        self.today = datetime.date.today()
        self.sun = self.location.sun(self.today)
        
    def addEvent(self, after, callback, before=True):
        "Register a new callback to trigger on sun time"
        self.callbacks.append(AlmanacCallback(after, before, callback))
    
    def __next__(self):
        now = datetime.datetime.now()
        if now.date() != self.today: # Rollover at midnight
            self.updateDay()
            for cb in self.callbacks:
                cb.reset()
        for cb in self.callbacks:
            cb.run(self.sun, now)
