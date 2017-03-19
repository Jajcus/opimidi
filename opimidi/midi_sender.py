
from evdev import ecodes
import rtmidi
import logging

from .config import Config
from .input import EventHandler, make_devices
from .util import run_async_jobs

logger = logging.getLogger("midi_sender")

MIDI_PORT = "f_midi:f_midi-0"
DEFAULT_CHANNEL = 1

class MidiAction:
    def message(self, value):
        """Midi message to send on this action.
        
        value is current value of the input (0.0 - 1.0)."""
        raise NotImplementedError

class ControlChange(MidiAction):
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

class BankSelect(ControlChange):
    def __init__(self, bank_number, channel=DEFAULT_CHANNEL):
        if bank_number < 1 or bank_number > 16384:
            raise ValueEror("Invalid bank number")
        midi_val = bank_number - 1
        code = 0xb0 | (channel - 1) & 0x0f
        msb = (midi_val >> 7) & 0x7f
        lsb = midi_val & 0x7f
        self._msg = [code, 0x00, msb, 0x20, lsb]
    def message(self, value):
        if value > 0.5:
            return self._msg
        else:
            return []

class ProgramChange(MidiAction):
    def __init__(self, program_number, channel=DEFAULT_CHANNEL):
        if program_number < 1 or program_number > 128:
            raise ValueEror("Invalid program number")
        code = 0xc0 | (channel - 1) & 0x0f
        self._msg = [code, program_number - 1]
    def message(self, value):
        if value > 0.5:
            return self._msg
        else:
            return []

INPUTS = {
        "button_A": (ecodes.EV_KEY, ecodes.BTN_0),
        "button_B": (ecodes.EV_KEY, ecodes.BTN_1),
        "pedal_1": (ecodes.EV_ABS, 0),
        "pedal_2": (ecodes.EV_ABS, 1),
        }

DEMO_EVENT_MAP = {
        (ecodes.EV_KEY, ecodes.BTN_1): [ControlChange(80),],
        (ecodes.EV_KEY, ecodes.BTN_2): [ControlChange(81),],
        (ecodes.EV_ABS, 0): [ControlChange(4),],
        (ecodes.EV_ABS, 1): [ControlChange(1),],
        }

OP_ALLOWED = ["ControlChange", "ProgramChange"]
OP_NAMESPACE = { k: v for k, v in globals().items() if k in OP_ALLOWED }
OP_NAMESPACE["__builtins__"] = {}

def eval_ops(string):
    if "__" in string:
        logger.error("Expression %r not allowed", string)
        return []
    expr = "[" +  string + "]"
    logger.debug("Evaluating %r in %r", expr, OP_NAMESPACE)
    try:
        return eval(expr, OP_NAMESPACE)
    except Exception as err:
        logger.error("Invalid expression %r: %s", string, err)
        return []

class MIDISender(EventHandler):
    def __init__(self, config, event_map=None):
        self.config = config
        self.leave_ops = []
        if event_map:
            self.event_map = event_map
        else:
            self.event_map = {}
        self.midiout = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA)
        self.midi_port = None
        for i, name in enumerate(self.midiout.get_ports()):
            if name == MIDI_PORT or name.split(" ", 1)[0] == MIDI_PORT:
                self.midi_port = self.midiout.open_port(i)
                break
        else:
            raise RuntimeError("Could not find MIDI port %r", MIDI_PORT)

    def apply_ops(self, ops, value=1.0):
        for op in ops:
            message = op.message(value)
            logger.debug("  sending message: %r", message)
            self.midi_port.send_message(message)

    def handle_event(self, event):
        logger.debug("incoming event: %r", event)
        ops = self.event_map.get((event.type, event.code))
        if not ops:
            logger.debug("  no MIDI operators for that")
            return
        self.apply_ops(ops, event.value)

    def set_program(self, bank_n, prog_n):
        logger.debug("Switching to program %s:%s", bank_n, prog_n)
        program = self.config.get_program(bank_n, prog_n)
        if "enter" in program:
            enter_ops = eval_ops(program["enter"])
            self.apply_ops(enter_ops)
        if "leave" in program:
            self.leave_ops = eval_ops(program["leave"])
        else:
            self.leave_ops = []
        self.event_map = {}
        for key, event in INPUTS.items():
            try:
                ops_s = program[key]
            except KeyError:
                continue
            self.event_map[event] = eval_ops(ops_s)
        logger.debug("Event map: %r", self.event_map)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config = Config()
    midi_sender = MIDISender(config, DEMO_EVENT_MAP)
    jobs = []
    for device in make_devices():
        jobs.append(device.collect_events(midi_sender))
    run_async_jobs(jobs)

