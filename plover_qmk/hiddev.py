#!/usr/bin/python
#
# This code is based on work by Dima Tisnek, released here: https://github.com/dimaqq/recipes/blob/master/hiddev.py .
# It was almost completely rewritten by me (Antonius Frie) in January of 2020; the only parts of the original code
# that remain untouched are the four IOC constants, as well as the FIX function. This code still has some similarities to the
# original, but these are almost exclusively due to the fact that both use the same API.

import struct, array, fcntl
from collections import namedtuple as _namedtuple


# namedtuple only added defaults in python3.7, so we're doing our own version here


def namedtuple(typename, field_names, rename=False, defaults=None):

    tupletype = _namedtuple(typename, field_names, rename=rename)

    # patch the defaults into the type's "__new__"
    # this is exactly the same thing that namedtuple does internally
    # please don't ask me how it works
    if defaults is not None:
        tupletype.__new__.__defaults__ = tuple(defaults)

    return tupletype


StructInfo = namedtuple("StructInfo", ["tupletype", "fmt"])

# See <linux/hiddev.h> for the original definitions of these structs
# TODO: use a ctypes Structure for this instead??

hiddev_u32 = StructInfo(
    tupletype=namedtuple("hiddev_u32", ["value"], defaults=[0]), fmt=struct.Struct("I")
)

hiddev_buffer = StructInfo(
    tupletype=namedtuple("hiddev_buffer", ["data"], defaults=[bytes()]),
    fmt=struct.Struct("256s"),
)

hiddev_devinfo = StructInfo(
    tupletype=namedtuple(
        "hiddev_devinfo",
        [
            "bustype",
            "busnum",
            "devnum",
            "ifnum",
            "vendor",
            "product",
            "version",
            "num_applications",
        ],
        defaults=[0, 0, 0, 0, 0, 0, 0, 0],
    ),
    fmt=struct.Struct("IIIIhhhI"),
)

hiddev_collection_info = StructInfo(
    tupletype=namedtuple(
        "hiddev_collection_info",
        ["index", "type", "usage", "level"],
        defaults=[0, 0, 0, 0],
    ),
    fmt=struct.Struct("IIII"),
)

hiddev_string_descriptor = StructInfo(
    tupletype=namedtuple(
        "hiddev_string_descriptor", ["index", "value"], defaults=[0, bytes()]
    ),
    fmt=struct.Struct("i256s"),
)

hiddev_report_info = StructInfo(
    tupletype=namedtuple(
        "hiddev_report_info",
        ["report_type", "report_id", "num_fields"],
        defaults=[0, 0, 0],
    ),
    fmt=struct.Struct("III"),
)

hiddev_usage_ref = StructInfo(
    tupletype=namedtuple(
        "hiddev_usage_ref",
        [
            "report_type",
            "report_id",
            "field_index",
            "usage_index",
            "usage_code",
            "value",
        ],
        defaults=[0, 0, 0, 0, 0, 0],
    ),
    fmt=struct.Struct("IIIIIi"),
)


def encode_struct(structinfo, *args, **kwargs):

    # retrieve the namedtuple type associated with the
    # desired struct, and initialize a namedtuple
    # with the arguments we got. this way, we
    # don't have mess around with interpreting the
    # arguments (especially kwargs) ourselves.
    tupletype = structinfo.tupletype

    try:
        struct_data = tupletype(*args, **kwargs)
    except TypeError as e:  # Something probably went wrong with the given arguments
        raise e

    # unpack the namedtuple into the arguments of struct.pack
    # which will hand it all of the fields in the right order.
    encoded_struct = structinfo.fmt.pack(*struct_data)

    return encoded_struct


def decode_struct(structinfo, encoded_struct):

    raw_fields = structinfo.fmt.unpack(encoded_struct)

    # use the raw fields to initialize the corresponding namedtuple.
    # again, these will be in the right order for the initializer.
    decoded_struct = structinfo.tupletype(*raw_fields)

    return decoded_struct


IOCPARM_MASK = 0x7F
IOC_NONE = 0x20000000
IOC_WRITE = 0x40000000
IOC_READ = 0x80000000


class HIDDevice(object):
    def __init__(self, fd):
        self.fd = fd

    def do_ioctl(self, name, *args, **kwargs):

        # lookup structinfo
        structinfo = ioctls[name].structinfo
        encoded_struct = encode_struct(structinfo, *args, **kwargs)

        # turn this into an array so it becomes mutable
        encoded_struct = array.array("B", encoded_struct)

        # assemble request code
        length = structinfo.fmt.size
        request_code = (
            ioctls[name].readwrite
            | ((length & IOCPARM_MASK) << 16)
            | (ord("H") << 8)
            | ioctls[name].number
        )

        # TODO: do we need to include the signed/unsigned fix here?

        # TODO: check return value and turn into an exception if necessary
        fcntl.ioctl(self.fd, request_code, encoded_struct, True)

        result = decode_struct(structinfo, encoded_struct)
        return result

    def get_version(self):
        return self.do_ioctl("hidiocgversion")

    def get_collection_info(self, index):
        return self.do_ioctl("hidiocgcollectioninfo", index=index)

    def get_report(self, report_type, report_id=0):
        self.do_ioctl("hidiocgreport", report_type=report_type, report_id=report_id)

    def get_usage(self, report_type, report_id, field_index, usage_index):
        return self.do_ioctl(
            "hidiocgusage",
            report_type=report_type,
            report_id=report_id,
            field_index=field_index,
            usage_index=usage_index,
        )


def FIX(x):
    return struct.unpack("i", struct.pack("I", x))[0]


