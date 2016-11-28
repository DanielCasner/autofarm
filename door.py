#!/usr/bin/env python3
"""
Logic for controlling the chicken coop door.
"""

import pigpio
import logging
import json
from DRV8871 import Motor

COOP_OPEN_SW   = 17
COOP_CLOSED_SW =  4
COOP_MOT_IN1   = 0x10e
COOP_MOT_IN2   = 0x10f


class Door:
    """Object for door control"""
    
    DOOR_OPEN_TOKEN   = json.dumps("OPEN")
    DOOR_CLOSED_TOKEN = json.dumps("CLOSED")
    DOOR_AJAR_TOKEN   = json.dumps('AJAR')
    OPEN_TIMEOUT_MS   = 20000
    CLOSE_TIMEOUT_MS  = 20000
    OPEN_SPEED        = -1.0
    CLOSE_SPEED       =  0.5
    LATCH_SPEED       =  1.0
    LATCH_DURATION    =  1.0
    GLITCH_FILTER_µs  = 3000
    
    def __init__(self, pi, in1, in2, closed_sw, open_sw, client, door_status_topic):
        "Sets up the door logic with motor driver in1 and in2 and closed and open microswitches"
        self.enabled = False
        self.pi = pi
        self.motor = Motor(pi, in1, in2)
        pi.set_mode(closed_sw, pigpio.INPUT)
        pi.set_pull_up_down(closed_sw, pigpio.PUD_UP)
        pi.set_glitch_filter(closed_sw, self.GLITCH_FILTER_µs)
        pi.set_mode(open_sw, pigpio.INPUT)
        pi.set_pull_up_down(open_sw, pigpio.PUD_UP)
        pi.set_glitch_filter(open_sw, self.GLITCH_FILTER_µs)
        self.closed_sw = closed_sw
        self.open_sw = open_sw 
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.door_status_topic = door_status_topic
        self.enabled = True
    
    def __del__(self):
        self.enabled = False
        self.stop()
    
    def stop(self):
        self.motor.stop()
        self.pi.set_watchdog(self.open_sw,   0)
        self.pi.set_watchdog(self.closed_sw, 0)
        self.check_status_and_publsh()
    
    def publish_open(self):
        self.client.publish(self.door_status_topic, self.DOOR_OPEN_TOKEN, qos=1, retain=True)
        
    def publish_closed(self):
        self.client.publish(self.door_status_topic, self.DOOR_CLOSED_TOKEN, qos=1, retain=True)
        
    def publish_ajar(self):
        self.client.publish(self.door_status_topic, self.DOOR_AJAR_TOKEN, qos=1, retain=True)
    
    def check_status_and_publsh(self):
        if self.pi.read(self.open_sw) == 0:
            self.publish_open()
        elif self.pi.read(self.closed_sw) == 0:
            self.publish_closed()
        else:
            self.publish_ajar()
    
    def _open_cb(self, gpio, level, tick):
        "Callback when open_sw is triggered"
        if level == 1:
            # Door finished opening
            self.motor.stop()
            self.pi.set_watchdog(self.open_sw, 0)
            self.logger.debug("Door now open")
            self.publish_open()
        elif level == pigpio.TIMEOUT:
            self.stop()
            self.logger.warn("Door did not open in time")
        else:
            self.stop()
            self.logger.error("Unexpected door open switch status: {}".format(level))
    
    def _close_cb(self, gpio, level, tick):
        "Callback when closed_sw is triggered"
        if level == 1:
            # Door finished closing
            self.pi.set_watchdog(self.closed_sw, 0)
            self.motor.drive(self.LATCH_SPEED)
            time.sleep(self.LATCH_DURATION)
            self.motor.stop()
            self.logger.debug("Door now closed")
            self.publish_closed()
        elif level == pigpio.TIMEOUT:
            self.stop()
            self.logger.warn("Door did not close in time")
        else:
            self.stop()
            self.logger.error("Unexpected door close switch status: {}".format(level))
    
    def open(self, speed=1.0):
        "Trigger the door to open, optionally set a multiple of normal speed."
        if not self.enabled:
            return
        elif self.pi.read(self.open_sw) == 1:
            self.logger.debug("Door already open")
        else:
            self.pi.callback(self.open_sw, pigpio.RISING_EDGE, self._open_cb)
            self.pi.set_watchdog(self.open_sw, self.OPEN_TIMEOUT_MS)
            self.motor.drive(self.OPEN_SPEED * speed)
            self.logger.debug("Door opening")
    
    def close(self, speed=1.0):
        "Trigger the door to close, optionally set a multiple of normal speed"
        if not self.enabled:
            return
        elif self.pi.read(self.closed_sw) == 1:
            self.logger.debug("Door already closed")
        else:
            self.pi.callback(self.closed_sw, pigpio.RISING_EDGE, self._close_cb)
            self.pi.set_watchdog(self.closed_sw, self.CLOSE_TIMEOUT_MS)
            self.motor.drive(self.CLOSE_SPEED * speed)
            self.logger.debug("Door closing")

    def enable(self, enabled):
        self.enabled = enabled

        
if __name__ == '__main__':
    import sys
    import time
    import PCA9685_pigpio
    class DummyClient:
        def publish(self, *args, **kwargs):
            pass

    pi = PCA9685_pigpio.PCA9685Pi()
    door = Door(pi, COOP_MOT_IN1, COOP_MOT_IN2, COOP_CLOSED_SW, COOP_OPEN_SW, DummyClient(), "DUMMY_DOOR")

    if len(sys.argv) > 1:
        if sys.argv[1] == "open":
            door.open()
            time.sleep(door.OPEN_TIMEOUT_MS/1000.0)
        elif sys.argv[1] == "close":
            door.close()
            time.sleep(door.CLOSE_TIMEOUT_MS/1000.0)

    door.stop()
