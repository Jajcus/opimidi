
import asyncio
import evdev
import glob
import grp
import logging
import os
import pwd

logger = logging.getLogger("input")

BUTTONS_DEVICE_NAME = "opimidi-keys"

PEDALS_DEVICE_NAME = "pcf8591"
PEDALS_INPUTS = ["in0", "in1"]
PEDALS_POLL_INTERVAL = 0.01
PEDALS_SENSITIVITY = 2

class Buttons:
    def __init__(self):
        self.dev = None
        self._find_device()

    def _find_device(self):
        for dev_fn in evdev.list_devices():
            dev = evdev.InputDevice(dev_fn)
            logging.debug("%s: %r", dev_fn, dev.name)
            if dev.name == BUTTONS_DEVICE_NAME:
                self.dev = dev
                break
        else:
            raise RuntimeError("Could not find '{}' event device"
                               .format(BUTTONS_DEVICE_NAME))

    def set_permissions(self, uid, gid):
        if isinstance(uid, str):
            uid = pwd.getpwnam(uid).pw_uid
        if isinstance(gid, str):
            gid = grp.getgrnam(gid).gr_gid
        os.chown(self.dev.fn, uid, gid)
        os.chmod(self.dev.fn, 0o664)

    async def print_events(self):
        async for event in self.dev.async_read_loop():
            print(evdev.categorize(event), sep=': ')

class Pedals:
    def __init__(self):
        self.inputs = []
        self.values = [None for input_name in PEDALS_INPUTS]
        self._find_device()

    def _find_device(self):
        for path in glob.glob("/sys/class/hwmon/*"):
            dev_path = os.path.join(path, "device")
            name_path = os.path.join(dev_path, "name")
            with open(name_path, "rt") as name_f:
                name = name_f.readline().strip()
            if name == PEDALS_DEVICE_NAME:
                break
        else:
            raise RuntimeError("Could not find '{}' hwmon device"
                               .format(PEDALS_DEVICE_NAME))
        self.inputs = [
            os.path.join(dev_path, input_name + "_input")
            for input_name in PEDALS_INPUTS
            ]

    def read_inputs(self):
        changed = False
        for i, path in enumerate(self.inputs):
            with open(path, "rt") as input_f:
                raw_value = int(input_f.readline().strip())
            value = float(raw_value) / 10
            if (self.values[i] is None
                    or abs(value - self.values[i]) > PEDALS_SENSITIVITY):
                self.values[i] = value
                changed = True
        return changed

    async def print_events(self):
        while True:
            await asyncio.sleep(PEDALS_POLL_INTERVAL)
            if self.read_inputs():
                print(*self.values)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    buttons = Buttons()
    pedals = Pedals()
    asyncio.ensure_future(buttons.print_events())
    asyncio.ensure_future(pedals.print_events())
    loop = asyncio.get_event_loop()
    loop.run_forever()
