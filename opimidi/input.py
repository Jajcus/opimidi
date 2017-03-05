
import asyncio
import evdev
import glob
import logging
import os
import time

from collections import namedtuple

from .exceptions import HardwareInitError
from .util import run_async_jobs

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
PEDALS_SENSITIVITY = 4

InputEvent = namedtuple("InputEvent", "timestamp type code value timedelta")

class EventHandler:
    def handle_event(self, event):
        """Process incoming event.
        `event`: an InputEvent tuple
        """
        raise NotImplementedError

class EvdevInput:
    def __init__(self, device_name):
        self.dev = None
        self.key_state = {}
        self.key_ts = {}
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

    async def collect_events(self, handler):
        async for event in self.dev.async_read_loop():
            if event.type == evdev.ecodes.EV_SYN:
                continue
            elif event.type == evdev.ecodes.EV_KEY:
                key_event = evdev.events.KeyEvent(event)
                if key_event.keystate not in (0, 1):
                    continue
                key_code = event.code
                state = bool(key_event.keystate)
                last_state = self.key_state.get(key_code, False)
                if state == last_state:
                    continue
                timestamp = event.timestamp()
                last_ts = self.key_ts.get(key_code)
                if last_ts:
                    time_delta = timestamp - last_ts
                else:
                    time_delta = 0
                self.key_state[key_code] = state
                self.key_ts[key_code] = timestamp
                ievent = InputEvent(timestamp, event.type, key_code,
                                    float(state), time_delta)
                handler.handle_event(ievent)
                        
            else:
                logger.debug("Ignoring unknown event: %s",
                             evdev.util.categorize(event))

class HwmonInput:
    def __init__(self, device_name, input_names):
        self.inputs = []
        self.values = []
        self.rel_values = []
        self.min = []
        self.max = []
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
            self.values.append(value // 10)
            self.rel_values.append(0.5)
        self.min = list(self.values)
        self.max = list(self.values)

    def get_write_files(self):
        return []

    def read_inputs(self):
        changed = []
        for i, path in enumerate(self.inputs):
            with open(path, "rt") as input_f:
                raw_value = int(input_f.read().strip())
            last_value = self.values[i]
            value = raw_value // 10
            if value == last_value:
                continue
            max_v = self.max[i]
            min_v = self.min[i]
            if value > max_v:
                logger.debug("%r > %r, recalibrating", value, max_v)
                max_v = value
                self.max[i] = max_v
            elif value < min_v:
                logger.debug("%r < %r, recalibrating", value, min_v)
                min_v = value
                self.min[i] = min_v
            elif abs(value - self.values[i]) < PEDALS_SENSITIVITY:
                # ignore small changes
                continue
            elif  value < min_v + PEDALS_SENSITIVITY:
                value = min_v
            elif value > max_v - PEDALS_SENSITIVITY:
                value = max_v
            self.values[i] = value
            self.rel_values[i] = float(value - min_v) / (max_v - min_v)
            changed.append(i)
        return changed

    async def collect_events(self, handler):
        while True:
            await asyncio.sleep(PEDALS_POLL_INTERVAL)
            timestamp = time.time()
            for i in self.read_inputs():
                ievent = InputEvent(timestamp, evdev.ecodes.EV_ABS, i,
                                    self.rel_values[i], 0)
                handler.handle_event(ievent)

class EventPrinter:
    def handle_event(self, event):
        """Process incoming event.
        """
        print("{:15.2f} {} {} {:5.2f} {:5.2f}"
                .format(event.timestamp, event.type, event.code,
                        event.value, event.timedelta))

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
    printer = EventPrinter()
    jobs = []
    for device in make_devices():
        jobs.append(device.collect_events(printer))
    run_async_jobs(jobs)
