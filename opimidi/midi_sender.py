
from evdev import ecodes
import rtmidi
import logging

from .input import EventHandler, make_devices
from .util import run_async_jobs

logger = logging.getLogger("midi_sender")

MIDI_PORT = "f_midi:f_midi-0"
DEFAULT_CHANNEL = 1

class ControlChange:
    def __init__(self, number, lsb_number=None, channel=DEFAULT_CHANNEL):
        self.number = number & 0x7f
        if lsb_number is not None:
            self.lsb_number = lsb_number & 0x7f
        else:
            self.lsb_number = None
        self.code = 0xb0 | (channel - 1) & 0x0f

    def message(self, value):
        if self.lsb_number is None:
            # one byte precision
            midi_val = round(value * 127) & 0x7f
            return [self.code, self.number, midi_val]
        else:
            # two bytes precision
            midi_val = round(value * 16383)
            msb = (midi_val >> 7) & 0x7f
            lsb = midi_val & 0x7f
            return [self.code, self.number, msb, self.lsb_number, lsb]

EVENT_MAP = {
        (ecodes.EV_KEY, ecodes.BTN_1): ControlChange(80),
        (ecodes.EV_KEY, ecodes.BTN_2): ControlChange(81),
        (ecodes.EV_ABS, 0): ControlChange(4),
        (ecodes.EV_ABS, 1): ControlChange(1),
        }

class MIDISender(EventHandler):
    def __init__(self):
        self.midiout = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA)
        self.midi_port = None
        for i, name in enumerate(self.midiout.get_ports()):
            if name == MIDI_PORT or name.split(" ", 1)[0] == MIDI_PORT:
                self.midi_port = self.midiout.open_port(i)
                break
        else:
            raise RuntimeError("Could not find MIDI port %r", MIDI_PORT)
    def handle_event(self, timestamp, e_type, e_code, value, timedelta):
        logger.debug("incoming event: %r",
                     (timestamp, e_type, e_code, value, timedelta))
        midi_event = EVENT_MAP.get((e_type, e_code))
        if not midi_event:
            logger.debug("  no MIDI event for that")
            return
        message = midi_event.message(value)
        logger.debug("  sending message: %r", message)
        self.midi_port.send_message(message)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    midi_sender = MIDISender()
    jobs = []
    for device in make_devices():
        jobs.append(device.collect_events(midi_sender))
    run_async_jobs(jobs)

