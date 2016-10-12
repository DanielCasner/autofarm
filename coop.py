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
import candle
import door
import lights
import thermostat

mqtt_client = None
logger = logging.getLogger(__name__)

def MQTTConnected(client, userdata, flags, rc):
    "Callback for MQTT connection events"
    pass

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
