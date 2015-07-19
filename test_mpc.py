#!/usr/bin/python

import time
import sys
import mpc as mpc
import logging

mpc.setDebugLevel(logging.INFO)
mpc.initialise()

pattern = [
            [ mpc.drum_map["kick"], mpc.drum_map["cymbal"] ],
            [ mpc.drum_map["cymbal_stop"] ],
            [ mpc.drum_map["snare"] ],
            [],
            [ mpc.drum_map["kick"] ],
            [],
            [ mpc.drum_map["kick"] ],
            [ mpc.drum_map["snare"] ]
]

try:
    print("running pattern ... [ctrl-z to exit]")
    while (1):
        for step in pattern:
            for instrument in step:
                #print type(instrument)
                # callback the note on channel 2 at 64 velocity
                note = instrument["midi_key"]#.values()[1]
                mpc.callback([0x91, note, 0x40], int(round(time.time() * 1000)))
            time.sleep(0.25)
except KeyboardInterrupt:
    # quit
    mpc.destroy
    sys.exit()
