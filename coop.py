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
import astral

DOOR_OPEN_SW     = 
DOOR_CLOSED_SW   = 
EXTERIOR_LIGHTS  = (4 + PCA9685Pi.EXTENDER_OFFSET,
                    5 + PCA9685Pi.EXTENDER_OFFSET,
                    6 + PCA9685Pi.EXTENDER_OFFSET)
HEN_HOUSE_LIGHT  =  7 + PCA9685Pi.EXTENDER_OFFSET
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
    debug_LEDs = (lights.Light(pi, [DEBUG_LED1], [PCA9685Pi.MAX_PWM]), lights.Light(pi, [DEBUG_LED2], [PCA9685Pi.MAX_PWM]))

class SharedClient(mqtt.Client):
    "MQTT client set up for shared use"
    
    class Subscription(list):
        "A list of callbacks that also has a stored QOS and topic"
        def __init__(self, topic, qos, callbacks=[]):
            list.__init__(callbacks)
            self.topic = topic
            self.qos = qos
    
    def __init__(self, *args, **kwargs):
        "Initalize client"
        mqtt.Client.__init__(self, *args, **kwargs)
        self._connected = False
        self._subscriptions = {}
    
    def subscribe(self, topic, qos, callback):
        "Subscribe to a given topic with callback"
        needToSubscribe = True
        if topic in self._subscriptions:
            sub = self._subscriptions[topic]
            if qos > sub.qos:
                mqtt.Client.unsubscribe(topic)
                sub.qos = qos
            else:
                needToSubscribe = False
            sub.append(callback)
        else:
            self._subscriptions[topic] = Subscription(topic, qos, [callback])
        if self._connected and needToSubscribe:
            sub = self._subscriptions[topic]
            mqtt.Client.subscribe(self, sub.topic, sub.qos)
    
    def unsubscribe(self, topic, callback):
        "Unsubscribe a single callback"
        self._subscriptions[topic].remove(callback)
        if len(self._subscriptions[topic]) == 0:
            mqtt.Client.unsubscribe(self, topic)
            del self._subscriptions[topic]
    
    def on_connect(self, client, userdata, flags, rc):
        "Callback on MQTT connection"
        self._connected = True
        if len(self._subscriptions):
            mqtt.Client.subscribe([(s.topic, s.qos) for s in self._subscriptions.values()])
        
    def on_disconnect(self, client, userdata, rc):
        self._connected = False
        
    def on_message(self, client, userdata, msg):
        "Callback on MQTT message"
        for cb in self._subscriptions[msg.topic]:
            cb(msg)

def Automate(mqtt_connect_args):
    "Run the automation main loop"
    logger.debug("Starting MQTT client thread")
    mqtt_client.loop_start() # Start MQTT client in its own thread
    mqtt_client.connect(*mqtt_connect_args)
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
    parser.add_argument('-t', "--topic", type=str, default="coop", help="Base MQTT topic")
    parser.add_argument("location", type=argparse.FileType('rb'), help="Pickle file containing an Astral location instance for almanac")
    args = parser.parse_args()
    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)

    global base_topic
    base_topic = args.topic
    
    global location
    location = pickle.load(args.location)

    mqtt_client = SharedClient(args.clientID, not args.clientID)

    Automate(mqtt_connect_args)
