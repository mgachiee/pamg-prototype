from pathlib import Path

from src.core.note_logger import NoteLogger


def test_note_logger_resolves_relative_path_next_to_packaged_executable(monkeypatch, tmp_path):
    executable = tmp_path / "pamg-server.exe"
    monkeypatch.setattr("src.core.note_logger.sys.frozen", True, raising=False)
    monkeypatch.setattr("src.core.note_logger.sys.executable", str(executable))

    logger = NoteLogger("logs/pamg_playback.log")

    assert Path(logger.log_path) == tmp_path / "logs" / "pamg_playback.log"