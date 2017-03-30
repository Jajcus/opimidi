
from evdev import ecodes

import logging

from .alsa import seq
from .config import Config
from .input import EventHandler, make_devices
from .util import run_async_jobs

logger = logging.getLogger("midi_sender")

MIDI_DEST = "f_midi"

class MidiAction:
    def message(self, value):
        """Midi message to send on this action.
        
        value is current value of the input (0.0 - 1.0)."""
        raise NotImplementedError

class ControlChange(MidiAction):
    def __init__(self, number):
        self.event = seq.SeqControlChangeEvent(param=number)

    def message(self, value):
        # one byte precision
        midi_val = round(value * 127) & 0x7f
        self.event.value = midi_val
        return [self.event]

class BankSelect(MidiAction):
    def __init__(self, bank_number):
        if bank_number < 1 or bank_number > 16384:
            raise ValueEror("Invalid bank number")
        midi_val = bank_number - 1
        self.event = seq.SeqControlChange14btEvent(param=0, value=midi_val)

    def message(self, value):
            if value > 0.5:
                return [self.event]
            else:
                return []

class ProgramChange(MidiAction):
    def __init__(self, program_number):
        if program_number < 1 or program_number > 128:
            raise ValueEror("Invalid program number")
        self.event = seq.SeqProgramChangeEvent(value=program_number-1)
    def message(self, value):
        if value > 0.5:
            return [self.event]
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
        self.seq = seq.SeqClient("opimidi")
        self.port = self.seq.create_port("out",
                                         seq.PORT_CAP_READ|seq.PORT_CAP_SUBS_READ,
                                         seq.PORT_TYPE_MIDI_GENERIC)
        try:
            dest_client, dest_port = self.seq.parse_address(MIDI_DEST)
        except RuntimeError as err:
            logger.error("could not parse 'aseqdump': %s", err)
        try:
            self.seq.connect_to(self.port, dest_client, dest_port)
        except RuntimeError as err:
            logger.error("could not connect to %s:%s: %s", dest_addr, dest_port, err)

    def apply_ops(self, ops, value=1.0):
        for op in ops:
            message = op.message(value)
            logger.debug("  sending message: %r", message)
            for event in message:
                self.seq.event_output(event, port=self.port)
            self.seq.drain_output()

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

