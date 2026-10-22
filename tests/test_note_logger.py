import re

from src.core.note_logger import NoteLogger


def test_note_logger_writes_execution_trace_header(tmp_path):
    log_path = tmp_path / "realtime_output.log"
    logger = NoteLogger(str(log_path))

    logger.start_session(
        key_center="D",
        time_signature="4/4",
        tempo=120,
        raw_valence=-0.5,
        raw_arousal=0.75,
        normalized_valence=0.25,
        normalized_arousal=0.75,
        preset_label="Interpolated",
    )
    logger.close()

    contents = log_path.read_text(encoding="utf-8")
    assert "=" * 127 in contents
    assert "PAMG REAL-TIME AUDIO ENGINE - EXECUTION TRACE" in contents
    assert re.search(r"Timestamp: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", contents)
    assert f"Directory: {log_path.resolve()}" in contents
    assert "Key Center: D | Time Signature: 4/4 | Initial Tempo: 120.0 BPM" in contents
    assert "Received VA: V=-0.500 | A=0.750" in contents
    assert "Normalized VA: V=0.250 | A=0.750" in contents
    assert "Preset: Interpolated" in contents


def test_note_logger_handles_missing_received_va(tmp_path):
    log_path = tmp_path / "realtime_output.log"
    logger = NoteLogger(str(log_path))

    logger.start_session(
        key_center="D",
        time_signature="4/4",
        tempo=120.0,
        raw_valence=None,
        raw_arousal=None,
        normalized_valence=0.0,
        normalized_arousal=0.0,
        preset_label="Preset A",
    )
    logger.close()

    assert "Received VA: V=N/A | A=N/A" in log_path.read_text(encoding="utf-8")


def test_note_logger_records_state_updates_before_session_starts(tmp_path):
    log_path = tmp_path / "realtime_output.log"
    logger = NoteLogger(str(log_path))

    logger.log_state_update(-0.5, 0.75, 0.25, 0.75, 128, "3/4", "F#", 99)
    logger.start_session("D", "4/4", 120, None, None, 0.0, 0.0, "Preset A")

    contents = log_path.read_text(encoding="utf-8")
    assert "STATE UPDATE" in contents
    assert "Received VA: V=-0.500 | A=0.750" in contents
    assert "Normalized XY: X=0.250 | Y=0.750" in contents
    assert "Meter: 3/4 | Tempo: 128.0 | Seed: 99" in contents
