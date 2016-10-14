#!/usr/bin/env python3
"""
Lighting helper functions
Based on pgpio
"""

class Light(object):
    "One or more channel driver"
    
    def __init__(self, pi, gpios, scales=None, phases=None):
        self.pi = pi
        self.gpio   = tuple(gpios)
        if scales is None:
            self.scales = tuple([1] * len(gpios))
        else:
            self.scales = tuple(scales)
        if phases is None:
            num = len(self.gpios)
            self.phase = tuple((float(i)/num for i in range(num)))
        else:
            self.phase = tuple(phases)
        self.set([0] * len(gpios))
        
    def __del__(self):
        for pin in self.gpio:
            self.pi.set_PWM_dutycycle(pin, 0)
    
    def set(self, *vals):
        for pin, scale, phase, val in zip(self.gpio, self.scales, self.phase, vals):
            self.pi.set_PWM_dutycycle(pin, scale*val, phase)

class Dimmer(object):
    "Mains dimmer controller"
    
    def __init__(self, pi, gpio, min_pwm, max_pwm, phase=0):
        self.pi = pi
        self.gpio = gpio
        self.offset = min_pwm
        self.scale  = max_pwm - min_pwm
        self._max_power = 1.0
        self.set(0)
    
    def __del__(self):
        self.pi.set_PWM_dutycycle(self.gpio, 0)
    
    def clamp(self, val):
        "Sets a maximum output power command"
        self._max_power = val
        if self._output > val: # If current setting is over clamp, adjust now
            self.set(val)
    
    def set(self, val):
        "Set output value, mapped to minimum and maximum PWM values"
        if val < 0.0 or val > 1.0:
            raise ValueError("val must be in the range [0.0 to 1.0] but was given {}".format(val))
        if val > self._max_power:
            val = self._max_power
        self.pi.set_PWM_dutycycle(self.gpio, (val * self.scale) + self.offset, self.phase)
        self._output = val
