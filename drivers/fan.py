#!/usr/bin/env python3
"""
Classes for PWMing fans
"""
__author__ = "<Daniel Casner <www.danielcasner.org>"

def DiscreteFan(object):
    "A simple fan controller with discrete PWM speeds"

    def __init__(self, pi, gpio, speeds=(0, 4095), phase=0):
        "Setup the fan"
        self.pi = pi
        self.gpio = gpio
        self.speeds = speeds
        self.phase = phase
        self.set(0)

    def set(self, speed_index):
        "Sets the fan to the speed given by index"
        self.pi.set_PWM_dutycycle(self.gpio, self.speeds[speed_index], self.phase)

    def __del__(self):
        self.pi.set_PWM_dutycycle(self.gpio, 0)
