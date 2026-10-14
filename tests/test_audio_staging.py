"""
Tests for Audio Staging, Freeverb Concert Hall Settings, Master Headroom,
and Soft-Knee Velocity Calibration.
"""

from unittest.mock import MagicMock, patch
import mido
import pytest

from src.core.configs import AUDIO_CONFIG
from src.core.midi_io import NativeFluidSynthPort
from src.modules.orchestrator_agent import OrchestratorAgent


def test_audio_config_specs():
    """Verify AUDIO_CONFIG contains all expected concert hall, gain, and staging parameters."""
    assert AUDIO_CONFIG.get("reverb_enabled") is True
    assert 0.70 <= AUDIO_CONFIG.get("reverb_room_size", 0.0) <= 1.0  # Large concert hall acoustic
    assert 0.0 <= AUDIO_CONFIG.get("reverb_damping", -1.0) <= 1.0
    assert AUDIO_CONFIG.get("reverb_width", 0.0) >= 1.0
    assert 0.0 <= AUDIO_CONFIG.get("reverb_level", -1.0) <= 1.0

    assert 0.40 <= AUDIO_CONFIG.get("master_gain", 0.0) <= 0.85  # Master headroom protection

    assert "channel_volumes" in AUDIO_CONFIG
    vols = AUDIO_CONFIG["channel_volumes"]
    # Melody channels should be in the soloist pocket (~110)
    assert vols.get(0, 0) >= 105
    # Harmony accompaniment should be slightly lower (~95)
    assert vols.get(4, 0) <= vols.get(0, 0)
    # Channel 9 (drums) volume should be configured
    assert 9 in vols

    assert "channel_reverb_sends" in AUDIO_CONFIG
    reverbs = AUDIO_CONFIG["channel_reverb_sends"]
    # High sends for strings/pads/harmony, moderate sends for lead and drums
    assert reverbs.get(0, 0) > 0
    assert reverbs.get(4, 0) >= reverbs.get(1, 0)
    assert reverbs.get(9, 0) > 0

    assert AUDIO_CONFIG.get("velocity_floor", 0) >= 1
    assert AUDIO_CONFIG.get("velocity_ceiling", 0) <= 127
    assert AUDIO_CONFIG.get("velocity_floor", 0) < AUDIO_CONFIG.get("velocity_ceiling", 0)
    assert AUDIO_CONFIG.get("velocity_curve") in ("linear", "soft_knee", "compressed")


def test_orchestrator_initial_cc_queue():
    """Verify OrchestratorAgent queues CC 7 (volume), CC 11 (expression), and CC 91 (reverb) on startup."""
    agent = OrchestratorAgent(
        melody_channels=[0, 1],
        harmony_channels=[2, 3, 4],
        audio_config=AUDIO_CONFIG,
    )

    cc_changes = agent.consume_cc_changes()
    assert len(cc_changes) > 0

    # Ensure CC 91 and CC 7 were queued for lead melody (ch 0) and harmony (ch 2)
    cc_map = {(ch, ctrl): val for (ch, ctrl, val) in cc_changes}

    assert (0, 7) in cc_map
    assert cc_map[(0, 7)] == AUDIO_CONFIG["channel_volumes"].get(0, 100)

    assert (0, 91) in cc_map
    assert cc_map[(0, 91)] == AUDIO_CONFIG["channel_reverb_sends"].get(0, 40)

    assert (2, 7) in cc_map
    assert (2, 91) in cc_map

    # Queue should be empty on subsequent consume
    assert len(agent.consume_cc_changes()) == 0


def test_orchestrator_phrase_boundary_cc_resend():
    """Verify that on_phrase_start triggers resending of CC staging."""
    agent = OrchestratorAgent(
        melody_channels=[0, 1],
        harmony_channels=[2, 3, 4],
        audio_config=AUDIO_CONFIG,
    )
    # Drain initial queue
    agent.consume_cc_changes()
    assert len(agent.consume_cc_changes()) == 0

    # Trigger phrase boundary
    agent.on_phrase_start()
    requeued = agent.consume_cc_changes()
    assert len(requeued) > 0
    cc_nums = {ctrl for (_, ctrl, _) in requeued}
    assert 7 in cc_nums
    assert 91 in cc_nums


