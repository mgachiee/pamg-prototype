import asyncio
import pytest

from src.core.midi_events import normalize_event
from src.core.midi_io import close_midi_ports
from src.core.players import play_note, play_ratchet, play_arpeggio, silence_all_notes


def test_normalize_event_clamping():
    # Out of range high note
    ev_high = normalize_event(
        {"note": 150, "velocity": 200, "channel": 20},
        default_channel=0,
        default_duration=0.5,
    )
    assert ev_high.note == 127
    assert ev_high.velocity == 127
    assert ev_high.channel == 15

    # Out of range low note
    ev_low = normalize_event(
        {"note": -10, "velocity": -5, "channel": -1},
        default_channel=0,
        default_duration=0.5,
    )
    assert ev_low.note == 0
    assert ev_low.velocity == 1
    assert ev_low.channel == 0


def test_normalize_event_invalid_duration():
    # Negative duration falls back to default_duration
    ev_neg = normalize_event(
        {"note": 60, "velocity": 64, "duration": -1.0},
        default_channel=0,
        default_duration=0.5,
    )
    assert ev_neg.duration == 0.5

    # NaN duration falls back to default_duration
    ev_nan = normalize_event(
        {"note": 60, "velocity": 64, "duration": float("nan")},
        default_channel=0,
        default_duration=0.5,
    )
    assert ev_nan.duration == 0.5


def test_close_midi_ports_idempotency(dummy_port):
    # Pass same port twice
    close_midi_ports(dummy_port, dummy_port)
    assert dummy_port.closed is True
    # Call again should not raise
    close_midi_ports(dummy_port)


def test_players_note_off_safety_on_cancellation(dummy_port):
    async def _run():
        task = asyncio.create_task(
            play_note(dummy_port, note=60, velocity=100, duration=1.0)
        )
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())
    # Verify both note_on and note_off were sent despite cancellation
    types = [msg.type for msg in dummy_port.messages]
    assert "note_on" in types
    assert "note_off" in types


def test_players_ratchet_note_off_safety(dummy_port):
    async def _run():
        task = asyncio.create_task(
            play_ratchet(dummy_port, note=38, velocity=100, total_duration=0.5, subdivisions=2)
        )
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())
    types = [msg.type for msg in dummy_port.messages]
    assert "note_on" in types
    assert "note_off" in types


def test_players_ratchet_crescendo_velocity(dummy_port):
    """Verify crescendo=True causes subdivision velocities to ramp from p to f."""
    async def _run():
        await play_ratchet(dummy_port, note=45, velocity=100, total_duration=0.1, subdivisions=4, crescendo=True)

    asyncio.run(_run())
    note_ons = [msg for msg in dummy_port.messages if msg.type == "note_on"]
    assert len(note_ons) == 4
    velocities = [msg.velocity for msg in note_ons]

    # Verify first stroke starts soft (~30) and final stroke reaches target (100)
    assert velocities[0] == 30
    assert velocities[-1] == 100
    assert velocities == sorted(velocities)
    assert len(set(velocities)) == 4


def test_silence_all_notes(dummy_port):
    """Verify silence_all_notes sends pedal release and all notes/sound off."""
    asyncio.run(silence_all_notes(dummy_port, channels=[0, 1]))

    ccs = [(m.channel, m.control, m.value) for m in dummy_port.messages if m.type == "control_change"]
    # Channel 0
    assert (0, 64, 0) in ccs   # Sustain pedal release
    assert (0, 66, 0) in ccs   # Sostenuto release
    assert (0, 123, 0) in ccs  # All Notes Off
    assert (0, 120, 0) in ccs  # All Sound Off

    # Channel 1
    assert (1, 64, 0) in ccs
    assert (1, 66, 0) in ccs
    assert (1, 123, 0) in ccs
    assert (1, 120, 0) in ccs


def test_close_midi_ports_sends_panic(dummy_port):
    """Verify close_midi_ports dispatches panic controllers before closing."""
    close_midi_ports(dummy_port)
    assert dummy_port.closed is True
    ccs = [(m.channel, m.control, m.value) for m in dummy_port.messages if m.type == "control_change"]
    assert (0, 64, 0) in ccs
    assert (0, 123, 0) in ccs
