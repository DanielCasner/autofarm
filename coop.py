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
EXTERIOR_LIGHTS  = (-1 + PCA9685Pi.EXTENDER_OFFSET,
                   -1 + PCA9685Pi.EXTENDER_OFFSET,
                   -1 + PCA9685Pi.EXTENDER_OFFSET)
HEN_HOUSE_IR     = -1 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_LIGHT  =  5 + PCA9685Pi.EXTENDER_OFFSET
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
    hen_door.enable(False)
    sun_scheduler.addEvent(hen_door.open,  ('sunrise', datetime.timedelta(0)))
    sun_scheduler.addEvent(hen_door.close, ('dusk',    datetime.timedelta(0)))
    # Hen house SAD lamp
    logger.debug("Setting up hen house light")
    global hen_lamp
    hen_lamp = lights.SlowLinearFasder(pi, [HEN_HOUSE_LIGHT], [PCA9685Pi.MAX_PWM], [0])
    sun_scheduler.addEvent(lambda: hen_lamp.setTarget(1.0, 45*60),
                           after  = ('noon', datetime.timedelta(hours=-7)),
                           before = ('dawn', datetime.timedelta(0)), # Only turn on light if less than 14 hours of daylight
                           )
    sun_scheduler.addEvent(lambda: hen_lamp.setTarget(0.0, 45*60),
                           after  = ('noon', datetime.timedelta(hours=6, minutes=15)), # Always let hens sleep
                           )
    # Camera IR Illuminator
    logger.debug("Setting up hen house camera IR illuminator")
    global hen_illuminator
    hen_illuminator = lights.Light(pi, [HEN_HOUSE_IR], [PCA9685Pi.MAX_PWM])
    sun_scheduler.addEvent(lambda: hen_illuminator.set(0.00), ('sunrise', datetime.timedelta(0)))
    sun_scheduler.addEvent(lambda: hen_illuminator.set(0.25), ('sunset', datetime.timedelta(0)))

def ParsePayload(msg, lb=None, ub=None, options=None):
    try:
        cmd = json.loads(msg.payload)
    except:
        logger.warn("Unable to parse payload of message on topic \"{0.topic}\": {0.payload}".format(msg))
        return None
    else:
        if options:
            if not cmd in options:
                logger.warn("Invalid command of message on topic \"{0.topic}\" (options are {1!r}): {0.payload}".format(msg, options))
                return None
            else:
                return cmd
        else:
            if lb is not None and cmd < lb:
                logger.warn("Command for topic {}, {} < lower bound {}".format(msg.topic, cmd, lb))
                return None
            elif ub is not None and cmd > ub:
                logger.warn("Command for topic {}, {} > upper bound {}".format(msg.topic, cmd, ub))
                return None
            else:
                return cmd

def DoorCommand(msg):
    cmd = ParsePayload(msg, options=["OPEN", "CLOSE", "ENABLE", "DISABLE"])
    if cmd == 'OPEN':
        hen_door.open()
    elif cmd == 'CLOSE':
        hen_door.close()
    elif cmd == 'ENABLE':
        hen_door.enable(True)
    elif cmd == 'DISABLE':
        hen_door.enable(False)

def HenHouseLightCommand(msg):
    cmd = ParsePayload(msg)
    if cmd is not None:
        hen_lamp.setTarget(cmd, 5) # 5 second fade

def HenHouseIlluminator(msg):
    cmd = ParsePayload(msg)
    if cmd is not None:
        hen_illuminator.set(cmd)

def Automate(mqtt_connect_args):
    "Run the automation main loop"
    logger.debug("Starting MQTT client thread")
    mqtt_client.loop_start() # Start MQTT client in its own thread
    mqtt_client.connect(*mqtt_connect_args)
    InitalizeHardware()
    mqtt_client.subscribe(topic_join(base_topic, "door", "command"), 1, DoorCommand)
    mqtt_client.subscribe(topic_join(base_topic, "house_light", "brightness", 1, HenHouseLightCommand))
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
    parser.add_argument('-v', "--verbose", help="More verbose debugging output")
    parser.add_argument("location", type=argparse.FileType('rb'), help="Pickle file containing an Astral location instance for almanac")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARN)
    
    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)

    base_topic = args.topic
    mqtt_client = SharedClient(args.clientID, not args.clientID)
    hmon = health.HealthMonitor()
    sun_scheduler = almanac.SunScheduler(args.location)

    Automate(brokerConnect)
