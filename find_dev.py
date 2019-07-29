import pyudev
import hiddev
import select

ctx = pyudev.Context()

def check_device(device):
    """Checks if a given hiddev device belongs to a stenoHID interface. Returns True if it does, False otherwise."""

    # check that it's actually an hid device
    interface = device.find_parent(subsystem="usb", device_type="usb_interface")
    if interface["DRIVER"] != "usbhid":
        return False

    # check the vendor and product IDs
    usb_device = interface.find_parent(subsystem="usb", device_type="usb_device")
    print(usb_device["ID_MODEL_ID"])
    if usb_device["ID_VENDOR_ID"] != "feed" or usb_device["ID_MODEL_ID"] != "1337":
        print("id mismatch")
        return False

    fname = device["DEVNAME"]

    # check the application usage page
    # we have to actually open the device for this
    # (we'll only check collection 0)
    with open(fname, "rb") as f:
        info = hiddev.hiddev_collection_info()
        info.get_info(f.fileno(), index=0)

        print("found device with usage {:04x}".format(info.usage))

        if info.usage != 0xff020001:
            print("usage mismatch")
            return False

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
