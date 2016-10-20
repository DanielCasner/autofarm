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
import paho.mqtt.client as mqtt
from PCA9685_pigpio import *
from door import Door
from thermostat import Thermostat
import candle
import lights
import health

BASE_TOPIC = "coop"

DOOR_OPEN_SW     = 
DOOR_CLOSED_SW   = 
BROODER_HEATER   =  8 + PCA9685Pi.EXTENDER_OFFSET
BROODER_COOLER   =  9 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_HEATER = 10 + PCA9685Pi.EXTENDER_OFFSET
HEN_HOUSE_COOLER = 11 + PCA9685Pi.EXTENDER_OFFSET
DOOR_MOT_IN2     = 12 + PCA9685Pi.EXTENDER_OFFSET
DOOR_MOT_IN1     = 13 + PCA9685Pi.EXTENDER_OFFSET
DEBUG_LED1       = 14 + PCA9685Pi.EXTENDER_OFFSET
DEBUG_LED2       = 15 + PCA9685Pi.EXTENDER_OFFSET

# Mains dimmers run backwards
DIMMER_MAX_PWM = 0
DIMMER_MIN_PWM = 4096

THERMOSTAT_PID = (1.0, 0.0, 0.0, 1.0)

mqtt_client = None
logger = logging.getLogger(__name__)
hmon   = health.HealthMonitor()

def topic_join(*args):
    "Returns the tokens specified jouint by the MQTT topic namespace separatot"
    return "/".join(args)

def InitalizeHardware():
    # Set up pigpio interface
    global pi
    pi = PCA9685Pi()
    pi.set_PWM_frequency(PCA9685Pi.EXTENDER_OFFSET, 28000) # Required for Fan control, should be okay for everything else
    # Debugging LEDs
    global debug_LEDs
    debug_LEDs = (lights.Light(pi, DEBUG_LED1, [255]), lights.Light(pi, DEBUG_LED2, [255]))
    # Hen house door control
    global hen_house_door
    hen_house_door = Door(DOOR_MOT_IN1, DOOR_MOT_IN2, DOOR_OPEN_SW, DOOR_CLOSED_SW, mqtt_client, topic_join(BASE_TOPIC, "hen_door"))
    # Setup the hen house temperature controller
    global hen_house_thermostat
    hen_house_thermostat = Thermostat(
        lights.Dimmer(pi, HEN_HOUSE_HEATER, DIMMER_MIN_PWM, DIMMER_MAX_PWM, 0)
        lights.Dimmer(pi, HEN_HOUSE_COOLER, 0, 4096, 1)
        *THERMOSTAT_PID
    )
    # Setup the boorder temperature controller
    global booder_thermostat
    booder_thermostat = Thermostat(
        lights.Dimmer(pi, BROODER_HEATER, DIMMER_MIN_PWM, DIMMER_MAX_PWM, 0)
        lights.Dimmer(pi, BROODER_COOLER, 0, 4096, 1)
        *THERMOSTAT_PID
    )
    

def MQTTConnected(client, userdata, flags, rc):
    "Callback for MQTT connection events"
    client.subscribe

def MQTTMessage(client, userdata, msg):
    "Callback for MQTT data received"
    pass

def Automate(mqtt_connect_args):
    "Run the automation main loop"
    mqtt_client.on_connect = MQTTConnected
    mqtt_client.on_message = MQTTMessage
    logger.debug("Starting MQTT client thread")
    mqtt_client.loop_start() # Start MQTT client in its own thread
    logger.debug("Entering main loop")
    try:
        while True:
            # Do main loop
            time.sleep(1)
    except KeyboardInterrupt:
        logger.debug("Exiting at sig-exit")
    # Clean up peripherals
    mqtt_client.loop_stop()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("-i", "--clientID", type=str, default="", help="MQTT client ID for the counter node")
    parser.add_argument("-b", "--brokerHost", type=str, default="localhost", help="MQTT Broker hostname or IP address")
    parser.add_argument('-p', "--brokerPort", type=int, help="MQTT Broker port")
    parser.add_argument('-k', "--brokerKeepAlive", type=int, help="MQTT keep alive seconds")
    parser.add_argument('-n', "--bind", type=str, help="Local interface to bind to for connection to broker")
    args = parser.parse_args()
    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)

    mqtt_client = mqtt.Client(args.clientID, not args.clientID)
    
    Automate(mqtt_connect_args)
