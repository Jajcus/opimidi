#!/usr/bin/python3

import time
from opimidi.alsa import seq

client = seq.SeqClient("my client")
queue = client.create_queue("my queue")
port = client.create_port("port 1", seq.PORT_CAP_READ|seq.PORT_CAP_SUBS_READ, seq.PORT_TYPE_MIDI_GENERIC)

print("Client: {!r} Queue: {!r} Port: {!r}".format(client, queue, port))

try:
    dump_addr, dump_port = client.parse_address("aseqdump")
except RuntimeError as err:
    dump_addr, dump_port = (129, 0)
    print("could not pares 'aseqdump':", err)

try:
    client.connect_to(port, dump_addr, dump_port)
except RuntimeError as err:
    print("could not connect to {}:{}: {!r}".format(dump_addr, dump_port, err))


note = seq.SeqNoteOnEvent()
note.note = 62
note.velocity = 63

print("Note: {!r}".format(note))

input("Press enter to send")

client.start_queue(queue)
client.drain_output()

client.event_output(note, port=port)
client.drain_output()

time.sleep(1)

note = seq.SeqNoteOffEvent(note=62, velocity=1, dest_port=port)
client.event_output(note)
client.drain_output()

time.sleep(1)

note = seq.SeqNoteEvent(note=66,velocity=100,duration=100)
client.event_output(note, port=port, queue=queue)
client.drain_output()

note = seq.SeqNoteEvent(note=67,velocity=100,duration=100)
client.event_output(note, port=port, queue=queue)
client.drop_output()
client.drain_output()

cc = seq.SeqControlChangeEvent(channel=3,param=60, value=66)
client.event_output(cc, port=port)
client.drain_output()
