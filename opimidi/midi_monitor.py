
import asyncio
import logging

from .alsa import seq

from .ops import eval_ops

logger = logging.getLogger("midi_monitor")


MONITOR_SETTINGS = [ 
        ("pedal_1", "1"),
        ("pedal_2", "2"),
        ("button_A", "A"),
        ("button_B", "B"),
        ]


BUTTON_MONITORS = {"A", "B"}

class MIDIMonitor:
    def __init__(self, ui):
        self.loop = asyncio.get_event_loop()
        self.ui = ui

        # name -> controller number
        self.monitors = {}
        # controller number -> monitor
        self.monitors_rev = {}
        # name -> 0-7 value
        self.monitor_values = {}
        # controller number -> float value 
        self.midi_controls = {}

        self.pending_changes = {}

        self.seq = seq.Client("opimidi_ui")
        self.seq_port = self.seq.create_port("in",
                                seq.PORT_CAP_WRITE | seq.PORT_CAP_SUBS_WRITE,
                                seq.PORT_TYPE_MIDI_GENERIC)
        try:
            be_client, be_port = self.seq.parse_address("opimidi_be")
            self.seq.connect_from(self.seq_port, be_client, be_port)
        except (OSError, seq.SeqError) as err:
            logger.debug("could not connect to opimidi_be: %s", err)

        self.seq.asyncio_subscribe_events(self.loop, self.handle_midi_event)

    def set_program(self, program):
        logger.debug("Setting program to %r", program)
        for handle in self.pending_changes.items():
            handle.cancel()
        self.pending_changes = {}
        self.monitors = {}
        self.monitors_rev = {}
        all_monitors = set()
        for key, monitor in MONITOR_SETTINGS:
            all_monitors.add(monitor)
            try:
                ops_s = program[key]
            except KeyError:
                continue
            ops = eval_ops(ops_s)
            if not ops:
                continue
            logger.debug("   monitor %r: %r", monitor, ops)
            for op in ops:
                event = op.monitored_event()
                if not event:
                    continue
                if not isinstance(event, seq.ControlChangeEvent):
                    logger.warning("%r monitoring not supported",
                                   event.__class__.__name__)
                    continue
                break
            else:
                logger.debug("        ...not something we can monitor")
                continue
            self.monitors[monitor] = event.param
            self.monitors_rev[event.param] = monitor
            logger.debug("   monitor %r: CC %r", monitor, event.param)
        # load current values for all monitors
        for monitor in all_monitors:
            try:
                control = self.monitors[monitor]
                value = self.midi_controls[control]
            except KeyError:
                value = None
            self.set_monitor(monitor, value)

    def handle_midi_event(self, event):
        if isinstance(event, seq.ControlChangeEvent):
            self.handle_midi_cc(event)
        else:
            logger.debug("Unknown event: %r", event)

    def handle_midi_cc(self, event):
        control = event.param
        value = event.value / 127.0
        self.midi_controls[control] = value
        monitor = self.monitors_rev.get(control)
        if not monitor:
            logger.debug("CC: %r=%r, not monitored", control, value)
            return
        logger.debug("CC: %r=%r updating monitor", control, value)
        self.set_monitor(monitor, value)

    def set_monitor(self, monitor, value):
        if value is None:
            mon_value = None
        elif monitor in BUTTON_MONITORS:
            # looks better when not displaying full range
            if value > 0.5:
                mon_value = 6
            else:
                mon_value = 3
        else:
            mon_value = round(value * 7)
        if mon_value == self.monitor_values.get(monitor):
            logger.debug("  monitor value = %r (no change)", mon_value)
            return
        logger.debug("  monitor value = %r", mon_value)
        self.monitor_values[monitor] = mon_value
        handle = self.loop.call_later(0.01, self.update_monitor, monitor)
        if monitor not in self.pending_changes:
            logger.debug("  scheduling UI update")
            self.pending_changes[monitor] = handle

    def update_monitor(self, monitor):
        try:
            del self.pending_changes[monitor]
        except KeyError:
            pass
        self.ui.set_monitor(monitor, self.monitor_values[monitor])
