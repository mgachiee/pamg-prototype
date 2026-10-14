"""Async MIDI playback helpers for note and chord scheduling."""

import asyncio
import mido
from typing import Any, Optional


from src.core.logger import Logger

logger = Logger()


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
    except Exception as e:
        logger.debug(f"send_cc failed: {e}")


async def silence_all_notes(
    queue_or_port: Any,
    channels: Optional[list[int]] = None,
) -> None:
    """
    Send MIDI Panic / Silence across specified channels (or all 16 channels).
    Releases sustain and sostenuto pedals (CC 64, CC 66), sends All Notes Off (CC 123),
    All Sound Off (CC 120), and Reset All Controllers (CC 121).

    Args:
        queue_or_port: The MIDI queue or port to send through.
        channels: Optional list of channels. If None, targets all channels 0-15.
    """
    if queue_or_port is None:
        return

    if channels is None:
        channels = list(range(16))

    for ch in channels:
        try:
            # 1. Damper / Sustain Pedal Off (CC 64 = 0)
            await _send(queue_or_port, mido.Message("control_change", channel=ch, control=64, value=0))
            # 2. Sostenuto Pedal Off (CC 66 = 0)
            await _send(queue_or_port, mido.Message("control_change", channel=ch, control=66, value=0))
            # 3. All Notes Off (CC 123 = 0)
            await _send(queue_or_port, mido.Message("control_change", channel=ch, control=123, value=0))
            # 4. All Sound Off (CC 120 = 0)
            await _send(queue_or_port, mido.Message("control_change", channel=ch, control=120, value=0))
        except Exception as e:
            logger.debug(f"silence_all_notes failed on channel {ch}: {e}")


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
    msg_off = mido.Message('note_off', channel=channel, note=note, velocity=0)
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
    crescendo=False,
) -> None:
    """
    Play a ratcheted note burst or orchestral drum roll with guaranteed note-off safety.

    Args:
        port: MIDI output port or queue.
        note: MIDI note number (0-127).
        velocity: MIDI target velocity (1-127).
        total_duration: Total ratchet duration in seconds.
        subdivisions: Number of sub-hits within the duration.
        channel: MIDI channel (0-15).
        crescendo: If True, swell velocity from 35% up to 100% across subdivisions.
    """
    # Split the duration into even subdivisions for the ratchet burst.
    sub = total_duration / max(1, subdivisions)
    for i in range(subdivisions):
        if crescendo and subdivisions > 1:
            factor = 0.30 + 0.70 * ((i / (subdivisions - 1)) ** 1.2)
            stroke_vel = max(1, min(127, int(round(velocity * factor))))
        else:
            stroke_vel = velocity

        await _send(port, mido.Message('note_on', channel=channel, note=note, velocity=stroke_vel))
        try:
            await asyncio.sleep(sub * 0.85 if crescendo else sub * 0.4)
        finally:
            await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=0))
        await asyncio.sleep(sub * 0.15 if crescendo else sub * 0.6)

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
            await _send(port, mido.Message('note_off', channel=channel, note=note, velocity=0))

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
    Play an arpeggio by sequencing note on/off events with note-off safety.

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
        try:
            await asyncio.sleep(step)
        finally:
            await _send(port, mido.Message('note_off', channel=channel, note=n, velocity=0))