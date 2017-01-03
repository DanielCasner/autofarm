#!/usr/bin/env python3
"""Logging handler using MQTT Shared Client."""
__author__ = "Daniel Casner <www.danielcasner.org>"
import sharedclient
import logging

class MQTTHandler(logging.Handler):
    """A logging handler which broadcasts records over MQTT"""
    
    def __init__(self, client, topic, qos=2):
        logging.Handler.__init__(self)
        self.client = client
        self.def_topic = topic
        self.def_qos   = qos
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.client.publish(self.def_topic, msg, qos=self.def_qos, retain=False)
            self.flush()
        except Exception:
            self.handleError(record)
