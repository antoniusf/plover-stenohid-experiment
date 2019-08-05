import pyudev
import select
import time

from plover import log

from . import hiddev

ctx = pyudev.Context()

# TODO: make all lookups get()s, because apparently these attributes can disappear sometimes

def check_device(device):
    """Checks if a given hiddev device belongs to a stenoHID interface. Returns True if it does, False otherwise."""

    # check that it's actually an hid device
    print("checking if it's an hid...", end="\t")
    interface = device.find_parent(subsystem="usb", device_type="usb_interface")

    # this can happen if the device is unplugged in between
    if interface is None:
        print("error (device unplugged)")
        return False
    
    if interface["DRIVER"] != "usbhid":
        print("no")
        return False

    print("yes")

    # check the vendor and product IDs
    print("checking if vendor and product IDs match...", end="\t")
    usb_device = interface.find_parent(subsystem="usb", device_type="usb_device")

    if usb_device is None:
        print("error (device unplugged)")
        return False
    
    if not usb_device or usb_device["ID_VENDOR_ID"] != "feed" or usb_device["ID_MODEL_ID"] != "1337":
        print("no (device IDs were 0x{}, 0x{})".format(usb_device["ID_VENDOR_ID"], usb_device["ID_MODEL_ID"]))
        return False

    print("yes")

    print("checking if it has the correct usage...", end="\t")

    fname = device["DEVNAME"]

    # check the application usage page
    # we have to actually open the device for this
    # (we'll only check collection 0)
    try:
        with open(fname, "rb") as f:

            info = hiddev.hiddev_collection_info()
            info.get_info(f.fileno(), index=0)

            print("found device with usage {:04x}".format(info.usage))

            if info.usage != 0xff020001:
                print("no")
                return False

    # FileNotFoundError can be thrown by open()
    # OSError can be thrown by the ioctl inside of info.get_info
    except (FileNotFoundError, OSError):
        print("error (device unplugged)")
        return False

    print("hi")
    time.sleep(5)

    print("yes")
    return True

def find_devices():

    # usbmisc is where the hiddev devices appear to sit
    for device in ctx.list_devices(subsystem="usbmisc"):

        if check_device(device):
            # we've found our device!
            return device

    # we've found nothing...
    return None

def wait_for_device(finished_notify_fd):

    # start the monitor _before doing the initial scan,
    # so we can't accidentally miss the event
    monitor = pyudev.Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem="usbmisc")
    monitor.start()

    # do the initial scan
    device = find_devices()

    if device is not None:
        return device["DEVNAME"]

    # start polling the monitor
    while True:
        ready, a, b = select.select([monitor, finished_notify_fd], [], [])

        if finished_notify_fd in ready:
            return None

        # there's definitely something in here now
        device = monitor.poll()
        if not device:
            continue

        # check if the subsystem is actually correct
        if device["SUBSYSTEM"] != "usbmisc":
            continue

        # check if the device was plugged in
        print(device.action)
        if device.action != "add":
            continue

        # check if this is a stenoHID interface
        if check_device(device):
            return device["DEVNAME"]

if __name__ == "__main__":
    import sys
    print(wait_for_device(sys.stdin))
