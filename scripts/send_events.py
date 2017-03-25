#!/usr/bin/python3

import errno
import time

from opimidi.alsa import seq

client = seq.Client("my client")
queue = client.create_queue("my queue")
port = client.create_port("port 1",
                            seq.PORT_CAP_READ | seq.PORT_CAP_SUBS_READ
                            | seq.PORT_CAP_WRITE | seq.PORT_CAP_SUBS_WRITE,
                            seq.PORT_TYPE_MIDI_GENERIC)

print("Client: {!r} Queue: {!r} Port: {!r}".format(client, queue, port))
print("FD: {!r}".format(client.fileno()))

try:
    dump_client, dump_port = client.parse_address("aseqdump")
except (OSError, seq.SeqError) as err:
    dump_client, dump_port = (129, 0)
    print("could not parse 'aseqdump':", err)

try:
    client.connect_to(port, dump_client, dump_port)
except (OSError, seq.SeqError) as err:
    print("could not connect to {}:{}: {}".format(dump_client, dump_port, err))


note = seq.NoteOnEvent()
note.note = 62
note.velocity = 63

print("Note: {!r}".format(note))

input("Press enter to send")

client.start_queue(queue)
client.drain_output()

res = client.event_output(note, port=port)
print(res)
client.drain_output()

time.sleep(1)

note = seq.NoteOffEvent(note=62, velocity=1, dest_port=port)
print("Note: {!r}".format(note))
res = client.event_output(note)
print(res)
client.drain_output()

time.sleep(1)

note = seq.NoteEvent(note=66,velocity=100,duration=100)
print("Note: {!r}".format(note))
res = client.event_output(note, port=port, queue=queue)
print(res)
client.drain_output()

note = seq.NoteEvent(note=67,velocity=100,duration=100)
print("Note: {!r}".format(note))
res = client.event_output(note, port=port, queue=queue)
print(res)
client.drop_output()
client.drain_output()

cc = seq.ControlChangeEvent(channel=3,param=60, value=66)
print("CC: {!r}".format(cc))
res = client.event_output(cc, port=port)
print(res)
client.drain_output()
