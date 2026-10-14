"""
Unit tests for cross-platform audio driver detection.
"""

from unittest.mock import patch
from src.utils.audio import get_default_audio_driver, use_highres_timer


def test_audio_driver_detection():
    with patch("platform.system", return_value="Windows"):
        assert get_default_audio_driver() == "wasapi"

    with patch("platform.system", return_value="Linux"):
        assert get_default_audio_driver() == "pulseaudio"

    with patch("platform.system", return_value="Darwin"):
        assert get_default_audio_driver() == "coreaudio"

    with patch("platform.system", return_value="UnknownOS"):
        assert get_default_audio_driver() == "unknown"


def test_highres_timer_toggle():
    # Calling on Windows should execute without raising exceptions
    use_highres_timer("enable")
    use_highres_timer("disable")
