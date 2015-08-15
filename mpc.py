#!/usr/bin/python
import time
import rtmidi_python as rtmidi
import midiconstants as c
import RPi.GPIO as GPIO
import smbus    # pins GPIO 2 & 3
import logging
import threading
import os.path
import sys

#
# TO ENABLE I2C for the rpi2
# sudo raspi-config
# and enable i2c in advanced options
# then
# sudo nano -w /etc/modules
# i2c-bcm2708
# i2c-dev
# to test we're good....
# sudo i2cdetect -y 1
#
# run via a root crontab on reboot eg.
#
# @reboot        /home/mat/mpc.py 2>&1 > /home/mat/mpc.log
#

SendAutoOff = True
AutoOffSleepMS = 0.1
in_sys_exclusive = False
sysex_buffer = []
my_channel = 1
drum_map = {
    # c0, gpio 1, d-plug 8
    'kick': {'midi_key': 24, 'gpio': 4, 'dplug': 8},
    # d1, gpio 2, d-plug 9
    'snare': {'midi_key': 26, 'gpio': 5, 'dplug': 9},
    # e1, gpio 3, d-plug 5
    'clap': {'midi_key': 28, 'gpio': 7, 'dplug': 5},
    # f1, gpio 4, d-plug 4
    'tom1': {'midi_key': 29, 'gpio': 10, 'dplug': 4},
    # g1, gpio 5, d-plug 2
    'tom2': {'midi_key': 31, 'gpio': 11, 'dplug': 2},
    # a1, gpio 6, d-plug 10
    'tom3': {'midi_key': 33, 'gpio': 15, 'dplug': 10},
    # b1, gpio 7, d-plug 7
    'tom4': {'midi_key': 35, 'gpio': 16, 'dplug': 7},
    # f#1, gpio 8, d-plug 11
    'closed_hat': {'midi_key': 30, 'gpio': 22, 'dplug': 11},
    # g#1, gpio 9, d-plug 12
    'open_hat': {'midi_key': 32, 'gpio': 19, 'dplug': 12},
    # a#1, gpio 10, d-plug 6
    'cymbal': {'midi_key': 34, 'gpio': 21, 'dplug': 6},
    # c1, gpio 11, d-plug 13
    'cymbal_stop': {'midi_key': 36, 'gpio': 22, 'dplug': 13}
}

GPIO.setmode(GPIO.BCM)
midi_in = None
is_dirty = False
initialised = False
lastbuttontime = 0
mybus = smbus.SMBus(1)

debugLevel = logging.INFO
logger = logging.getLogger('mpc')
logger.setLevel(debugLevel)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
ch.setLevel(debugLevel)
logger.addHandler(ch)

def incrementMidiChannel():
    global my_channel, is_dirty
    my_channel += 1
    if ( my_channel > 16 ):
        my_channel = 1
    is_dirty = True
    display(my_channel)

def decrementMidiChannel():
    global my_channel, is_dirty
    my_channel -= 1
    if ( my_channel < 1 ):
        my_channel = 16
    is_dirty = True
    display(my_channel)

def setMidiChannel(channel):
    global my_channel, is_dirty
    if ( my_channel != channel ):
        my_channel = channel
        if ( my_channel < 1 ):
            my_channel = 1
        if ( my_channel > 16 ):
            my_channel = 16
        is_dirty = True
        display(my_channel)

def setDebugLevel(val):
    logger.setLevel(val)
    ch.setLevel(val)

def destroy():
    global initialised, midi_in, is_dirty, my_channel
    raw_display("    ")
    initialised = False
    if ( midi_in != None ):
        midi_in.close_port()
        del midi_in
    GPIO.cleanup()
    if (is_dirty):
        saveConfig()

def saveConfig():
    global my_channel
    logger.info("saving fresh config")
    raw_display("SAUE")
    f = open('mpc.cfg','w')
    f.write(str(my_channel))
    f.close
    time.sleep(0.5)
    is_dirty = False
    display(my_channel)

def auto_off(drum):
    time.sleep(AutoOffSleepMS)
    logger.info("auto_off killing GPIO " + str(drum["gpio"]))
    GPIO.output(drum["gpio"], False)

