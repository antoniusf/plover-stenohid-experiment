import pyudev
import select
import time
import os

from plover import log

from . import hiddev

ctx = pyudev.Context()

# TODO: make all lookups get()s, because apparently these attributes can disappear sometimes

def check_device(device):
    """Checks if a given hiddev device belongs to a stenoHID interface. If yes, it
    returns the opened device file descriptor. Otherwise, returns None.
    """

    # check that it's actually an hid device
    log.debug("checking device...")
    log.debug("checking if it's an hid...")
    interface = device.find_parent(subsystem="usb", device_type="usb_interface")

    # this can happen if the device is unplugged in between
    if interface is None:
        log.debug("error (device unplugged)")
        return False
    
    if interface["DRIVER"] != "usbhid":
        log.debug("no")
        return False

    log.debug("... yes")

    # check the vendor and product IDs
    log.debug("checking if vendor and product IDs match...")
    usb_device = interface.find_parent(subsystem="usb", device_type="usb_device")

    if usb_device is None:
        log.debug("error (device unplugged)")
        return False
    
    if not usb_device or usb_device["ID_VENDOR_ID"] != "feed" or usb_device["ID_MODEL_ID"] != "1337":
        log.debug("no (device IDs were 0x{}, 0x{})".format(usb_device["ID_VENDOR_ID"], usb_device["ID_MODEL_ID"]))
        return False

    log.debug("... yes")

    log.debug("checking if it has the correct usage...")

    fname = device["DEVNAME"]

    # check the application usage page
    # we have to actually open the device for this
    # (we'll only check collection 0)
    try:
        fd = os.open(fname, os.O_RDONLY)
    except FileNotFoundError:
        log.debug("error (device unplugged)")
        return None

    try:
        info = hiddev.hiddev_collection_info()
        info.get_info(fd, index=0)
    # OSError can be thrown by the ioctl inside of info.get_info
    except OSError:
        # close the fd in this case
        # we can't use a `finally` for this, because if everything works, we need to return the opened fd, and the finally
        # would get in the way of that.
        os.close(fd)
        log.debug("error (device unplugged)")
        return None

    log.debug("... usage is 0x{:04x}".format(info.usage))

    if info.usage != 0xff020001:
        os.close(fd)
        log.debug("... no")
        return None

    log.debug("... yes")
    return fd

def find_devices():

    # usbmisc is where the hiddev devices appear to sit
    for device in ctx.list_devices(subsystem="usbmisc"):

        device_fd = check_device(device)
        if device_fd:
            # we've found our device!
            return device_fd

    # we've found nothing...
    return None

def wait_for_device(finished_notify_fd):

    # start the monitor _before doing the initial scan,
    # so we can't accidentally miss the event
    monitor = pyudev.Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem="usbmisc")
    monitor.start()

    # do the initial scan
    device_fd = find_devices()

    if device_fd:
        return device_fd

    # start polling the monitor
    while True:
        ready, a, b = select.select([monitor, finished_notify_fd], [], [])

        if finished_notify_fd in ready:
            return None

        # there's definitely something in here now
        device = monitor.poll()
        if not device:
            continue

        log.debug("found a new device")

        # check if the subsystem is actually correct
        if device["SUBSYSTEM"] != "usbmisc":
            continue

        # check if the device was plugged in
        log.debug("device action was \"{}\"".format(device.action))
        if device.action != "add":
            continue

        # check if this is a stenoHID interface
        device_fd = check_device(device)
        if device_fd:
            return device_fd

if __name__ == "__main__":
    import sys
    print(wait_for_device(sys.stdin))
