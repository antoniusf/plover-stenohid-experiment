# -*- coding: utf-8 -*-
# Copyright (c) 2013 Hesky Fisher
# Copyright (c) 2019 Antonius Frie: Rewrite for use with the hiddev interface, modify protocol format.
# See LICENSE.txt for details.

# TODO: add tests

"Thread-based monitoring of a QMK-based stenotype machine, linux hiddev backend."

from time import sleep

import pyudev
import os
import select
import struct

from .find_dev import wait_for_device

from plover import log
from plover.machine.base import ThreadedStenotypeBase

STENO_KEY_CHART = ("Fn", "#1", "#2", "#3", "#4", "#5", "#6", "S1-",
                   "S2-", "T-", "K-", "P-", "W-", "H-", "R-", "A-",
                   "O-", "*1", "*2", "res1", "res2", "pwr", "*3", "*4",
                   "-E", "-U", "-F", "-R", "-P", "-B", "-L", "-G",
                   "-T", "-S", "-D", "#7", "#8", "#9", "#A", "#B",
                   "#C", "-Z")

packet_struct = struct.Struct("Ii")

def parse_packet(packet):
    usage, value = packet_struct.unpack(packet)

    usage_page = usage >> 16
    usage = usage & 0xFF

    assert usage_page == 0xff02 # TODO: this probably shouldn't be an assert (and we should check the usage range, too)
    key_index = usage - 8 # (usages start at 8, compare usb_descriptor.c in QMK)
    return key_index, value

# 0xFEED is for qmk
VENDOR_IDS = [0xFEED]

EMPTY = [0] * 6

class DataHandler(object):

    def __init__(self, callback):
        self._callback = callback
        # current state of the keyboard
        self._pressed = set()
        # accumulated state of the keyboard
        self._stroke = set()

    def update(self, p):
        key_index, value = parse_packet(p)

        if value == 1:
            self._pressed.add(key_index)
            self._stroke.add(key_index)

        elif value == 0:
            self._pressed.discard(key_index)

            if self._pressed == set() and self._stroke != set():
                # all keys are up, process stroke
                stroke = [STENO_KEY_CHART[idx] for idx in sorted(self._stroke)]
                self._callback(stroke)

                # clear accumulated state
                self._stroke.clear()


class QMK(ThreadedStenotypeBase):

    # key layout copied from gemini pr, it is the exact same
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
        self.finished_notify_recv = self.finished_notify_send = None

    def _on_stroke(self, keys):
        steno_keys = self.keymap.keys_to_actions(keys)
        if steno_keys:
            self._notify(steno_keys)

    def _connect(self):
        connected = False
        self._initializing()
        device = wait_for_device(self.finished_notify_recv)

        if device:
            self._machine = device
            self._ready()

        return connected

    #def _reconnect(self):
    #    self._machine = None
    #    self._initializing()

    #    connected = self._connect()
    #    # Reconnect loop
    #    while not self.finished.isSet() and not connected:
    #        sleep(0.5)
    #        connected = self._connect()
    #    return connected

    def run(self):
        handler = DataHandler(self._on_stroke)

        self._connect()

        while not self.finished.isSet():
            ready, _, _ = select.select([self._machine, self.finished_notify_recv], [], [])
            # (if this is not true, we got pulled out by self.finished_notify_recv. on the next run self.finished.isSet() will be false and break the loop.)
            if self._machine in ready:

                try:
                        # 4 bytes usage, 4 bytes status (hiddev format)
                        # we need to use os.read here, because buffering and select do not play well together
                        packet = os.read(self._machine, 8)
                except IOError:
                    os.close(self._machine)
                    log.warning(u'machine disconnected, reconnecting…')
                    if self._connect():
                        pass
                        log.warning('machine reconnected.')
                else:
                    handler.update(packet)

    def start_capture(self):
        """Begin listening for output from the stenotype machine."""
        self.finished_notify_recv, self.finished_notify_send = os.pipe()
        super(QMK, self).start_capture()

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        if self.finished_notify_recv:
            os.write(self.finished_notify_send, b"0")

        super(QMK, self).stop_capture()

        if self.finished_notify_recv:
            os.close(self.finished_notify_recv)
            os.close(self.finished_notify_send)
            self.finished_notify_recv = None
            self.finished_notify_send = None

        if self._machine:
            os.close(self._machine)
            self._machine = None

        self._stopped()
