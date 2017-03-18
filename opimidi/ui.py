
import asyncio
import logging
import glob
import re
import subprocess
import sys
import time

from concurrent.futures import CancelledError

from evdev import ecodes

from .util import run_async_jobs, abort
from .input import EventHandler, make_devices
from .lcd import LCD
from .config import Config

BANNER = "*** OPIMIDI ***"

KEYS = {
        ecodes.BTN_0: "A",
        ecodes.BTN_1: "B",
        ecodes.BTN_2: "MODE",
        }

QUEUE_SIZE = 10
HOLD_TIME = 1

IP_CMD = ["/sbin/ip", "-o", "-4", "addr", "show", "dev", "eth0"]
IP_RE = re.compile(r"inet\s+([\d.]+)")

logger = logging.getLogger("ui")

class UIMode:
    """Implementation of a single UI mode."""
    def __init__(self, ui):
        self.ui = ui

    def enter(self):
        """Enter new UI mode.
        
        Changes display contents and the back-end state."""
        pass

    async def run(self):
        """Main loop of the UI mode.
        
        React to the input events, return new mode when done."""
        raise NotImplementedError

    def leave(self):
        """Leave the UI mode.

        Reset back-end state changed by enter()."""
        pass

class StandByMode(UIMode):
    def __init__(self, ui):
        super().__init__(ui)

    def enter(self):
        self.ui.lcd.set_backlight(False)
        self.ui.write_centered(0, BANNER)
        self.ui.write_centered(1, time.ctime())
    
    def leave(self):
        self.ui.lcd.set_backlight(True)

    async def run(self):
        while True:
            i_type, key_name = await self.ui.input(10)
            logger.debug("%s: %s", i_type, key_name)
            if i_type == "press":
                # any key press
                return DefaultMode(self.ui)
            self.ui.write_centered(1, time.ctime())

class MenuMode(UIMode):
    menu_entries = [
            "???",
            ]
    menu_line = 1
    def __init__(self, ui):
        super().__init__(ui)
        self.current = 0

    def enter(self):
        self.ui.write_centered(0, BANNER)
        self.update_menu()

    def update_menu(self):
        entry = self.menu_entries[self.current]
        logger.debug("Selected: %r", entry)
        self.ui.write_three(self.menu_line, "<-", entry, "->")
        select_method = "select_" + entry.lower().replace(" ", "_")
        if hasattr(self, select_method):
            getattr(self, select_method)()
        else:
            logger.debug("No such method: %r", select_method)

    def activate(self, entry):
        logger.debug("Entering: %r", entry)
        activate_method = "activate_" + entry.lower().replace(" ", "_")
        method = getattr(self, activate_method, None)
        if method:
            return method()
        else:
            logger.debug("No such method: %r", activate_method)
        return None

    def leave(self):
        pass

    async def run(self):
        while True:
            i_type, key_name = await self.ui.input()
            logger.debug("%s: %s", i_type, key_name)
            if i_type == "hold" and key_name == "MODE":
                return DefaultMode(self.ui)
            if i_type != "press":
                continue
            if key_name == "A":
                change = -1
            elif key_name == "B":
                change = 1
            elif key_name == "MODE":
                entry = self.menu_entries[self.current]
                new_mode = self.activate(entry)
                if new_mode is not None:
                    return new_mode
            else:
                continue
            self.current = (self.current + change) % len(self.menu_entries)
            self.update_menu()

class SetupMode(MenuMode):
    menu_entries = [
            "Info",
            "Standby",
            ]
    def activate_info(self):
        return InfoMode(self.ui)
    def activate_standby(self):
        return StandByMode(self.ui)

def _get_cpu_temp():
    with open("/sys/class/thermal/thermal_zone0/temp", "rt") as temp_f:
        value = temp_f.read().strip()
    try:
        temp = round(float(value) / 1000.0)
    except ValueError as err:
        raise OSError("Invalid CPU temp value read: " + value.strip())
    return temp

def _get_case_temp():
    w1_devs = glob.glob("/sys/bus/w1/devices/28-*/w1_slave")
    if not w1_devs:
        raise OSError("No w1 temperature sensor found")

    with open(w1_devs[0], "rt") as temp_f:
        line1 = temp_f.readline().strip()
        line2 = temp_f.readline().strip()

    if not line1.endswith("YES"):
        raise OSError("Bad w1 temperature sensor reading")

    if "t=" not in line2:
        raise OSError("Bad w1 temperature sensor reading")

    try:
        temp = round(float(line2.split("t=", 1)[1]) / 1000.0)
    except ValueError as err:
        raise OSError("Invalid case temp value read: " + value.strip())

    return temp

class InfoMode(MenuMode):
    menu_entries = [
            "IP Address",
            "Temperature",
            ]
    menu_line = 0
    def enter(self):
        self.update_menu()

    def select_ip_address(self):
        try:
            output = subprocess.check_output(IP_CMD)
        except (OSError, subprocess.CalledProcessError) as err:
            logger.error("%s: %s", " ".join(IP_CMD), err)
            self.ui.write_centered(1, "unknown")
            return
        output = output.decode("utf-8", "replace")
        match = IP_RE.search(output)
        if not match:
            logger.debug("could not find IP in: %r", output)
            self.ui.write_centered(1, "unknown")
            return
        self.ui.write_centered(1, match.group(1))

    def select_temperature(self):
        self.ui.write_centered(1, "...")
        try:
            cpu_temp = "{}\xdfC".format(_get_cpu_temp())
        except OSError as err:
            logger.warning("Could not read CPU temp: %s", err)
            cpu_temp = "unkn"

        try:
            case_temp = "{}\xdfC".format(_get_case_temp())
        except OSError as err:
            case_temp = "unkn"

        self.ui.write_centered(1, cpu_temp + " / " + case_temp)

    def activate(self, entry):
        return SetupMode(self.ui)


