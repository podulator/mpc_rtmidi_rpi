#!/usr/bin/python

import time
import sys
import mpc as mpc
import logging
import random

mpc.setDebugLevel(logging.INFO)
mpc.initialise()
mpc.setMidiChannel(1)
mpc.incrementMidiChannel()

pattern = [
            [ mpc.drum_map["kick"], mpc.drum_map["cymbal"] ],
            [ mpc.drum_map["closed_hat"] ],
            [ mpc.drum_map["snare"] ],
            [],
            [ mpc.drum_map["kick"] ],
            [ mpc.drum_map["open_hat"] ],
            [ mpc.drum_map["kick"] ],
            [ mpc.drum_map["snare"] ]
]

try:
    print("running pattern ... [ctrl-c to exit]")
    while (True):
        for step in pattern:
            for instrument in step:
                #print type(instrument)
                # callback the note on channel 2 at 64 velocity
                note = instrument["midi_key"]#.values()[1]
                velocity = random.randint(40, 127)
                mpc.MidiCallback([0x91, note, velocity], int(round(time.time() * 1000)))
            time.sleep(0.25)
except KeyboardInterrupt:
    # quit
    mpc.destroy()
    sys.exit()