@patch("subprocess.Popen")
def test_fluidsynth_cli_args_reverb_gain(mock_popen):
    """Verify NativeFluidSynthPort passes reverb and gain flags to fluidsynth CLI."""
    mock_proc = MagicMock()
    mock_popen.return_value = mock_proc

    fs_config = {
        "master_gain": 0.65,
        "reverb_active": True,
        "reverb_room_size": 0.82,
        "reverb_damping": 0.35,
        "reverb_width": 1.2,
        "reverb_level": 0.75,
        "velocity_floor": 25,
        "velocity_ceiling": 120,
        "velocity_curve": "soft_knee",
    }

    port = NativeFluidSynthPort("dummy.sf2", audio_driver="dsound", config=fs_config)
    assert mock_popen.called
    call_args = mock_popen.call_args[0][0]

    assert "-o" in call_args
    assert "synth.gain=0.650" in call_args
    assert "synth.reverb.active=yes" in call_args
    assert "synth.reverb.room-size=0.820" in call_args
    assert "synth.reverb.damp=0.350" in call_args
    assert "synth.reverb.width=1.200" in call_args
    assert "synth.reverb.level=0.750" in call_args


@patch("subprocess.Popen")
def test_fluidsynth_velocity_shaping(mock_popen):
    """Verify soft-knee velocity curve maps input velocities cleanly into floor..ceiling range."""
    mock_popen.return_value = MagicMock()

    fs_config = {
        "velocity_floor": 15,
        "velocity_ceiling": 120,
        "velocity_curve": "soft_knee",
    }
    port = NativeFluidSynthPort("dummy.sf2", audio_driver="dsound", config=fs_config)

    # Note off (velocity 0)
    assert port._shape_velocity(0) == 0

    # Low velocity (e.g. 1) should be mapped to velocity_floor (15)
    v_min = port._shape_velocity(1)
    assert v_min == 15

    # Mid velocity (e.g. 64)
    v_mid = port._shape_velocity(64)
    assert 15 < v_mid < 120

    # High velocity (127) should reach ceiling (120)
    v_max = port._shape_velocity(127)
    assert v_max == 120


@patch("subprocess.Popen")
def test_fluidsynth_send_commands(mock_popen):
    """Verify send() applies velocity shaping for note_on and sends CC messages to stdin."""
    mock_stdin = MagicMock()
    mock_proc = MagicMock()
    mock_proc.stdin = mock_stdin
    mock_popen.return_value = mock_proc

    fs_config = {
        "velocity_floor": 15,
        "velocity_ceiling": 120,
        "velocity_curve": "soft_knee",
    }
    port = NativeFluidSynthPort("dummy.sf2", audio_driver="dsound", config=fs_config)

    # Test Note On with velocity shaping
    port.send(mido.Message("note_on", channel=0, note=60, velocity=100))
    written_data = mock_stdin.write.call_args_list[0][0][0].decode("utf-8")
    assert written_data.startswith("noteon 0 60 ")
    written_vel = int(written_data.strip().split()[3])
    assert 15 <= written_vel <= 120

    # Test CC Message (Reverb send CC 91)
    mock_stdin.reset_mock()
    port.send(mido.Message("control_change", channel=2, control=91, value=85))
    cc_written = mock_stdin.write.call_args_list[0][0][0].decode("utf-8")
    assert cc_written == "cc 2 91 85\n"


@patch("subprocess.Popen")
def test_fluidsynth_panic_and_resume(mock_popen):
    """Verify panic() tracks active notes, cuts gain and volumes, releases pedals, and resume() restores gain."""
    mock_stdin = MagicMock()
    mock_proc = MagicMock()
    mock_proc.stdin = mock_stdin
    mock_popen.return_value = mock_proc

    port = NativeFluidSynthPort("dummy.sf2", audio_driver="dsound", config={"master_gain": 0.70})

    # Send note on (should be tracked in active_notes)
    port.send(mido.Message("note_on", channel=1, note=64, velocity=90))
    assert (1, 64) in port.active_notes

    # Call panic
    mock_stdin.reset_mock()
    port.panic()

    writes = [call[0][0].decode("utf-8") for call in mock_stdin.write.call_args_list]
    # Verify gain cut
    assert "gain 0\n" in writes
    # Verify channel volume cut and sustain pedal release
    assert "cc 1 7 0\n" in writes
    assert "cc 1 64 0\n" in writes
    # Verify explicit noteoff for tracked active note
    assert "noteoff 1 64\n" in writes
    assert "reset\n" in writes
    assert len(port.active_notes) == 0

    # Call resume
    mock_stdin.reset_mock()
    port.resume()
    resume_writes = [call[0][0].decode("utf-8") for call in mock_stdin.write.call_args_list]
    assert "gain 0.700\n" in resume_writes


def test_bind_subprocess_lifecycle():
    """Verify bind_subprocess_to_parent_lifecycle runs safely."""
    from src.utils.audio import bind_subprocess_to_parent_lifecycle
    dummy_proc = MagicMock()
    dummy_proc._handle = None
    bind_subprocess_to_parent_lifecycle(dummy_proc)

