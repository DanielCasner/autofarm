#!/usr/bin/env python3
"""
Lighting helper functions
Based on pgpio
"""

class Light(object):
    "One or more channel driver"
    
    def __init__(self, pi, gpios, phases=None):
        self.pi = pi
        self.gpio  = tuple(gpios)
        if phases is None:
            num = len(self.gpios)
            self.phase = tuple((float(i)/num for i in range(num)))
        else:
            self.phase = phases
        
    def set(self, *vals):
        for args in zip(self.gpio, vals, self.phase):
            self.pi.set_PWM_dutycycle(*args)
