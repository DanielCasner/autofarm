#!/usr/bin/env python3
"""
A subclass of mqtt client which supports subscriptions going to multiple different callbacks. The purpose is to allow
a complex program to share one MQTT client among a number of destinct functions or even separate modules.
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import paho.mqtt.client as mqtt

def topic_join(*args):
    "Returns the tokens specified jouint by the MQTT topic namespace separatot"
    return "/".join(args)

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
                mqtt.Client.unsubscribe(self, topic)
                sub.qos = qos
            else:
                needToSubscribe = False
            sub.append(callback)
        else:
            self._subscriptions[topic] = self.Subscription(topic, qos, [callback])
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
            mqtt.Client.subscribe(self, [(s.topic, s.qos) for s in self._subscriptions.values()])
        
    def on_disconnect(self, client, userdata, rc):
        self._connected = False
        
    def on_message(self, client, userdata, msg):
        "Callback on MQTT message"
        for cb in self._subscriptions[msg.topic]:
            cb(msg)
