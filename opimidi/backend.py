
import argparse
import asyncio
from functools import partial
import logging
import os
import signal

from .comm import CommProtocol
from .config import Config
from .input import EventHandler, make_devices
from .midi_sender import MIDISender
from .util import abort, signal_handler

logger = logging.getLogger("main")

SOCKET_DIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
BACKEND_SOCKET = os.path.join(SOCKET_DIR, "opimidi.sock")

class BackendEventHandler(EventHandler):
    def __init__(self, midi_sender):
        self.midi_sender = midi_sender
        self.subscribers = {}
    def handle_event(self, event):
        used = False
        for client, subscriptions in self.subscribers.items():
            if (event.type, event.code) in subscriptions:
                client.send_frame([["input_event"] + list(event)])
                used = True
        if not used:
            self.midi_sender.handle_event(event)

class BackendProtocol(CommProtocol):
    def __init__(self, loop, event_handler):
        self.event_handler = event_handler
        self.midi_sender = event_handler.midi_sender
        CommProtocol.__init__(self, loop)

    def cmd_set_subscribed_events(self, events):
        events = set((t, v) for t, v in events)
        self.event_handler.subscribers[self] = events
        logger.debug("Event subscription changed: %r", events)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        try:
            del self.event_handler.subscribers[self]
        except KeyError:
            pass

    def cmd_set_program(self, bank_n, prog_n):
        self.midi_sender.set_program(bank_n, prog_n)

def main():
    parser = argparse.ArgumentParser(description="OPiMIDI back-end")
    parser.add_argument("--debug", dest="log_level",
                        action="store_const", const=logging.DEBUG,
                        help="Enable debug logging")
    parser.set_defaults(log_level=logging.INFO)
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler, loop)
    loop.add_signal_handler(signal.SIGTERM, signal_handler, loop)
    try:
        config = Config()
        midi_sender = MIDISender(config)
        event_handler = BackendEventHandler(midi_sender)
        logger.debug("Creating backend socket...")
        try:
            proto_f = partial(BackendProtocol, loop, event_handler)
            create_server = loop.create_unix_server(proto_f, BACKEND_SOCKET)
            server = loop.run_until_complete(create_server)
        except OSError as err:
            logger.error("Could create server: %s", err)
            return
        try:
            jobs = []
            for device in make_devices():
                jobs.append(device.collect_events(event_handler))
            loop.run_until_complete(asyncio.wait(jobs))
        finally:
            server.close()
            try:
                os.unlink(BACKEND_SOCKET)
            except OSError:
                pass
            loop.run_until_complete(server.wait_closed())
    except asyncio.CancelledError:
        loop.run_until_complete(asyncio.wait(asyncio.Task.all_tasks()))
    finally:
        logger.debug("Cleaning up...")
        loop.close()

if __name__ == "__main__":
    main()
