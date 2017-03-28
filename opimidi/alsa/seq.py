
import logging
import errno

from functools import partial

from . import _seq
from ._seq import *

logger = logging.getLogger("alsa.seq")

class Client(_seq.SeqClient):
    __slots__ = ()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_classes.update(EVENT_CLASS_MAP)

    def asyncio_subscribe_events(self, loop, callback):
        loop.add_reader(self.fileno(), partial(self._incoming, callback))

    def _incoming(self, callback):
        logger.debug("   input pending")
        while True:
            try:
                event = self.event_input()
            except OSError as err:
                if err.errno == errno.ENOSPC:
                    logger.warning("Input queue overflow, events lost")
                elif err.errno == errno.EAGAIN:
                    logger.debug("   no more events pending")
                    break
                elif err.errno == errno.EINTR:
                    logger.debug("   EINTR")
                    continue
                else:
                    raise
            logger.debug("   got event: %r:", event)
            callback(event)

class SeqEvent(_seq.SeqEvent):
    __slots__ = ()
    def _repr(self, details):
        if (self.flags & TIME_STAMP_MASK) == TIME_STAMP_TICK:
            ts_prefix = "@#"
            ts_val = self.tick
            ts_val_s = str(ts_val)
        else:
            ts_prefix = "@"
            ts_val = self.tv_sec + 0.000000001 * self.tv_nsec
            ts_val_s = "{:.3}".format(ts_val)

        if (self.flags & TIME_MODE_MASK) == TIME_MODE_REL and ts_val > 0:
            ts_prefix += "+"

        return ("<{0.__class__.__name__} {1} {2}"
                " from {0.source_client}:{0.source_port}"
                " to {0.dest_client}:{0.dest_port}"
                ">".format(self, details, ts_prefix + ts_val_s))

    def __repr__(self):
        return self._repr(self.type)

class NoteEvent(_seq.SeqNoteEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self,
            "#{0.note} velocity={0.velocity} duration={0.duration}"
            .format(self))

class NoteOnEvent(_seq.SeqNoteOnEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self,
            "#{0.note} velocity={0.velocity}"
            .format(self))

class NoteOffEvent(_seq.SeqNoteOffEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self,
            "#{0.note} velocity={0.velocity}"
            .format(self))

class ControlChangeEvent(_seq.SeqControlChangeEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self,
            "#{0.param} value={0.value}"
            .format(self))

class ControlChange14bitEvent(_seq.SeqControlChange14bitEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self,
            "#{0.param} value={0.value}"
            .format(self))

class ProgramChangeEvent(_seq.SeqProgramChangeEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self,
            "#{0.value}"
            .format(self))

class _AddressEvent(_seq.SeqAddressEvent):
    __slots__ = ()
    def __repr__(self):
        return SeqEvent._repr(self, "{0.client}:{0.port}" .format(self))

class ClientStartEvent(_AddressEvent):
    __slots__ = ()
    def __init__(self, client=0, port=0, **kwargs):
        super().__init__(EVENT_CLIENT_START, client, port, **kwargs)

class ClientExitEvent(_AddressEvent):
    __slots__ = ()
    def __init__(self, client=0, port=0, **kwargs):
        super().__init__(EVENT_CLIENT_EXIT, client, port, **kwargs)

class ClientChangeEvent(_AddressEvent):
    __slots__ = ()
    def __init__(self, client=0, port=0, **kwargs):
        super().__init__(EVENT_CLIENT_CHANGE, client, port, **kwargs)

class PortStartEvent(_AddressEvent):
    __slots__ = ()
    def __init__(self, client=0, port=0, **kwargs):
        super().__init__(EVENT_PORT_START, client, port, **kwargs)

class PortExitEvent(_AddressEvent):
    __slots__ = ()
    def __init__(self, client=0, port=0, **kwargs):
        super().__init__(EVENT_PORT_EXIT, client, port, **kwargs)

class PortChangeEvent(_AddressEvent):
    __slots__ = ()
    def __init__(self, client=0, port=0, **kwargs):
        super().__init__(EVENT_PORT_CHANGE, client, port, **kwargs)

EVENT_CLASS_MAP = {
        None: SeqEvent, # default
        EVENT_NOTE: NoteEvent,
        EVENT_NOTEON: NoteOnEvent,
        EVENT_NOTEOFF: NoteOffEvent,
        EVENT_CONTROLLER: ControlChangeEvent,
        EVENT_CONTROL14: ControlChange14bitEvent,
        EVENT_PGMCHANGE: ProgramChangeEvent,
        EVENT_CLIENT_START: ClientStartEvent,
        EVENT_CLIENT_EXIT: ClientExitEvent,
        EVENT_CLIENT_CHANGE: ClientChangeEvent,
        EVENT_PORT_START: PortStartEvent,
        EVENT_PORT_EXIT: PortExitEvent,
        EVENT_PORT_CHANGE: PortChangeEvent,
        }
