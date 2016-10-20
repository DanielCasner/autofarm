#!/usr/bin/env python3
"""
Module to monitor system (CPU, memory, etc.) health in general and for this process.
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import os
import psutil

class HealthMonitor(psutil.Process):
    
    def __init__(self, pid=os.getpid()):
        psutil.Process.__init__(self, pid)
    
    def temperature(self):
        "Returns the current CPU temperature in ºC"
        return float(open("/sys/class/thermal/thermal_zone0/temp", "r").read().strip())/1000.0

    def load(self):
        "Returns the current CPU utalization percentage"
        return psutil.cpu_percent(), self.cpu_percent()
        
    def memory(self):
        "Returns the current memory utalization percentage"
        return psutil.virtual_memory().percent, self.memory_percent()


if __name__ == '__main__':
    "Unit test"
    h = HealthMonitor()
    print("Temperature:", h.temperature())
    print("       Load:", h.load())
    print("     Memory:", h.memory())
