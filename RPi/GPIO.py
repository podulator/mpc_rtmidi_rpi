OUT = 0x01
IN = 0x00
BOARD = True
BCM = True
PUD_UP = 1
PUD_DOWN = 2
def setup(pin, direction, pull_up_down=PUD_DOWN):
    return True
def output(pin, value):
    return True
def input(pin):
    return True
def cleanup():
    return True
def setmode(pin_config):
    return True
