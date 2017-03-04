
import asyncio
import evdev
import glob
import logging
import os

from .exceptions import HardwareInitError

logger = logging.getLogger("input")

# buttons
EVDEV_DEVICES = ["opimidi-keys"]

# analog input from pedals
HWMON_DEVICES = {
        "pcf8591": ["in0", "in1"],
        }

PEDALS_DEVICE_NAME = "pcf8591"
PEDALS_INPUTS = ["in0", "in1"]
PEDALS_POLL_INTERVAL = 0.01
PEDALS_SENSITIVITY = 2

class EvdevInput:
    def __init__(self, device_name):
        self.dev = None
        self._find_device(device_name)

    def _find_device(self, device_name):
        for dev_fn in evdev.list_devices():
            dev = evdev.InputDevice(dev_fn)
            logger.debug("%s: %r", dev_fn, dev.name)
            if dev.name == device_name:
                self.dev = dev
                break
        else:
            raise HardwareInitError("Could not find '{}' event device"
                                    .format(device_name))

    def get_write_files(self):
        return [self.dev.fn]

    async def print_events(self):
        async for event in self.dev.async_read_loop():
            print(evdev.categorize(event), sep=': ')

class HwmonInput:
    def __init__(self, device_name, input_names):
        self.inputs = []
        self.values = []
        self._find_device(device_name, input_names)

    def _find_device(self, device_name, input_names):
        for path in glob.glob("/sys/class/hwmon/*"):
            dev_path = os.path.join(path, "device")
            name_path = os.path.join(dev_path, "name")
            with open(name_path, "rt") as name_f:
                name = name_f.read().strip()
            if name == device_name:
                break
        else:
            raise HardwareInitError("Could not find '{}' hwmon device"
                                    .format(device_name))
        self.inputs = []
        self.values = []
        for input_name in PEDALS_INPUTS:
            input_path = os.path.join(dev_path, input_name + "_input")
            try:
                with open(input_path, "rt") as input_f:
                    value = int(input_f.read().strip())
            except (IOError, ValueError) as err:
                raise HardwareInitError("Cannot read input {!r} on device {!r}: {}"
                                        .format(input_name, device_name, err))
            self.inputs.append(input_path)
            self.values.append(value)

    def get_write_files(self):
        return []

    def read_inputs(self):
        changed = False
        for i, path in enumerate(self.inputs):
            with open(path, "rt") as input_f:
                raw_value = int(input_f.read().strip())
            value = float(raw_value) / 10
            if abs(value - self.values[i]) > PEDALS_SENSITIVITY:
                self.values[i] = value
                changed = True
        return changed

    async def print_events(self):
        while True:
            await asyncio.sleep(PEDALS_POLL_INTERVAL)
            if self.read_inputs():
                print(*self.values)

def make_devices():
    result = []
    for device_name in EVDEV_DEVICES:
        try:
            evdev_input = EvdevInput(device_name)
        except HardwareInitError as err:
            logger.error(err)
            continue
        result.append(evdev_input)
    for device_name, input_names in HWMON_DEVICES.items():
        try:
            hwmon_input = HwmonInput(device_name, input_names)
        except HardwareInitError as err:
            logger.error(err)
            continue
        result.append(hwmon_input)
    return result

def get_write_files():
    result = []
    for device in make_devices():
        result += device.get_write_files()
    return result

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    for device in make_devices():
        asyncio.ensure_future(device.print_events())
    loop = asyncio.get_event_loop()
    loop.run_forever()
