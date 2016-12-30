#!/usr/bin/env python3
"""
Logic for controlling the chicken coop door.
"""

import pigpio
import logging
import json
import time
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
    OPEN_TIMEOUT      = 20
    CLOSE_TIMEOUT     = 27
    OPEN_SPEED        = -1.0
    CLOSE_SPEED       =  0.5
    LATCH_SPEED       =  1.0
    LATCH_DURATION    =  3.0
    GLITCH_FILTER_µs  = 3000
        
    def __init__(self, pi, in1, in2, closed_sw, open_sw, client, door_status_topic):
        "Sets up the door logic with motor driver in1 and in2 and closed and open microswitches"
        self.enabled = True
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
        time.sleep(0.1)
    
    def __del__(self):
        self.enabled = False
        self.stop()
    
    def check_status_and_publish(self):
        if self.pi.read(self.open_sw) == 0:
            self.client.publish(self.door_status_topic, self.DOOR_OPEN_TOKEN, qos=1, retain=True)
        elif self.pi.read(self.closed_sw) == 0:
            self.client.publish(self.door_status_topic, self.DOOR_CLOSED_TOKEN, qos=1, retain=True)
        else:
            self.client.publish(self.door_status_topic, self.DOOR_AJAR_TOKEN, qos=1, retain=True)
    
    def stop(self):
        self.motor.stop()
        self.check_status_and_publish()
    
    def open(self, speed=1.0):
        "Trigger the door to open, optionally set a multiple of normal speed."
        if not self.enabled:
            return
        elif self.pi.read(self.open_sw):
            self.logger.info("Door already open")
        else:
            start_time = time.time()
            self.motor.drive(self.OPEN_SPEED * speed)
            self.logger.debug("Door opening")
            while time.time() < start_time + self.OPEN_TIMEOUT:
                if self.pi.read(self.open_sw):
                    self.stop()
                    self.logger.info("Door now open")
                    break
            else:
                self.stop()
                self.logger.debug("Door did not open in time")
            
    
    def close(self, speed=1.0):
        "Trigger the door to close, optionally set a multiple of normal speed"
        if not self.enabled:
            return
        elif self.pi.read(self.closed_sw):
            self.logger.info("Door already closed")
        else:
            start_time = time.time()
            self.motor.drive(self.CLOSE_SPEED * speed)
            self.logger.debug("Door closing")
            while time.time() < start_time + self.CLOSE_TIMEOUT:
                if self.pi.read(self.closed_sw):
                    self.motor.drive(self.LATCH_SPEED * speed)
                    self.logger.debug("Latching")
                    time.sleep(self.LATCH_DURATION)
                    self.stop()
                    self.logger.info("Door now closed")
                    break
            else:
                self.stop()
                self.logger.debug("Door did not open in time")

    def enable(self, enabled):
        self.enabled = enabled

if __name__ == '__main__':
    import sys
    import PCA9685_pigpio
    logging.basicConfig(level=logging.DEBUG)
    class DummyClient:
        def publish(self, *args, **kwargs):
            print("MQTT Publish:", repr(args), repr(kwargs))


    print("Initalizing PI")
    pi = PCA9685_pigpio.PCA9685Pi()

    print("Initalizing Door")
    door = Door(pi, COOP_MOT_IN1, COOP_MOT_IN2, COOP_CLOSED_SW, COOP_OPEN_SW, DummyClient(), "DUMMY_DOOR")

    if len(sys.argv) > 1:
        if sys.argv[1] == "open":
            door.open()
        elif sys.argv[1] == "close":
            door.close()

    del door
