
import asyncio
import logging
import time

from concurrent.futures import CancelledError

from evdev import ecodes

from .util import run_async_jobs, abort
from .input import EventHandler, make_devices
from .lcd import LCD

BANNER = "*** OPIMIDI ***"

KEYS = {
        ecodes.BTN_1: "A",
        ecodes.BTN_2: "MODE",
        ecodes.BTN_3: "B",
        }

QUEUE_SIZE = 10
HOLD_TIME = 2

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
            if i_type == "press":
                # any key press
                return DefaultMode(self.ui)
            self.ui.write_centered(1, time.ctime())

class DefaultMode(UIMode):
    def enter(self):
        self.ui.write_centered(0, BANNER)
        self.ui.write_three(1, "<-", "preset", "->")

    def leave(self):
        pass

    async def run(self):
        while True:
            i_type, key_name = await self.ui.input()
            if i_type == "hold" and key_name == "MODE":
                return StandByMode(self.ui)

class OpimidiUI(EventHandler):
    def __init__(self):
        self._pressed = {}
        self.lcd = LCD()
        self.lcd.set_display(cursor=False, blink=False)
        self.input_queue = asyncio.Queue(QUEUE_SIZE)

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
