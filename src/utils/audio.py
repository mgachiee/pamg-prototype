"""
Cross-platform audio driver detection and high-resolution multimedia timer management.
"""

import platform

AUDIO_DRIVER_MAPPING = {
    "windows": "wasapi",
    "linux": "pulseaudio",
    "darwin": "coreaudio",
}


def get_device_os() -> str:
    """
    Return the operating system name.

    Returns:
        str: OS name ('Windows', 'Linux', 'Darwin', etc.).
    """
    return platform.system()


def get_default_audio_driver() -> str:
    """
    Return the default audio driver based on the operating system.

    Returns:
        str: 'wasapi' for Windows, 'pulseaudio' for Linux, 'coreaudio' for macOS,
             or 'unknown' for unrecognized systems.
    """
    return AUDIO_DRIVER_MAPPING.get(get_device_os().lower(), "unknown")


def use_highres_timer(mode: str = "enable") -> None:
    """
    Enable or disable high-resolution multimedia timer on Windows (1ms scheduling quantum).
    For Linux and macOS, the default timer resolution is sufficient.

    Args:
        mode (str): 'enable' to enable high-resolution timer, 'disable' to disable.
    """
    is_windows = get_device_os().lower() == "windows"
    if is_windows:
        try:
            import ctypes
            if mode == "enable":
                ctypes.windll.winmm.timeBeginPeriod(1)
            elif mode == "disable":
                ctypes.windll.winmm.timeEndPeriod(1)
        except Exception as e:
            # Non-fatal if timer resolution cannot be altered
            pass
