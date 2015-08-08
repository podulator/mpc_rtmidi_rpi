#!/usr/bin/python
import time
import rtmidi_python as rtmidi
import midiconstants as c
import RPi.GPIO as GPIO
import logging
import threading

SendAutoOff = True
AutoOffSleepMS = 0.1
USE_I2C_7SEGMENTDISPLAY = True  # pins GPIO 2 & 3
USE_HARDWARE_BUTTONS = True # pins GPIO 17 & 18
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
    'closed_hat': {'midi_key': 30, 'gpio': 18, 'dplug': 11},
    # g#1, gpio 9, d-plug 12
    'open_hat': {'midi_key': 32, 'gpio': 19, 'dplug': 12},
    # a#1, gpio 10, d-plug 6
    'cymbal': {'midi_key': 34, 'gpio': 21, 'dplug': 6},
    # c1, gpio 11, d-plug 13
    'cymbal_stop': {'midi_key': 36, 'gpio': 22, 'dplug': 13}
}

midi_in = None
debugLevel = logging.ERROR
logger = logging.getLogger('mpc')
logger.setLevel(debugLevel)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(debugLevel)
logger.addHandler(ch)

def incrementMidiChannel():
    global my_channel
    my_channel += 1
    if (my_channel > 16):
        my_channel = 1
    display(my_channel)

def decrementMidiChannel():
    global my_channel
    my_channel -= 1
    if (my_channel < 1):
        my_channel = 16
    display(my_channel)

def setDebugLevel(val):
    logger.setLevel(val)
    ch.setLevel(val)

def destroy():
    global midi_in
    if (midi_in != None):
        midi_in.close_port()
        del midi_in
    GPIO.cleanup()

def auto_off(drum):
    time.sleep(AutoOffSleepMS)
    logger.info("auto_off killing GPIO " + str(drum["gpio"]))
    GPIO.output(drum["gpio"], False)

def callback(message, time_stamp):

    global in_sys_exclusive
    global sysex_buffer

    if logger.isEnabledFor(logging.DEBUG):
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

if USE_HARDWARE_BUTTONS:
    # thanks to rpi samplerbox project for this
    # https://github.com/josephernest/SamplerBox/blob/master/samplerbox.py
    def Buttons():
        GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        global lastbuttontime
        while True:
            now = time.time()
            if not GPIO.input(18) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                decrementMidiChannel()

            elif not GPIO.input(17) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                incrementMidiChannel()

            time.sleep(0.020)

    ButtonsThread = threading.Thread(target=Buttons)
    ButtonsThread.daemon = True
    ButtonsThread.start()

if USE_I2C_7SEGMENTDISPLAY:
    # thanks to rpi samplerbox project for this
    # https://github.com/josephernest/SamplerBox/blob/master/samplerbox.py
    import smbus

    bus = smbus.SMBus(1)     # using I2C

    def display(channel):
        logger.info("midi channel set to :: " + str(channel))
        raw_display("ch" + str(channel))

    def raw_display(s):
        for k in '\x76\x79\x00' + s:     # position cursor at 0
            try:
                bus.write_byte(0x71, ord(k))
            except:
                try:
                    bus.write_byte(0x71, ord(k))
                except:
                    pass
            time.sleep(0.002)

    raw_display('----')
    time.sleep(0.5)

else:

    def display(channel):
        logger.info("midi channel set to :: " + str(channel))
        pass

def initialise():
    global my_channel

    GPIO.setmode(GPIO.BCM)
    for drum_key in drum_map:
        logger.info("setting pin " + str(drum_map[drum_key]["gpio"]) + " up for output")
        GPIO.setup(drum_map[drum_key]["gpio"], GPIO.OUT)

    logger.info("Searching for Midi in ports ... ")
    midi_in = rtmidi.MidiIn()

    has_ports = False
    for port_name in midi_in.ports:
        logger.info("found port :: " + port_name)
        has_ports = True

    if (not has_ports):
        logger.info("No midi in ports found, quitting")
        exit (1)
    else:
        logger.info("Opening first port")
        midi_in.callback = callback
        midi_in.ignore_types(False, False, True)
        midi_in.open_port( 0 )

    display(my_channel)

#print drum_map

if __name__ == "__main__":

    try:
        initialise()
        raw_input("running....[press enter to exit]")
    finally:
        print("exiting")
        destroy()

#--------------------------------------------------------------------------
