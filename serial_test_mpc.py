#!/usr/bin/python

import time
import sys
import logging
import serial

ser = serial.Serial('/dev/ttyAMA0', baudrate=38400)

try:
    print("running pattern ... [ctrl-c to exit]")
    data = [0x91, 24, 0x40]
    while (True):
        ser.write(data)
        ser.flushOutput()
        time.sleep(0.25)
except KeyboardInterrupt:
    # quit
    sys.exit()
