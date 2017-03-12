
import asyncio
import logging
import json

logger = logging.getLogger("comm")

class CommProtocol(asyncio.Protocol):
    def __init__(self, loop, connection_list=None):
        logger.debug('Creating CommProtocol')
        self.loop = loop
        self.transport = None
        self.connection_list = connection_list
        self._frame_buf = bytes()

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        logger.debug('Connection with %s', peername)
        self.transport = transport
        if self.connection_list is not None:
            self.connection_list.append(self)

    def connection_lost(self, exc):
        logger.debug('Connection lost')
        if self.connection_list:
            try:
                self.connection_list.remove(self)
            except ValueError:
                pass

    def data_received(self, data):
        message = data.decode()
        logger.debug('Data received: %r', message)
        while data:
            if 0 in data:
                head, data = data.split(b"\x00", 1)
                frame = self._frame_buf + head
                self._frame_buf = data
                decoded = json.loads(frame.decode("utf-8"))
                self.frame_received(decoded)
            else:
                self._frame_buf += data
                return

    def frame_received(self, frame):
        logger.debug("Frame received: %r", frame)
        for command in frame:
            cmd_name = command[0]
            args = command[1:]
            meth_name = "cmd_" + cmd_name
            meth = getattr(self, meth_name, None)
            if meth:
                meth(*args)
            else:
                logger.debug("Unknown command received: %r", command)

    def send_frame(self, frame):
        logger.debug("Sending frame: %r", frame)
        encoded = json.dumps(frame).encode("utf-8")
        self.transport.write(encoded + b'\x00')

