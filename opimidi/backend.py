
import argparse
import asyncio
from functools import partial
import logging
import os
import signal

from .comm import CommProtocol
from .input import EventHandler, make_devices
from .midi_sender import MIDISender
from .util import abort, signal_handler

logger = logging.getLogger("main")

SOCKET_DIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
BACKEND_SOCKET = os.path.join(SOCKET_DIR, "opimidi.sock")

class BackendEventHandler(EventHandler):
    def __init__(self, midi_sender, connections):
        self.midi_sender = midi_sender
        self.connections = connections
    def handle_event(self, event):
        self.midi_sender.handle_event(event)
        for client in self.connections:
            client.send_frame([["input_event"] + list(event)])

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
        logger.debug("Creating backend socket...")
        try:
            connections = []
            proto_f = partial(CommProtocol, loop, connections)
            create_server = loop.create_unix_server(proto_f, BACKEND_SOCKET)
            server = loop.run_until_complete(create_server)
        except OSError as err:
            logger.error("Could create server: %s", err)
            return
        try:
            midi_sender = MIDISender()
            event_handler = BackendEventHandler(midi_sender, connections)
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
