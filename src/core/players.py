"""Async MIDI playback helpers for note and chord scheduling."""

import asyncio
import mido
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Control messages
# ---------------------------------------------------------------------------

async def send_cc(
    queue: Optional[asyncio.Queue],
    control: int,
    value: int,
    channel: int = 0,
) -> None:
    """
    Queue a MIDI Control Change (CC) message.

    Args:
        queue (asyncio.Queue): The async MIDI queue to push to.
        control (int): The MIDI controller number (0-127).
        value (int): The controller value (0-127).
        channel (int): MIDI channel (0-indexed).
    """
    if queue is None:
        return
    try:
        msg = mido.Message(
            "control_change",
            control=int(control),
            value=int(value),
            channel=int(channel),
        )
        await queue.put(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Multi-note helpers
# ---------------------------------------------------------------------------

# ------------------------------------------------------------------
# Queue/port send helper
# ------------------------------------------------------------------

async def _send(target: Any, message: mido.Message) -> None:
    """
    Send a MIDI message to a port or an asyncio queue.

    Args:
        target (Any): MIDI output port or asyncio.Queue instance.
        message (mido.Message): Message to send.
    """
    if isinstance(target, asyncio.Queue):
        await target.put(message)
    else:
        target.send(message)

# ------------------------------------------------------------------
# Note playback
# ------------------------------------------------------------------

async def play_note(
    port,
    note,
    velocity,
    duration,
    channel=0,
) -> None:
    """
    Play a single MIDI note.

    Sends a `note_on` message immediately and a `note_off` after `duration`.

    Args:
        port: MIDI output port or queue.
        note: MIDI note number (0-127).
        velocity: MIDI velocity (1-127).
        duration: Note length in seconds.
        channel: MIDI channel (0-15).
    """
    # Note-on immediately, note-off after the requested duration.
    msg_on = mido.Message('note_on', channel=channel, note=note, velocity=velocity)
    msg_off = mido.Message('note_off', channel=channel, note=note, velocity=velocity)
    await _send(port, msg_on)
    try:
        await asyncio.sleep(duration)
    finally:
        await _send(port, msg_off)

# ------------------------------------------------------------------
# Ratchet playback
# ------------------------------------------------------------------

async def play_ratchet(
    port,
    note,
    velocity,
    total_duration,
    subdivisions=3,
    channel=0,
) -> None:
    """
    Play a ratcheted note burst.

    Args:
        port: MIDI output port or queue.
        note: MIDI note number (0-127).
        velocity: MIDI velocity (1-127).
        total_duration: Total ratchet duration in seconds.
        subdivisions: Number of sub-hits within the duration.
        channel: MIDI channel (0-15).
    """
    # Split the duration into even subdivisions for the ratchet burst.
    sub = total_duration / max(1, subdivisions)
    for _ in range(subdivisions):
        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=velocity))
        await asyncio.sleep(sub * 0.4)
        await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=velocity))
        await asyncio.sleep(sub * 0.6)

# ------------------------------------------------------------------
# Chord playback
# ------------------------------------------------------------------

async def play_chord(
    port,
    chord_notes,
    velocity,
    duration,
    channel=0,
) -> None:
    """
    Play a chord by sending simultaneous `note_on` messages.

    Args:
        port: MIDI output port or queue.
        chord_notes: Iterable of MIDI note numbers.
        velocity: MIDI velocity (1-127).
        duration: Chord length in seconds.
        channel: MIDI channel (0-15).
    """
    # Send all note-on messages first to form a chord.
    for note in chord_notes:
        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=velocity))
    try:
        await asyncio.sleep(duration)
    finally:
        # Always release notes, even if the sleep is interrupted.
        for note in chord_notes:
            await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=velocity))

# ------------------------------------------------------------------
# Arpeggio playback
# ------------------------------------------------------------------

async def play_arpeggio(
    port,
    notes,
    velocity,
    total_duration,
    channel=1,
) -> None:
    """
    Play an arpeggio by sequencing note on/off events.

    Args:
        port: MIDI output port or queue.
        notes: Iterable of MIDI note numbers.
        velocity: MIDI velocity (1-127).
        total_duration: Total arpeggio duration in seconds.
        channel: MIDI channel (0-15).
    """
    # Each note gets an equal slice of the total duration.
    step = total_duration / max(1, len(notes))
    for n in notes:
        await _send(port, mido.Message('note_on', channel=channel, note=n, velocity=velocity))
        await asyncio.sleep(step)
        await _send(port, mido.Message('note_off', channel=channel, note=n, velocity=0))