#!/bin/bash

## Taken from http://wiki.linuxaudio.org/wiki/raspberrypi

/bin/sleep 5

## Stop the ntp service
service ntp stop

## Stop the triggerhappy service
service triggerhappy stop

## Stop the dbus service. Warning: this can cause unpredictable behaviour when running a desktop environment on the RPi
service dbus stop

## Stop the console-kit-daemon service. Warning: this can cause unpredictable behaviour when running a desktop environment on the RPi
killall console-kit-daemon

## Stop the polkitd service. Warning: this can cause unpredictable behaviour when running a desktop environment on the RPi
killall polkitd

## Remount /dev/shm to prevent memory allocation errors
mount -o remount,size=128M /dev/shm

## Kill the usespace gnome virtual filesystem daemon. Warning: this can cause unpredictable behaviour when running a desktop environment on the RPi
killall gvfsd

## Kill the userspace D-Bus daemon. Warning: this can cause unpredictable behaviour when running a desktop environment on the RPi
killall dbus-daemon

## Kill the userspace dbus-launch daemon. Warning: this can cause unpredictable behaviour when running a desktop environment on the RPi
killall dbus-launch

## Uncomment if you'd like to disable the network adapter completely
#echo -n “1-1.1:1.0” | tee /sys/bus/usb/drivers/smsc95xx/unbind
## In case the above line doesn't work try the following
#echo -n “1-1.1” | tee /sys/bus/usb/drivers/usb/unbind

# to totally remove networking uncomment these guys
# service ifplugd stop
# killall ifplugd
# service networking stop

# setup the correct baud rate for MIDI
stty -F /dev/ttyAMA0 38400

exit 0
