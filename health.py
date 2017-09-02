#!/usr/bin/env python3
"""
Module to monitor system (CPU, memory, etc.) health in general and for this process.
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import os
import psutil
import time
import json

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
        
    def uptime(self):
        "Returns the amount of time this process has been running"
        return time.time() - self.create_time()

class HealthPublisher(HealthMonitor):
    "Class for puriodically publishing health data"
    
    def __init__(self, client, topic, interval=30, pid=os.getpid()):
        HealthMonitor.__init__(self, pid)
        self.client = client
        self.topic = topic
        self.interval = interval
        self.last_publish_time = 0.0
        
    def __next__(self):
        "Step the publisher"
        now = time.time()
        if now - self.last_publish_time >= self.interval:
            msg = {
                "cpu_temp": self.temperature(),
                "load":     self.load(),
                "memory":   self.memory(),
                "uptime":   self.uptime(),
            }
            self.client.publish(self.topic, json.dumps(msg))
            self.last_publish_time = now

if __name__ == '__main__':
    "Unit test"
    h = HealthMonitor()
    print("Temperature:", h.temperature())
    print("       Load:", h.load())
    print("     Memory:", h.memory())
