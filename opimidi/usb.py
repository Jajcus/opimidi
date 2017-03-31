"""Configure the USB gadget."""

import argparse
import errno
import os
import logging
import sys

logger = logging.getLogger("usb")

# http://pid.codes/1209/0001/
# note: this is not universally unique
VENDOR_ID = 0x1209
PRODUCT_ID = 0x0001

GADGET_STRINGS = {
        0x409: {
            "manufacturer": "Jajcus",
            "product": "opimidi",
            }
        }

MAX_POWER = 400

FUNCTIONS = {
        "midi.midi0": {
                "id": "opimidi",
                "in_ports": 1,
                "out_ports": 2,
            },
        "acm.acm0": {
            },
        }
 
# Gadget instance name in configfs
CONFIGFS_GADGET_NAME = "opimidi"
CONFIGFS_HOME = "/sys/kernel/config"

def _new_dir(name):
    logging.debug("mkdir %s", name)
    os.mkdir(name)
    logging.debug("chdir %s", name)
    os.chdir(name)

def _write_file(name, data):
    logging.debug("echo '%s' > %s", data, name)
    with open(name, "wt") as file:
        print(data, file=file)

def _up_dir():
    logging.debug("chdir ..")
    os.chdir("..")

def _up_2dir():
    logging.debug("chdir ../..")
    os.chdir("../..")

def _symlink(src, dst):
    logging.debug("ln -s %s %s", src, dst)
    os.symlink(src, dst)

def _rmdir(path):
    if os.path.exists(path):
        logging.debug("rmdir %s", path)
        os.rmdir(path)

def _rm(path):
    if os.path.exists(path):
        logging.debug("rm %s", path)
        os.remove(path)

def make_usb_gadget():
    udcs = os.listdir("/sys/class/udc")
    if len(udcs) < 1:
        raise FileNotFoundError("No UDC available!")
    gadget_dir = os.path.join(CONFIGFS_HOME, "usb_gadget", CONFIGFS_GADGET_NAME)
    _new_dir(gadget_dir)
    _write_file("idVendor", VENDOR_ID)
    _write_file("idProduct", PRODUCT_ID)
    for language, strings in GADGET_STRINGS.items():
        _new_dir("strings/0x{:x}".format(language))
        for key, value in strings.items():
            _write_file(key, value)
        _up_2dir()
    _new_dir("configs/c.1")
    _up_2dir()
    for function, config in FUNCTIONS.items():
        _new_dir("functions/" + function)
        for key, value in config.items():
            _write_file(key, value)
        _up_2dir()
        _symlink("functions/" + function, "configs/c.1/" + function)
    _write_file("UDC", udcs[0])

def remove_usb_gadget():
    gadget_dir = os.path.join(CONFIGFS_HOME, "usb_gadget", CONFIGFS_GADGET_NAME)
    if not os.path.exists(gadget_dir):
        return
    logging.debug("chdir %s", gadget_dir)
    os.chdir(gadget_dir)
    try:
        _write_file("UDC", "")
    except OSError as err:
        if err.errno != errno.ENODEV:
            raise
    for function in FUNCTIONS:
        _rm("configs/c.1/" + function)
        _rmdir("functions/" + function)
    _rmdir("configs/c.1")
    for language in GADGET_STRINGS:
        _rmdir("strings/0x{:x}".format(language))
    _up_dir()
    _rmdir(gadget_dir)

def _parse_cmdline():
    parser = argparse.ArgumentParser(description="Set device permissions for opimidi")
    parser.add_argument("--debug", dest="log_level",
                        action="store_const", const=logging.DEBUG,
                        help="Enable debug logging")
    parser.set_defaults(log_level=logging.INFO)
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)

def opimidi_start_usb():
    _parse_cmdline()
    try:
        make_usb_gadget()
    except OSError as err:
        print(err, file=sys.stderr)
        sys.exit(1)

def opimidi_stop_usb():
    _parse_cmdline()
    try:
        remove_usb_gadget()
    except OSError as err:
        print(err, file=sys.stderr)
        sys.exit(1)