def callback(message, time_stamp):

    global in_sys_exclusive, initialised, sysex_buffer

    if ( not initialised ):
        return

    if ( logger.isEnabledFor(logging.DEBUG) ):
        message_text = ", ".join(map(str, message))
        logger.debug("received :: (@ " + str(time_stamp) + ") == " + message_text)

    if ( in_sys_exclusive ):
        logger.debug("handling sysex stream")
        if ( message[0] == 0xF7 ):
            logger.info("at the end of the message :: " + str(sysex_buffer))
            in_sys_exclusive = False
        else:
            logger.debug("appending message part :: " + str(message))
            sysex_buffer.append( message )

    #if ( (message[0] - 0x90) == (my_channel - 1) ):
    if ( (message[0] == c.NOTE_ON | (my_channel - 1)) ):
        logger.debug("it's a 'note on' event on our midi channel")

        for drum_key in drum_map:
            if (drum_map[drum_key]["midi_key"] == message[1]):
                logger.info("let's hit the " + drum_key + " on GPIO " + str(drum_map[drum_key]["gpio"]))

                # light up the pin
                GPIO.output(drum_map[drum_key]["gpio"], True)

                # and then do an auto off
                if ( SendAutoOff ):
                    auto_off(drum_map[drum_key])

                break

    elif ( (message[0] == c.NOTE_OFF | (my_channel - 1)) ):
        logger.debug("it's a 'note off' event on our channel")

        for drum_key in drum_map:
            if (drum_map[drum_key]["midi_key"] == message[1]):
                logger.info("let's stop that " + drum_key)
                break

    elif ( message[0] == 0xF2 ):
        logger.debug("song position counter")
        #message[1] = low
        #message[2] = hi

    elif ( message[0] == 0xF8 ):
        logger.debug("ping ... timing message")

    elif ( message[0] == 0xFA ):
        logger.info("song start")

    elif ( message[0] == 0xFB ):
        logger.info("song continue")

    elif ( message[0] == 0xFC ):
        logger.info("song stop")

    elif ( message[0] == 0xFF ):
        logger.info("down tools, it's a reset")

    elif ( message[0] == 0xF0 ):
        logger.debug("potential timecode :: " + str(message))
        #in_sys_exclusive = True
        #sysex_buffer = []

    else:
        logger.debug("unknown message :: " + str(message))

def animate(longString):
    strlen = len(longString) - 4
    for x in range(0, strlen - 1):
        raw_display( longString[x:x+4] )
        time.sleep(0.2)

def display(channel):
    logger.info("midi channel set to :: " + str(channel).zfill(2))
    raw_display("ch" + str(channel).zfill(2))

def raw_display(s):
    global mybus
    for k in '\x76\x79\x00' + s:     # position cursor at 0
        try:
            bus.write_byte(0x71, ord(k))
        except:
            try:
                bus.write_byte(0x71, ord(k))
            except:
                pass
        time.sleep(0.002)

def initialise():
    global my_channel, initialised

    for drum_key in drum_map:
        logger.info("setting pin " + str(drum_map[drum_key]["gpio"]) + " up for output")
        GPIO.setup(drum_map[drum_key]["gpio"], GPIO.OUT)

    logger.info("Searching for Midi in ports ... ")
    midi_in = rtmidi.MidiIn()

    has_ports = False
    for port_name in midi_in.ports:
        logger.info("found port :: " + port_name)
        has_ports = True

    if ( not has_ports ):
        logger.info("No midi in ports found, quitting")
        exit (1)
    else:
        logger.info("Opening first port")
        midi_in.callback = callback
        midi_in.ignore_types(False, False, True)
        midi_in.open_port( 0 )

    if ( os.path.isfile('mpc.cfg') ):
        logger.info("loading settings from mpc.cfg file")
        f = open('mpc.cfg', 'r')
        my_channel = int(f.readline().strip())
        f.close

    # start the buttons probing
    ButtonsThread = threading.Thread(target=Buttons)
    ButtonsThread.daemon = True
    ButtonsThread.start()

    animate("----init----nnidi2nnpc----")
    display( my_channel )
    initialised = True

def Buttons():
    logger.info("setting up hardware buttons")
    GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    global lastbuttontime, initialised
    while True:
        if (initialised):
            now = time.time()
            if ( not GPIO.input(18) and not GPIO.input(17) and (now - lastbuttontime) > 0.2 ):
                logger.info("both buttons pressed, saving")
                lastbuttontime = now
                saveConfig()

            elif ( not GPIO.input(18) and (now - lastbuttontime) > 0.2) :
                logger.info("increment button pressed")
                lastbuttontime = now
                decrementMidiChannel()

            elif ( not GPIO.input(17) and (now - lastbuttontime) > 0.2 ):
                logger.info("decrement button pressed")
                lastbuttontime = now
                incrementMidiChannel()

        if ( time ):
            time.sleep(0.020)

if __name__ == "__main__":

    try:
        print ("initialsing")
        initialise()
        print("running engine ... [ctrl-c to exit]")
        sys.stdout.flush()
        while ( True ):
            if ( time ):
                time.sleep(1)
    except KeyboardInterrupt:
        # quit
        destroy()
        sys.stdout.flush()
        sys.exit()

#--------------------------------------------------------------------------
