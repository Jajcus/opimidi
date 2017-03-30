
import logging

from .alsa import seq

logger = logging.getLogger("ops")

class ProgramOp:
    def monitored_event(self, value):
        """Event to monitor for this op."""
        return None

    def current_value(self):
        """Current value, if maintained, None otherwise."""
        return None

    def midi_message(self, value):
        """MIDI message to send for this operator.
        
        value is current value of the input (0.0 - 1.0)."""
        raise NotImplementedError

_CONTROL_VALUES = {}

class ControlChange(ProgramOp):
    def __init__(self, number):
        self.event = seq.ControlChangeEvent(param=number)

    def monitored_event(self):
        return self.event

    def current_value(self):
        return _CONTROL_VALUES.get(self.event.param)

    def midi_message(self, value):
        _CONTROL_VALUES[self.event.param] = value
        # one byte precision
        midi_val = round(value * 127) & 0x7f
        self.event.value = midi_val
        return [self.event]

    def __repr__(self):
        return "ControlChange({!r})".format(self.event.param)

class BankSelect(ProgramOp):
    def __init__(self, bank_number):
        if bank_number < 1 or bank_number > 16384:
            raise ValueEror("Invalid bank number")
        midi_val = bank_number - 1
        self.event = seq.ControlChange14btEvent(param=0, value=midi_val)

    def monitored_event(self):
        return self.event

    def midi_message(self, value):
        if value > 0.5:
            return [self.event]
        else:
            return []

    def __repr__(self):
        return "ControlChange({!r})".format(self.event.value + 1)

class ProgramChange(ProgramOp):
    def __init__(self, program_number):
        if program_number < 1 or program_number > 128:
            raise ValueEror("Invalid program number")
        self.event = seq.ProgramChangeEvent(value=program_number-1)

    def midi_message(self, value):
        if value > 0.5:
            return [self.event]
        else:
            return []

    def __repr__(self):
        return "ProgramChange({!r})".format(self.event.value + 1)

class Toggle(ProgramOp):
    def __init__(self, op, hist_low=0.4, hist_high=0.5):
        if not isinstance(op, ProgramOp):
            raise TypeError("Argument must be ProgramOp")
        self.hist_low = hist_low
        self.hist_high = hist_high
        self.on = False
        self.op = op
    def monitored_event(self):
        return self.op.monitored_event()
    def current_value(self):
        return self.op.current_value()
    def midi_message(self, value):
        # input value hysteresis
        last_on = self.on
        if last_on and value < self.hist_low:
            self.on = False
            # only react to raising slope
            return []
        elif not last_on and value > self.hist_high:
            self.on = True
        else:
            # no change
            return []
        prev_op_value = self.op.current_value()
        if prev_op_value is None:
            logger.debug("Setting %r on", self.op)
            return self.op.midi_message(1.0)
        elif prev_op_value > 0.5:
            logger.debug("Toggling %r off", self.op)
            return self.op.midi_message(0.0)
        else:
            logger.debug("Toggling %r on", self.op)
            return self.op.midi_message(1.0)
    def __repr__(self):
        return "Toggle({!r})".format(self.op)

class Set(ProgramOp):
    def __init__(self, op, value=1.0):
        if not isinstance(op, ProgramOp):
            raise TypeError("First Set() argument must be ProgramOp")
        self.op = op
        self.value = value
    def monitored_event(self):
        return self.op.monitored_event()
    def current_value(self):
        return self.op.current_value()
    def midi_message(self, value):
        if value > 0.5:
            return self.op.midi_message(self.value)
        else:
            return []
    def __repr__(self):
        return "Set({!r},{!r})".format(self.op, self.value)


OP_ALLOWED = ["ControlChange", "BankSelect", "ProgramChange", "Toggle", "Set"]
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
