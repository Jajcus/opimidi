
from evdev import ecodes

import logging

from .alsa import seq
from .config import Config
from .input import EventHandler, make_devices
from .util import run_async_jobs
from . import ops
from .ops import eval_ops

logger = logging.getLogger("midi_sender")

MIDI_DEST = "f_midi"

INPUTS = {
        "button_A": (ecodes.EV_KEY, ecodes.BTN_0),
        "button_B": (ecodes.EV_KEY, ecodes.BTN_1),
        "pedal_1": (ecodes.EV_ABS, 0),
        "pedal_2": (ecodes.EV_ABS, 1),
        }

DEMO_EVENT_MAP = {
        (ecodes.EV_KEY, ecodes.BTN_1): [ops.ControlChange(80),],
        (ecodes.EV_KEY, ecodes.BTN_2): [ops.ControlChange(81),],
        (ecodes.EV_ABS, 0): [ops.ControlChange(4),],
        (ecodes.EV_ABS, 1): [ops.ControlChange(1),],
        }

class MIDISender(EventHandler):
    def __init__(self, config, event_map=None):
        self.config = config
        self.leave_ops = []
        self.program = None
        if event_map:
            self.event_map = event_map
        else:
            self.event_map = {}
        self.seq = seq.SeqClient("opimidi_be")
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
            message = op.midi_message(value)
            if not message:
                continue
            logger.debug("  sending message: %r", message)
            for event in message:
                self.seq.event_output(event, port=self.port)
            self.seq.drain_output()

    def handle_event(self, event):
        logger.debug("incoming event: %r", event)
        try:
            ops = self.event_map.get((event.type, event.code))
            if not ops:
                logger.debug("  no MIDI operators for that")
                return
            self.apply_ops(ops, event.value)
        except Exception as err:
            logger.error("Error while handling event: %s", err, exc_info=True)

    def set_program(self, bank_n, prog_n):
        logger.debug("Switching to program %s:%s", bank_n, prog_n)
        program = self.config.get_program(bank_n, prog_n)
        self.leave_ops = []
        if not self.program or program.bank != self.program.bank:
            logger.debug("Switching bank")
            if "enter" in program.bank:
                enter_ops = eval_ops(program.bank["enter"])
                self.apply_ops(enter_ops)
            if "leave" in program.bank:
                self.leave_ops = eval_ops(program.bank["leave"])
        if "enter" in program:
            enter_ops = eval_ops(program["enter"])
            self.apply_ops(enter_ops)
        if "leave" in program:
            self.leave_ops = eval_ops(program["leave"]) + self.leave_ops
        self.event_map = {}
        for key, event in INPUTS.items():
            try:
                ops_s = program[key]
            except KeyError:
                continue
            self.event_map[event] = eval_ops(ops_s)
        logger.debug("Event map: %r", self.event_map)
        self.program = program

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config = Config()
    midi_sender = MIDISender(config, DEMO_EVENT_MAP)
    jobs = []
    for device in make_devices():
        jobs.append(device.collect_events(midi_sender))
    run_async_jobs(jobs)

