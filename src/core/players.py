import asyncio
import mido
from typing import Any

async def _send(target: Any, message: mido.Message):
    if isinstance(target, asyncio.Queue):
        await target.put(message)
    else:
        target.send(message)

async def play_note(port, note, velocity, duration, channel=0):
    msg_on = mido.Message('note_on', channel=channel, note=note, velocity=velocity)
    msg_off = mido.Message('note_off', channel=channel, note=note, velocity=velocity)
    await _send(port, msg_on)
    try:
        await asyncio.sleep(duration)
    finally:
        await _send(port, msg_off)

async def play_ratchet(port, note, velocity, total_duration, subdivisions=3, channel=0):
    sub = total_duration / max(1, subdivisions)
    for _ in range(subdivisions):
        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=velocity))
        await asyncio.sleep(sub * 0.4)
        await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=velocity))
        await asyncio.sleep(sub * 0.6)

async def play_chord(port, chord_notes, velocity, duration, channel=0):
    for note in chord_notes:
        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=velocity))
    try:
        await asyncio.sleep(duration)
    finally:
        for note in chord_notes:
            await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=velocity))

async def play_arpeggio(port, notes, velocity, total_duration, channel=1):
    step = total_duration / max(1, len(notes))
    for n in notes:
        await _send(port, mido.Message('note_on', channel=channel, note=n, velocity=velocity))
        await asyncio.sleep(step)
        await _send(port, mido.Message('note_off', channel=channel, note=n, velocity=0))