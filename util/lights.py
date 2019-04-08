#!/usr/bin/env python3
"""
Lighting helper functions
Based on pgpio
"""

import time
import logging

class Light(object):
    "One or more channel driver"

    def clamp(self, val):
        return max(0, min(val, self.maximum))

    def __init__(self, pi, gpios, maximum, scale=1, phases=None, gamma=1):
        self.pi = pi
        self.gpio = tuple(gpios)
        self.maximum = maximum
        self.scale = scale
        if phases is None:
            self.phase = tuple([0]*len(self.gpio))
        else:
            self.phase = tuple(phases)
        self.gamma = gamma
        self.set(*([0] * len(gpios)))
        self.logger = logging.getLogger(repr(self))
        self.logger.debug("Light initalized with gpios={0.gpio!r}, "
                          "maximum={0.maximum!r} scale={0.scale!r}, "
                          "phase={0.phase!r}, gamma={0.gamma!r}".format(self))

    def set(self, *vals):
        "Update the target value of the light"
        self._target = vals
        for pin, phase, val in zip(self.gpio, self.phase, vals):
            if self.gamma == 1:
                out = self.clamp(val * self.scale)
            else:
                out = self.clamp(pow(val * self.scale / self.maximum, self.gamma) * self.maximum)
            self.pi.set_PWM_dutycycle(pin, out, phase)

    def get(self):
        "Retrieve the current target of the light"
        return self._target

    def __repr__(self):
        return "{0.__class__.__name__}(gpios={0.gpio!r})".format(self)

class SlowLinearFader(Light):
    "A light object that supports slow fading"

    def __init__(self, *a, **kw):
        Light.__init__(self, *a, **kw)
        self.start_val = [0]
        self.end_val = [0]
        self.start_time = 0
        self.end_time = 0
        self.done = False

    def setTarget(self, duration, targets):
        "Start linearly fading from current value to target over duration seconds"
        self.logger.info("Fading to % over % seconds", targets, duration)
        self.done = False
        self.start_val = self.get()
        self.end_val = targets
        self.start_time = time.time()
        self.end_time = self.start_time + duration

    def __next__(self):
        now = time.time()
        if now < self.end_time:
            delta = now - self.start_time
            progress = delta / (self.end_time - self.start_time)
            interpolation = [sv * (1.0 - progress) + ev * (progress) for sv, ev in zip(self.start_val, self.end_val)]
            self.set(*interpolation)
            return interpolation
        elif not self.done:
            self.set(*self.end_val)
            self.done = True
            return self.end_val
        return None

class GasLamp(SlowLinearFader):
    "A slow linear fater which can also be driven by candle flicker algorithm"

    def __init__(self, flicker, color_scaling, *light_args, **light_kw_args):
        SlowLinearFader.__init__(self, *light_args, **light_kw_args)
        self.flicker = flicker
        next(self.flicker) # Initalize candle
        self.fuel = None # If not none, do candle, if none do slow linear fade
        self.candle_scaling = color_scaling

    def setTarget(self, *args):
        "Sets explicit target"
        self.fuel = None
        SlowLinearFader.setTarget(self, *args)

    def setCandle(self, fuel):
        "Sets the light to fuel mode"
        self.fuel = fuel

    def __next__(self):
        if self.fuel is None:
            SlowLinearFader.__next__(self)
        else:
            flame = self.flicker.send(self.fuel)
            self.set(*(scale * flame for scale in self.candle_scaling))
            return flame

class Dimmer(object):
    "Mains dimmer controller"

    def __init__(self, pi, gpio, min_pwm, max_pwm):
        self.pi = pi
        self.gpio = gpio
        self.offset = min_pwm
        self.scale = max_pwm - min_pwm
        self._max_power = 1.0
        self.set(0)

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
        self.pi.set_PWM_dutycycle(self.gpio, (val * self.scale) + self.offset)
        self._output = val


if __name__ == '__main__':
    # Unit tests
    import sys
    logging.basicConfig(level=logging.DEBUG)
    class SpyPi:
        "Unit testing spy class"
        def __init__(self):
            self.expect = None
        def expect_pwm_cmd(self, *args):
            self.expect = args
        def set_PWM_dutycycle(self, *args):
            assert args == self.expect, "FAIL: set_PWM_dutycycle expected {!r} but got {!r}".format(self.expect, args)
    class DummyPi:
        "Unit testing dummy class"
        def __init__(self, verbose=True):
            self.verbose = verbose
        def set_PWM_dutycycle(self, *args):
            if self.verbose:
                print("Set PWM:", repr(args))

    if "dimmer" in sys.argv:
        pi = DummyPi(False)
        l = SlowLinearFader(pi, [0], 4095, 4096, gamma=2.8)
        print(next(l))
        l.setTarget(10, [1.0])
        t = time.time()
        while time.time() < t + 10:
            print(next(l))
        l.setTarget(1, [0.1])
        t = time.time()
        while time.time() < t + 2:
            print(next(l))

    else:
        pi = SpyPi()
        pi.expect_pwm_cmd(0, 0.0, 0.0)
        l = Light(pi, [0], 1)
        pi.expect_pwm_cmd(0, 1, 0)
        l.set(1)
        pi.expect_pwm_cmd(0, 0, 1)
        l = Light(pi, [0], 100, 100, [1])
        pi.expect_pwm_cmd(0, 100, 1)
        l.set(1)

        print("PASS")
