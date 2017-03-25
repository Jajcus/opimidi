#!/usr/bin/python3

import asyncio
import errno
import logging
import time

from opimidi.alsa import seq

logging.basicConfig(level=logging.DEBUG)

client = seq.Client("dump_events")
port = client.create_port("port 1",
                            seq.PORT_CAP_WRITE | seq.PORT_CAP_SUBS_WRITE,
                            seq.PORT_TYPE_MIDI_GENERIC)

print("Client: {!r} Port: {!r}".format(client, port))

try:
    playmidi_client, playmidi_port = client.parse_address("aplaymidi")
    client.connect_from(port, playmidi_client, playmidi_port)
except (OSError, seq.SeqError) as err:
    print("could not connect from aplaymidi: {}".format(err))

def callback(event):
    print(repr(event))

print("Now waiting for events:")
loop = asyncio.get_event_loop()
client.asyncio_subscribe_events(loop, callback)
loop.run_forever()

