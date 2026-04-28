import asyncio
import mido
from typing import Any

async def _send(target: Any, message: mido.Message):
    """
    Sends a MIDI message to the specified target, which can be either a mido output port or an asyncio.Queue.

    Args:
        target: The MIDI output port or asyncio.Queue to send the message to.
        message: The mido.Message to be sent.
    """
    if isinstance(target, asyncio.Queue):
        await target.put(message)
    else:
        target.send(message)

async def play_note(port, note, velocity, duration, channel=0):
    """
    Plays a single MIDI note by sending a 'note_on' message followed by a 'note_off' message after the specified duration.

    Args:
        port: The MIDI output port to send the messages to.
        note: The MIDI note number to play.
        velocity: The velocity of the note (1-127).
        duration: The duration in seconds to hold the note before sending the 'note_off' message.
        channel: The MIDI channel to use (0-15).
    """
    msg_on = mido.Message('note_on', channel=channel, note=note, velocity=velocity)
    msg_off = mido.Message('note_off', channel=channel, note=note, velocity=velocity)
    await _send(port, msg_on)
    try:
        await asyncio.sleep(duration)
    finally:
        await _send(port, msg_off)

async def play_ratchet(port, note, velocity, total_duration, subdivisions=3, channel=0):
    """
    Plays a ratchet pattern by sending rapid 'note_on' and 'note_off' messages.

    Args:
        port: The MIDI output port to send the messages to.
        note: The MIDI note number to play.
        velocity: The velocity of the note (1-127).
        total_duration: The total duration in seconds for the ratchet pattern.
        subdivisions: The number of subdivisions within the total duration.
        channel: The MIDI channel to use (0-15).
    """
    sub = total_duration / max(1, subdivisions)
    for _ in range(subdivisions):
        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=velocity))
        await asyncio.sleep(sub * 0.4)
        await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=velocity))
        await asyncio.sleep(sub * 0.6)

async def play_chord(port, chord_notes, velocity, duration, channel=0):
    """
    Plays a chord by sending simultaneous 'note_on' messages.

    Args:
        port: The MIDI output port to send the messages to.
        chord_notes: A list of MIDI note numbers to play simultaneously.
        velocity: The velocity of the notes (1-127).
        duration: The duration in seconds to hold the chord before sending the 'note_off' messages.
        channel: The MIDI channel to use (0-15).
    """
    for note in chord_notes:
        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=velocity))
    try:
        await asyncio.sleep(duration)
    finally:
        for note in chord_notes:
            await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=velocity))

async def play_arpeggio(port, notes, velocity, total_duration, channel=1):
    """
    Plays an arpeggio by sending 'note_on' messages in sequence.
    Args:
        port: The MIDI output port to send the messages to.
        notes: A list of MIDI note numbers to play in sequence.
        velocity: The velocity of the notes (1-127).
        total_duration: The total duration in seconds for the arpeggio.
        channel: The MIDI channel to use (0-15).
    """
    step = total_duration / max(1, len(notes))
    for n in notes:
        await _send(port, mido.Message('note_on', channel=channel, note=n, velocity=velocity))
        await asyncio.sleep(step)
        await _send(port, mido.Message('note_off', channel=channel, note=n, velocity=0))