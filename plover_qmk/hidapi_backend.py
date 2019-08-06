# -*- coding: utf-8 -*-
# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

# TODO: add tests

"Thread-based monitoring of a QMK-based stenotype machine, hidapi backend"

from time import sleep

import hid

from plover import log
from plover.machine.base import ThreadedStenotypeBase

# This matches up with the key definitions in qmk (keymap_steno.h)
STENO_KEY_CHART = ("Fn", "#1", "#2", "#3", "#4", "#5", "#6", "S1-",
                   "S2-", "T-", "K-", "P-", "W-", "H-", "R-", "A-",
                   "O-", "*1", "*2", "res1", "res2", "pwr", "*3", "*4",
                   "-E", "-U", "-F", "-R", "-P", "-B", "-L", "-G",
                   "-T", "-S", "-D", "#7", "#8", "#9", "#A", "#B",
                   "#C", "-Z")
PACKET_LENGTH = 6

def packet_to_stroke(p):
    keys = []
    for byte_index, byte in enumerate(p):
        for bit_index in range(8):

            key_index = byte_index * 8 + bit_index
            if key_index < len(STENO_KEY_CHART):
                if byte & (1 << bit_index):
                    keys.append(STENO_KEY_CHART[key_index])
    return keys

VENDOR_ID = 0xfeed
PRODUCT_ID = 0x1337
USAGE_PAGE = 0xff02
USAGE = 1

EMPTY = [0] * PACKET_LENGTH

class DataHandler(object):

    def __init__(self, callback):
        self._callback = callback
        self._pressed = EMPTY

    def update(self, p):
        if p == EMPTY and self._pressed != EMPTY:
            stroke = packet_to_stroke(self._pressed)
            if stroke:
                self._callback(stroke)
            self._pressed = EMPTY
        else:
            self._pressed = [x[0] | x[1] for x in zip(self._pressed, p)]


class QMK(ThreadedStenotypeBase):

    KEYS_LAYOUT = '''
        #1 #2  #3 #4 #5 #6 #7 #8 #9 #A #B #C
        Fn S1- T- P- H- *1 *3 -F -P -L -T -D
           S2- K- W- R- *2 *4 -R -B -G -S -Z
                  A- O-       -E -U
        pwr
        res1
        res2
    '''
    KEYMAP_MACHINE_TYPE = 'Gemini PR'

    def __init__(self, params):
        super(QMK, self).__init__()
        self._machine = None

    def _on_stroke(self, keys):
        steno_keys = self.keymap.keys_to_actions(keys)
        if steno_keys:
            self._notify(steno_keys)

    # this will continuously poll for devices,
    # just like _reconnect used to do
    def _connect(self):

        connected = False
        self._machine = None
        self._initializing()

        while not self.finished.isSet() and not connected:

            # scan connected qmk devices
            # getting hotplug notifications would be awesome, but this
            # is kind of hard to do cross-platform and hidapi doesn't
            # support it.
            interface_path = None
            for device in hid.enumerate(VENDOR_ID, PRODUCT_ID):
                # TESTING only; usage_page and usage do not work on linux, so I'm
                # hardcoding the interface
                #if device["interface_number"] == 0:
                if device["usage_page"] == USAGE_PAGE and device["usage"] == USAGE:
                    # This is the steno interface!
                    interface_path = device["path"]
                    break

            if interface_path:
                try:
                    if hasattr(hid.device, 'open'):
                        self._machine = hid.device()
                        self._machine.open_path(interface_path)
                    # ? i have no idea why you need this, or how you'd adapt it
                    # to take a path
                    #else:
                    #    self._machine = hid.device(VENDOR_ID, product_id)
                except IOError:
                    self._machine = None
                    log.warning("Opening the machine interface failed. Retrying")
                else:
                    self._machine.set_nonblocking(0)
                    self._ready()
                    connected = True
                    break

            sleep(1)

        if connected:
            self._ready()

        return connected

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        super(QMK, self).start_capture()

    def run(self):
        # connect in run, since that's waiting for the device now
        if not self._connect():
            return
        
        handler = DataHandler(self._on_stroke)
        while not self.finished.isSet():
            try:
                packet = self._machine.read(PACKET_LENGTH, 100)
            except IOError:
                self._machine.close()
                log.warning(u'machine disconnected, reconnecting…')
                if self._connect():
                    log.warning('machine reconnected.')
            else:
                if len(packet) == PACKET_LENGTH:
                    handler.update(packet)

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        super(QMK, self).stop_capture()
        if self._machine:
            self._machine.close()
        self._stopped()
