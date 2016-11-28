#!/usr/bin/env python3
"""
Chicken coop automation main executable.
This program administers the automation logic for the coop.
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import sys
import os
import time
import subprocess
import argparse
import logging
import datetime
from PCA9685_pigpio import *
from door import *
from thermostat import Thermostat
import candle
import lights
import health
import almanac
from sharedclient import SharedClient, topic_join

DOOR_OPEN_SW     = COOP_OPEN_SW
DOOR_CLOSED_SW   = COOP_CLOSED_SW
EXTERIOR_LIGHTS  = (4 + PCA9685Pi.EXTENDER_OFFSET,
                    5 + PCA9685Pi.EXTENDER_OFFSET,
                    6 + PCA9685Pi.EXTENDER_OFFSET)
HEN_HOUSE_IR     =  6 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_LIGHT  =  7 + PCA9685Pi.EXTENDER_OFFSET
BROODER_HEATER   =  8 + PCA9685Pi.EXTENDER_OFFSET
BROODER_COOLER   =  9 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_HEATER = 10 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_COOLER = 11 + PCA9685Pi.EXTENDER_OFFSET
DOOR_MOT_IN2     = COOP_MOT_IN2
DOOR_MOT_IN1     = COOP_MOT_IN1
DEBUG_LED1       = 0xc + PCA9685Pi.EXTENDER_OFFSET
DEBUG_LED2       = 0xd + PCA9685Pi.EXTENDER_OFFSET

# Mains dimmers run backwards
DIMMER_MAX_PWM = 0
DIMMER_MIN_PWM = 4096

THERMOSTAT_PID = (1.0, 0.0, 0.0, 1.0)

logger         = logging.getLogger(__name__)
mqtt_client    = None
base_topic     = None
sun_scheduler  = None
hmon           = None

def InitalizeHardware():
    # Set up pigpio interface
    global pi
    pi = PCA9685Pi()
    pi.set_PWM_frequency(PCA9685Pi.EXTENDER_OFFSET, 28000) # Required for Fan control, should be okay for everything else
    # Hen house door
    logger.debug("Setting up hen door")
    global hen_door
    hen_door = Door(pi, DOOR_MOT_IN1, DOOR_MOT_IN2, DOOR_CLOSED_SW, DOOR_OPEN_SW, mqtt_client, topic_join(base_topic, "door", "status"))
    sun_scheduler.addEvent(('sunrise', datetime.timedelta(0)), hen_door.open)
    sun_scheduler.addEvent(('dusk',    datetime.timedelta(0)), hen_door.close)
    return
    # Hen house SAD lamp
    logger.debug("Setting up hen house light")
    global hen_lamp
    hen_lamp = lights.SlowLinearFasder(pi, [HEN_HOUSE_LIGHT], [PCA9685Pi.MAX_PWM], [0])
    sun_scheduler.addEvent(after  = ('noon', datetime.timedelta(hours=-7)),
                           before = ('dawn', datetime.timedelta(0)), # Only turn on light if less than 14 hours of daylight
                           callback = lambda: hen_lamp.setTarget(1.0, 45*60))
    sun_scheduler.addEvent(after  = ('noon', datetime.timedelta(hours=6, minutes=15)), # Always let hens sleep
                           callback = lambda: hen_lamp.setTarget(0.0, 45*60))
    # Camera IR Illuminator
    logger.debug("Setting up hen house camera IR illuminator")
    global hen_illuminator
    hen_illuminator = lights.Light(pi, [HEN_HOUSE_IR], [PCA9685Pi.MAX_PWM])
    sun_scheduler.addEvent(after = ('sunrise', datetime.timedelta(0)),
                                    callback = lambda: hen_illuminator.set(0.00))
    sun_scheduler.addEvent(after = ('sunset', datetime.timedelta(0)),
                                    callback = lambda: hen_illuminator.set(0.25))

def DoorCommand(msg):
    try:
        cmd = json.loads(msg.payload)
    except:
        logger.warn("Unable to decode door command: {}".format(msg.payload))
    else:
        if cmd == 'OPEN':
            hen_door.open()
        elif cmd == 'CLOSE':
            hen_door.close()
        elif cmd == 'ENABLE':
            hen_door.enable(True)
        elif cmd == 'DISABLE':
            hen_door.enable(False)
        else:
            logger.warn("Invalid door command: {}".format(cmd))

def HenHouseLightCommand(msg):
    try:
        cmd = json.loads(msg.payload)
    except:
        logger.warn("Unable to decode hen house light command: {}".format(msg.payload))
    else:
        if not (cmd >= 0.0 and cmd <= 1.0):
            logger.warn("Invalid hen house light command: {}".format(cmd))
        else:
            hen_lamp.setTarget(cmd, 5) # 5 second fade

def HenHouseIlluminator(msg):
    try:
        cmd = json.loads(msg.payload)
    except:
        logger.warn("Unable to decode hen house illuminator command: {}".format(msg.payload))
    else:
        if not (cmd >= 0.0 and cmd <= 1.0):
            logger.warn("Invalid hen house illuminator command: {}".format(cmd))
        else:
            hen_illuminator.set(cmd)

def Automate(mqtt_connect_args):
    "Run the automation main loop"
    logger.debug("Starting MQTT client thread")
    mqtt_client.loop_start() # Start MQTT client in its own thread
    mqtt_client.connect(*mqtt_connect_args)
    InitalizeHardware()
    mqtt_client.subscribe(topic_join(base_topic, "door", "command"), 1, DoorCommand)
    #mqtt_client.subscribe(topic_join(base_topic, "house_light", "brightness", 1, HenHouseLightCommand))
    logger.debug("Entering main loop")
    try:
        while True:
            next(sun_scheduler)
            next(hen_lamp)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.debug("Exiting at sig-exit")
    # Clean up peripherals
    mqtt_client.loop_stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--clientID", type=str, default="", help="MQTT client ID for the counter node")
    parser.add_argument("-b", "--brokerHost", type=str, default="localhost", help="MQTT Broker hostname or IP address")
    parser.add_argument('-p', "--brokerPort", type=int, help="MQTT Broker port")
    parser.add_argument('-k', "--brokerKeepAlive", type=int, help="MQTT keep alive seconds")
    parser.add_argument('-n', "--bind", type=str, help="Local interface to bind to for connection to broker")
    parser.add_argument('-t', "--topic", type=str, default="coop", help="Base MQTT topic")
    parser.add_argument("location", type=argparse.FileType('rb'), help="Pickle file containing an Astral location instance for almanac")
    args = parser.parse_args()
    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)

    base_topic = args.topic
    mqtt_client = SharedClient(args.clientID, not args.clientID)
    hmon = health.HealthMonitor()
    sun_scheduler = almanac.SunScheduler(args.location)

    Automate(brokerConnect)
