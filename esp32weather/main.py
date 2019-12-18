#!/usr/bin/env python3
"""
Micropython application for ESP32Thing based weather station.
"""
import machine
import sys
import utime

BUTTON = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
LED = machine.Pin(5, machine.Pin.OUT)
LED.value(0)  # LED off by default

SENSOR_UV_EN = machine.Pin(18, machine.Pin.OUT)
SENSOR_UV_ADC = machine.ADC(machine.Pin(36))

while BUTTON.value():  # Continue until button pressed
    pass

print("Droping to REPL")
LED.value(1)  # Set LED on the way to the REPL
