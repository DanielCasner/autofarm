#!/usr/bin/env python3
"""
Software driver for DRV8871 motor driver using pigpio
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import pigpio

class Motor:
    "Object interface for DRV8871 motor driver. Relies on pigpio api"
    
    def __init__(self, pi, in1, in2):
        self.pi = pi
        self.gpio = (in1, in2)
        self.coast()
        
    def coast(self):
        "Put motor into coast mode, drivers in high-Z mode"
        for p in self.gpio:
            self.pi.write(p, 0)
    
    def stop(self):
        "Put the motor into break mode"
        for p in self.gpio:
            self.pi.write(p, 1)
    
    def drive(self, speed):
        "Drive the motor, speed has range -1.0 to +1.0"
        # Assumes PIGPIO default PWM range of 255
        if speed == 0:
            self.coast()
        elif speed > 0:
            dutycycle = round(speed * 255)
            self.pi.write(self.gpio[1], 0)
            self.pi.set_PWM_dutycycle(self.gpio[0], dutycycle)
        else: # speed < 0
            dutycycle = round(speed * -255)
            self.pi.write(self.gpio[0], 0)
            self.pi.set_PWM_dutycycle(self.gpio[1], dutycycle)
            
