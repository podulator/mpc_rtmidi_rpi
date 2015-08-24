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
import serial

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
# also, stop the UART being a serial console
# remove the refernce to ttyAMA0 in /boot/cmdline,txt
#
# edit /boot/config.txt, adding the following lines
# # Change UART clock to 2441000 for MIDI 31250 baud rate
# # As per patch https://www.raspberrypi.org/forums/viewtopic.php?f=29&t=113753&p=801441
# init_uart_clock=2441000
# init_uart_baud=38400
# dtparam=uart0_clkrate=3000000
#
# comment out the following line in /etc/inittab
# T0: 23: respawn: / sbin / getty -L ttyAMA0 115200 vt100

# run via a root crontab on reboot eg.
#
# @reboot        /home/mat/stop_services.sh && /home/mat/mpc.py 2>&1 > /home/mat/mpc.log
#
# thanks to the rpi samplerbox project for hardware pointers on pullups / downs and component list
# http://www.samplerbox.org/
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
    'tom3': {'midi_key': 33, 'gpio': 24, 'dplug': 10},
    # b1, gpio 7, d-plug 7
    'tom4': {'midi_key': 35, 'gpio': 16, 'dplug': 7},
    # f#1, gpio 8, d-plug 11
    'closed_hat': {'midi_key': 30, 'gpio': 22, 'dplug': 11},
    # g#1, gpio 9, d-plug 12
    'open_hat': {'midi_key': 32, 'gpio': 19, 'dplug': 12},
    # a#1, gpio 10, d-plug 6
    'cymbal': {'midi_key': 34, 'gpio': 21, 'dplug': 6},
    # c1, gpio 11, d-plug 13
    'cymbal_stop': {'midi_key': 36, 'gpio': 23, 'dplug': 13}
}

GPIO.setmode(GPIO.BCM)
midi_in = None
ser = None
is_dirty = False
initialised = False
mybus = smbus.SMBus(1)

debugLevel = logging.INFO
logger = logging.getLogger('mpc')
logger.setLevel(debugLevel)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
ch.setLevel(debugLevel)
logger.addHandler(ch)

def setDebugLevel(val):
    logger.setLevel(val)
    ch.setLevel(val)

def incrementMidiChannel():
    global my_channel, is_dirty
    my_channel += 1
    if ( my_channel > 16 ):
        my_channel = 1
    is_dirty = True
    displayChannel( my_channel )

def decrementMidiChannel():
    global my_channel, is_dirty
    my_channel -= 1
    if ( my_channel < 1 ):
        my_channel = 16
    is_dirty = True
    displayChannel( my_channel )

def setMidiChannel(channel):
    global my_channel, is_dirty
    if ( my_channel != channel ):
        my_channel = channel
        if ( my_channel < 1 ):
            my_channel = 1
        if ( my_channel > 16 ):
            my_channel = 16
        is_dirty = True
        displayChannel( my_channel )

def saveConfig():
    global my_channel
    logger.info( "saving fresh config" )
    raw_display( "SAUE" )
    f = open( 'mpc.cfg','w' )
    f.write( str(my_channel) )
    f.close
    is_dirty = False
    time.sleep(0.5)
    displayChannel( my_channel )

def animate(longString):
    logger.info( "writing :: " + longString )
    strlen = len(longString) - 4
    clearDisplay()
    for x in range(0, strlen - 1):
        if ( raw_display( longString[x:x+4] ) ):
            # only sleep if there's really a display there
            time.sleep(0.2)

def displayChannel(channel):
    logger.info( "midi channel set to :: " + str(channel).zfill(2) )
    raw_display( "CH" + str(channel).zfill(2) )

def clearDisplay():
    global mybus
    try:
        mybus.write_byte(0x71, 0x76)
    except:
        pass

def raw_display(s):
    global mybus
    success = True
    try:
        # position cursor at 0, append the string
        for k in '\x79\x00' + s:
            try:
                # 0x71 is the hardware address of the lcd
                mybus.write_byte(0x71, ord(k))
            except:
                try:
                    mybus.write_byte(0x71, ord(k))
                except:
                    success = False
    except:
        success = False
    return success


def callback(message, time_stamp):

    global in_sys_exclusive, initialised, sysex_buffer

    if ( not initialised ):
        return

    if ( logger.isEnabledFor(logging.DEBUG) ):
        message_text = ", ".join(map(str, message))
        logger.debug( "received :: (@ " + str(time_stamp) + ") == " + message_text )

    if ( in_sys_exclusive ):
        logger.debug( "handling sysex stream" )
        if ( message[0] == 0xF7 ):
            logger.info( "at the end of the sysex message :: " + str(sysex_buffer) )
            in_sys_exclusive = False
        else:
            logger.debug( "appending message part :: " + str(message) )
            sysex_buffer.append( message )

    #if ( (message[0] - 0x90) == (my_channel - 1) ):
    if ( (message[0] == c.NOTE_ON | (my_channel - 1)) ):
        logger.debug( "it's a 'note on' event on our midi channel" )

        for drum_key in drum_map:
            if ( drum_map[drum_key]["midi_key"] == message[1] ):
                logger.info( "let's hit the " + drum_key + " on GPIO " + str(drum_map[drum_key]["gpio"]) )

                # light up the pin
                GPIO.output( drum_map[drum_key]["gpio"], True )

                # and then do an auto off
                if ( SendAutoOff ):
                    auto_off(drum_map[drum_key])

                break

    elif ( (message[0] == c.NOTE_OFF | (my_channel - 1)) ):
        logger.debug( "it's a 'note off' event on our channel" )

        if (not SendAutoOff):
            for drum_key in drum_map:
                if ( drum_map[drum_key]["midi_key"] == message[1] ):
                    logger.info( "let's stop that " + drum_key )
                    GPIO.output( drum_map[drum_key]["gpio"], False )
                    break

    elif ( message[0] == 0xF2 ):
        logger.debug( "song position counter" )
        #message[1] = low
        #message[2] = hi

    elif ( message[0] == 0xF8 ):
        logger.debug( "ping ... timing message" )

    elif ( message[0] == 0xFA ):
        logger.info( "song start" )

    elif ( message[0] == 0xFB ):
        logger.info( "song continue" )

    elif ( message[0] == 0xFC ):
        logger.info( "song stop" )

    elif ( message[0] == 0xFF ):
        logger.info( "down tools, it's a reset" )

    elif ( message[0] == 0xF0 ):
        logger.debug( "potential timecode :: " + str(message) )
        #in_sys_exclusive = True
        #sysex_buffer = []

    else:
        logger.info( "unknown message :: " + str(message) )