class DefaultMode(UIMode):
    def enter(self):
        self.ui.write_centered(0, self.ui.bank.name)
        self.ui.write_three(1, "<", self.ui.program.name, ">")

    def leave(self):
        pass

    async def run(self):
        while True:
            i_type, key_name = await self.ui.input()
            logger.debug("%s: %s", i_type, key_name)
            if i_type == "hold" and key_name == "MODE":
                return SetupMode(self.ui)
            elif i_type != "press":
                continue
            if key_name == "MODE":
                return ProgramMode(self.ui)
            elif key_name == "A":
                self.ui.select_program(self.ui.cur_prog_i - 1)
            elif key_name == "B":
                self.ui.select_program(self.ui.cur_prog_i + 1)
            self.ui.write_three(1, "<", self.ui.program.name, ">")

class ProgramMode(UIMode):
    def enter(self):
        prog = self.ui.program
        logger.debug("Program settings: %r", prog.settings)
        labels = prog.settings.get("labels")
        if labels:
            self.ui.write_centered(0, prog.name)
            self.ui.write_centered(1, labels)
        else:
            self.ui.write_centered(0, self.ui.bank.name)
            self.ui.write_centered(1, prog.name)

    def leave(self):
        pass

    async def run(self):
        while True:
            i_type, key_name = await self.ui.input()
            logger.debug("%s: %s", i_type, key_name)
            if i_type == "hold" and key_name == "MODE":
                return SetupMode(self.ui)
            elif i_type != "press":
                continue
            if key_name == "MODE":
                return DefaultMode(self.ui)

class OpimidiUI(EventHandler):
    def __init__(self, backend=None):
        self.cur_bank_i = 0
        self.cur_prog_i = 0
        self.banks = []
        self.bank = None
        self.program = None
        self.programs = []
        self.backend = backend
        if backend:
            backend.ui = self
        self._pressed = {}
        self.config = Config()
        self.lcd = LCD()
        self.lcd.set_display(cursor=False, blink=False)
        self.input_queue = asyncio.Queue(QUEUE_SIZE)
        banks = self.config.get_banks()
        logger.debug("Configured banks: %r", banks)
        self.banks = [b for b in banks if b.programs]
        if not self.banks:
            logger.error("No programs found in config file")
            sys.exit(1)
        self.select_bank(0, False)

    def select_bank(self, index, in_backend=True):
        self.cur_bank_i = index % len(self.banks)
        self.bank = self.banks[self.cur_bank_i]
        self.programs = list(self.bank.programs.values())
        logger.debug("Selected bank #%i. Programs: %r",
                     self.cur_bank_i,
                     self.programs)
        self.select_program(0, in_backend)

    def select_program(self, index, in_backend=True):
        self.cur_prog_i = index % len(self.programs)
        self.program = self.programs[self.cur_prog_i]

    def write_centered(self, line, text):
        text = text[:self.lcd.width].center(self.lcd.width)
        self.lcd.write(line, 0, text)

    def write_three(self, line, text1, text2, text3):
        space_left = self.lcd.width - len(text1) - len(text3)
        text2 = text2[:space_left].center(space_left)
        text = text1 + text2 + text3
        self.lcd.write(line, 0, text[:self.lcd.width])
 
    async def input(self, timeout=None):
        get_item = self.input_queue.get()
        if timeout:
            try:
                return await asyncio.wait_for(get_item, timeout)
            except asyncio.TimeoutError:
                return None, None
        return await get_item

    def handle_event(self, event):
        logger.debug("incoming event: %r", event)
        if event.type != ecodes.EV_KEY:
            return

        waiting = self._pressed.pop(event.code, None)
        if event.value > 0.5:
            # key pressed
            if waiting:
                # just in case
                waiting.cancel()
            loop = asyncio.get_event_loop()
            waiting = loop.call_later(HOLD_TIME, self._push_hold, event)
            self._pressed[event.code] = waiting
        else:
            # key released
            if waiting:
                waiting.cancel()
                self._push_input("press", event)

    def _push_hold(self, event):
        try:
            del self._pressed[event.code]
        except KeyError:
            logger.debug("_push_hold for code not presed??")
        self._push_input("hold", event)

    def _push_input(self, i_type, event):
        try:
            key_name = KEYS[event.code]
        except KeyError:
            logger.debug("Ignoring unknown key: %r", event.code)
            return
        try:
            self.input_queue.put_nowait((i_type, key_name))
        except asyncio.QueueFull:
            logger.warning("Input queue full! Flushing old events.")
            self.input_queue = asyncio.Queue(QUEUE_SIZE)
            asyncio.ensure_future(self.input_queue.put((i_type, key_name)))

    async def run(self):
        mode = StandByMode(self)
        try:
            while mode:
                logger.debug("Entering %r", mode)
                mode.enter()
                try:
                    next_mode = await mode.run()
                finally:
                    logger.debug("Leaving %r", mode)
                    mode.leave()
                mode = next_mode
        except CancelledError:
            raise
        except Exception:
            logger.exception("Exception in UI.run()")
            abort()
        finally:
            self.lcd.set_backlight(False)
            self.lcd.clear()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    ui = OpimidiUI()
    jobs = []
    for device in make_devices():
        jobs.append(device.collect_events(ui))
    jobs.append(ui.run())
    run_async_jobs(jobs)
