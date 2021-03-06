#!/usr/bin/env python3
"""
Chicken coop automation main executable.
This program administers the automation logic for the coop.
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import sys
import argparse
import logging
from logging import handlers
import os
import datetime
import json
import re
from PCA9685_pigpio import *
from door import *
#from thermostat import Thermostat
#import candle
import lights
import health
import almanac
from sharedclient import SharedClient, topic_join
from mqtthandler import MQTTHandler
from candle import Flicker
import fans

DOOR_OPEN_SW     = COOP_OPEN_SW
DOOR_CLOSED_SW   = COOP_CLOSED_SW
EXTERIOR_LIGHTS  = (-1 + PCA9685Pi.EXTENDER_OFFSET,
                   -1 + PCA9685Pi.EXTENDER_OFFSET,
                   -1 + PCA9685Pi.EXTENDER_OFFSET)
HEN_HOUSE_IR     = -1 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_LIGHT  =  5 + PCA9685Pi.EXTENDER_OFFSET
BROODER_HEATER   = -1 + PCA9685Pi.EXTENDER_OFFSET
BROODER_COOLER   = -1 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_HEATER = -1 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_COOLER = -1 + PCA9685Pi.EXTENDER_OFFSET
DOOR_MOT_IN2     = COOP_MOT_IN2
DOOR_MOT_IN1     = COOP_MOT_IN1
DEBUG_LED1       = 0xc + PCA9685Pi.EXTENDER_OFFSET
DEBUG_LED2       = 0xd + PCA9685Pi.EXTENDER_OFFSET

# Mains dimmers run backwards
DIMMER_MAX_PWM = 0
DIMMER_MIN_PWM = 4096

LED_MAX_PWM = 4095

THERMOSTAT_PID = (1.0, 0.0, 0.0, 1.0)

HEN_LAMP_MAX = 100

RGB_RE = re.compile(r"rgb\((\d+),(\d+),(\d+)\)")

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
    sun_scheduler.addEvent(hen_door.open,  ('sunrise', datetime.timedelta(0)))
    sun_scheduler.addEvent(hen_door.close, ('dusk',    datetime.timedelta(0)))
    sun_scheduler.addEvent(hen_door.warn,  ('dusk',    datetime.timedelta(seconds=-45)))
    # Hen house SAD lamp
    logger.debug("Setting up hen house light")
    global hen_lamp
    hen_lamp = lights.SlowLinearFader(pi, [HEN_HOUSE_LIGHT], LED_MAX_PWM, LED_MAX_PWM/100, [0], 2.8)
    sun_scheduler.addEvent(lambda: hen_lamp.setTarget(45*60, [HEN_LAMP_MAX*0.80]),
                           after  = ('noon', datetime.timedelta(hours=-7)),
                           before = ('dawn', datetime.timedelta(0)), # Only turn on light if less than 14 hours of daylight
                           )
    sun_scheduler.addEvent(lambda: hen_lamp.setTarget(45*60, [0.0]),
                           after  = ('noon', datetime.timedelta(hours=6, minutes=15)), # Always let hens sleep
                           )
    if ((sun_scheduler.sun['noon'] - sun_scheduler.sun['dawn']) < datetime.timedelta(hours=7)) and \
       (abs(sun_scheduler.sun['noon'] - datetime.datetime.now(sun_scheduler.location.tz)) < datetime.timedelta(hours=7)):
        hen_lamp.setTarget(45, [HEN_LAMP_MAX*0.80])
    # Camera IR Illuminator
    #logger.debug("Setting up hen house camera IR illuminator")
    #global hen_illuminator
    #hen_illuminator = lights.Light(pi, [HEN_HOUSE_IR], [PCA9685Pi.MAX_PWM])
    #sun_scheduler.addEvent(lambda: hen_illuminator.set(0.00), ('sunrise', datetime.timedelta(0)))
    #sun_scheduler.addEvent(lambda: hen_illuminator.set(0.25), ('sunset', datetime.timedelta(0)))
    global exterior_lamp
    exterior_lamp = lights.GasLamp(Flicker(),
                                   (255, 128, 64),
                                   pi, EXTERIOR_LIGHTS, LED_MAX_PWM,
                                   LED_MAX_PWM/255, (1000, 2000, 3000), 2.8)
    global hen_cooler
    hen_cooler = fan.DiscreteFan(pi, HEN_HOUSE_COOLER, (0, 4095*8/12, 4095*10/12, 4095), 500)

def CleanupHardware():
    global hen_door
    del hen_door
    global hen_lamp
    del hen_lamp
    global exterior_lamp
    del exterior_lamp
    global hen_cooler
    del hen_cooler

def ParsePayload(msg, lb=None, ub=None, required_type=None, options=None):
    try:
        cmd = json.loads(msg.payload.decode())
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
            if required_type is not None and type(cmd) is not required_type:
                logger.warn("Command for topic {}, is type {} not {}".format(msg.topic, type(cmd), required_type))
            elif lb is not None and cmd < lb:
                logger.warn("Command for topic {}, {} < lower bound {}".format(msg.topic, cmd, lb))
                return None
            elif ub is not None and cmd > ub:
                logger.warn("Command for topic {}, {} > upper bound {}".format(msg.topic, cmd, ub))
                return None
            else:
                return cmd

def DoorCommand(msg):
    cmd = ParsePayload(msg, options=["OPEN", "CLOSE", "STOP", "WARN", "ENABLE", "DISABLE"])
    if cmd == 'OPEN':
        hen_door.open()
    elif cmd == 'CLOSE':
        hen_door.close()
    elif cmd == 'STOP':
        hen_door.stop()
    elif cmd == 'WARN':
        hen_door.warn()
    elif cmd == 'ENABLE':
        hen_door.enable(True)
    elif cmd == 'DISABLE':
        hen_door.enable(False)

def HenHouseLightCommand(msg):
    cmd = ParsePayload(msg, 0, 100)
    if cmd is not None:
        hen_lamp.setTarget(5, [cmd]) # 5 second fade

def ExteriorBrightness(msg):
    try:
        target = [int(c) for c in RGB_RE.match(msg.payload)]
    except:
        logger.warn("Unable to parse RGB command on topic \"{0.topic}\": {0.payload}".format(msg))
    else:
        exterior_lamp.setTarget(5, target)

def ExteriorFuel(msg):
    cmd = ParsePayload(msg, 0, 100)
    if cmd is not None:
        exterior_lamp.setCandle(cmd/50.0)
    else:
        exterior_lamp.setCandle(1.0)

def HenCoolerSpeed(msg):
    cmd = ParsePayload(msg, 0, 3, int)
    if cmd is not None:
        hen_cooler.set(cmd)

def Automate(mqtt_connect_args):
    "Run the automation main loop"
    logger.debug("Starting MQTT client thread")
    mqtt_client.loop_start() # Start MQTT client in its own thread
    mqtt_client.connect(*mqtt_connect_args)
    InitalizeHardware()
    mqtt_client.subscribe(topic_join(base_topic, "door", "command"), 1, DoorCommand)
    mqtt_client.subscribe(topic_join(base_topic, "house_light", "brightness"), 1, HenHouseLightCommand)
    mqtt_client.subscribe(topic_join(base_topic, "exterior", "brightness"), 1, ExteriorBrightness)
    mqtt_client.subscribe(topic_join(base_topic, "exterior", "fuel"), 1, ExteriorFuel)
    mqtt_client.subscribe(topic_join(base_topic, "hen_cooler", "speed"), 1, HenCoolerSpeed)
    mqtt_client.loop_timeout = 0.050
    logger.debug("Entering main loop")
    try:
        while True:
            next(sun_scheduler)
            next(hen_lamp)
            next(exterior_lamp)
            next(hmon)
            next(mqtt_client)
    except KeyboardInterrupt:
        logger.info("Exiting at sig-exit")
    # Clean up peripherals
    CleanupHardware()
    logger.info("Hardware cleanup done")
    mqtt_client.loop_stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--clientID", type=str, default="", help="MQTT client ID for the counter node")
    parser.add_argument("-b", "--brokerHost", type=str, default="localhost", help="MQTT Broker hostname or IP address")
    parser.add_argument('-p', "--brokerPort", type=int, help="MQTT Broker port")
    parser.add_argument('-k', "--brokerKeepAlive", type=int, help="MQTT keep alive seconds")
    parser.add_argument('-n', "--bind", type=str, help="Local interface to bind to for connection to broker")
    parser.add_argument('-t', "--topic", type=str, default="coop", help="Base MQTT topic")
    parser.add_argument('-v', "--verbose", action="store_true", help="More verbose debugging output")
    parser.add_argument('-l', "--log_file", type=str, help="Base file to write logs to, will automatically roll over ever 16 MB")
    parser.add_argument('-m', "--log_mqtt", action="store_true", help="If specified, logged events will be sent to mqtt")
    parser.add_argument("location", type=argparse.FileType('rb'), help="Pickle file containing an Astral location instance for almanac")

    if len(sys.argv) == 1 and os.path.isfile('coop.args'):
        cached_args = open('coop.args', 'r').read()
        print("Running with ached args:", cached_args)
        args = parser.parse_args(cached_args.split())
    else:
        args = parser.parse_args()

    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)

    base_topic = args.topic
    mqtt_client = SharedClient(args.clientID, not args.clientID)

    logHandlers = []
    if args.log_file:
        rfh = handlers.RotatingFileHandler(args.log_file, maxBytes=0x1000000)
        rfh.setLevel(logging.WARN)
        logHandlers.append(rfh)
    if args.log_mqtt:
        mh = MQTTHandler(mqtt_client, topic_join(base_topic, "log"))
        mh.setLevel(logging.DEBUG if args.verbose else logging.INFO)
        logHandlers.append(mh)
    if args.verbose:
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.DEBUG)
        logHandlers.append(sh)
    elif not len(logHandlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        logHandlers.append(sh)

    logging.basicConfig(level=logging.DEBUG, handlers=logHandlers)

    hmon = health.HealthPublisher(mqtt_client, topic_join(base_topic, "health"))
    sun_scheduler = almanac.SunScheduler(args.location)

    Automate(brokerConnect)