def auto_off(drum):
    time.sleep(AutoOffSleepMS)
    logger.info( "auto_off killing GPIO " + str(drum["gpio"]) )
    GPIO.output(drum["gpio"], False)

def initialise():
    global ser, my_channel, initialised
    # did we find any serial or usb midi ports at all
    has_ports = False

    logger.info("setting up mpc mappings")
    for drum_key in drum_map:
        logger.info("setting pin " + str(drum_map[drum_key]["gpio"]) + " up for output")
        GPIO.setup(drum_map[drum_key]["gpio"], GPIO.OUT)

    logger.info("checking for rpi serial port on /dev/ttyAMA0")
    try:
        ser = serial.Serial('/dev/ttyAMA0', baudrate=38400)
        logger.info("claimed port " + str(ser.port) + " @ baudrate " + str(ser.baudrate))
        logger.info("starting serial midi thread")
        MidiThread = threading.Thread( target=MidiSerialCallback )
        MidiThread.daemon = True
        MidiThread.start()
        has_ports = True
    except:
        logger.info("serial port not found, this ain't a rpi, skipping")

    logger.info("searching for alt USB Midi in ports ... ")
    midi_in = rtmidi.MidiIn()
    midi_in.callback = callback
    # skip any of sysex, time and sensitivity aka. aftertouch
    midi_in.ignore_types(True, True, True)

    for port in midi_in.ports:
        if 'Midi Through' not in port:
            logger.info("opening port :: " + port)
            midi_in.open_port(port)
            has_ports = True

    if ( not has_ports ):
        logger.error("no midi in ports found, quitting")
        destroy()
        exit (1)

    if ( os.path.isfile('mpc.cfg') ):
        logger.info("loading settings from mpc.cfg file")
        f = open('mpc.cfg', 'r')
        my_channel = int(f.readline().strip())
        f.close

    # start the buttons probing
    ButtonsThread = threading.Thread(target=Buttons)
    ButtonsThread.daemon = True
    ButtonsThread.start()

    animate("    ----InIt----nnIDI-2-nnPC----    ")
    displayChannel( my_channel )
    initialised = True

def shutdown():
    animate("----pouuering off----")
    destroy()
    raw_display('    ')
    os.system("halt")

def destroy():
    global initialised, midi_in
    raw_display("....")
    initialised = False
    if ( midi_in != None ):
        midi_in.close_port()
        del midi_in
    GPIO.cleanup()

def Buttons():
    logger.info("setting up hardware buttons")
    GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    global initialised, is_dirty
    lastButtonTime = 0
    longPressTime = 0
    while True:
        if (initialised):
            now = time.time()
            if ( not GPIO.input(18) and not GPIO.input(17) and (now - lastButtonTime) > 0.2 ):
                logger.info("both buttons pressed")
                lastButtonTime = now
                # cache the start of the dbl button press
                if ( longPressTime == 0 ):
                    longPressTime = now
                    logger.debug( "capturing longPressTime as :: " + str(longPressTime) )
                else:
                    logger.debug( "now - longPressTime = " + str( now - longPressTime) )
                    if ( (now - longPressTime > 1 and now - longPressTime < 2) and is_dirty ):
                        logger.info("saving")
                        saveConfig()
                    elif ( now - longPressTime > 5 ):
                        logger.info("shutting down")
                        shutdown()

            elif ( not GPIO.input(17) and (now - lastButtonTime) > 0.5) :
                longPressTime = 0
                logger.info("increment button pressed")
                lastButtonTime = now
                incrementMidiChannel()

            elif ( not GPIO.input(18) and (now - lastButtonTime) > 0.5 ):
                longPressTime = 0
                logger.info("decrement button pressed")
                lastButtonTime = now
                decrementMidiChannel()
            else:
                logger.debug("no button pressed")
                longPressTime = 0

        if ( time ):
            time.sleep(0.2)

def MidiSerialCallback():
    if ( ser == None ):
        return

    message = [0, 0, 0]
    while True:
        i = 0
        while i < 3:
            # read a byte
            data = ord(ser.read(1))
            if data >> 7 != 0:
                # status byte!
                # this is the beginning of a midi message:
                # http://www.midi.org/techspecs/midimessages.php
                i = 0
            message[i] = data
            i += 1
            # program change: don't wait for a third byte: it has only 2 bytes
            if i == 2 and message[0] >> 4 == 12:
                message[2] = 0
                i = 3
        MidiCallback(message, None)

if __name__ == "__main__":

    try:
        print ("initialising")
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
