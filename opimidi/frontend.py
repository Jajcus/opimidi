
import argparse
import asyncio
from functools import partial
import logging
import os
import signal

from .input import InputEvent
from .ui import OpimidiUI
from .util import abort, signal_handler
from .comm import CommProtocol

logger = logging.getLogger("main")

SOCKET_DIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
BACKEND_SOCKET = os.path.join(SOCKET_DIR, "opimidi.sock")

class FrontendProtocol(CommProtocol):
    def __init__(self, loop):
        CommProtocol.__init__(self, loop)
        self.ui = None
    def cmd_input_event(self, timestamp, type, code, value, timedelta):
        event = InputEvent(timestamp, type, code, value, timedelta)
        if self.ui:
            self.ui.handle_event(event)

def main():
    parser = argparse.ArgumentParser(description="OPiMIDI")
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
        logger.debug("Connecting to the backend...")
        try:
            proto_f = partial(FrontendProtocol, loop)
            connect = loop.create_unix_connection(proto_f, BACKEND_SOCKET)
            transport, protocol = loop.run_until_complete(connect)
        except OSError as err:
            logger.error("Could not connect to the backend: %s", err)
            return
        ui = OpimidiUI(protocol)
        loop.run_until_complete(ui.run())
        transport.abort()
    except asyncio.CancelledError:
        loop.run_until_complete(asyncio.wait(asyncio.Task.all_tasks()))
    finally:
        loop.close()

if __name__ == "__main__":
    main()
