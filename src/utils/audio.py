"""
Cross-platform audio driver detection and high-resolution multimedia timer management.
"""

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Optional

AUDIO_DRIVER_MAPPING = {
    "windows": "wasapi",
    "linux": "pulseaudio",
    "darwin": "coreaudio",
}


def get_fluidsynth_binary() -> str:
    """
    Find fluidsynth executable across frozen bundle, environment, or system PATH.

    Returns:
        str: Path or name of the FluidSynth binary.
    """
    # 1. Environment variable
    env_bin = os.environ.get("FLUIDSYNTH_BIN")
    if env_bin:
        env_path = Path(env_bin)
        target = env_path / ("fluidsynth.exe" if sys.platform == "win32" else "fluidsynth")
        if target.exists():
            return str(target)
        if env_path.is_file() and env_path.exists():
            return str(env_path)

    # 2. PyInstaller bundled executable directory or temporary _MEIPASS
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        meipass = Path(getattr(sys, "_MEIPASS", exe_dir))
        for d in [exe_dir, meipass]:
            target = d / ("fluidsynth.exe" if sys.platform == "win32" else "fluidsynth")
            if target.exists():
                return str(target)

    # 3. Standard system PATH via shutil.which
    which_bin = shutil.which("fluidsynth")
    if which_bin:
        return which_bin

    # 4. Fallback to default command name
    return "fluidsynth"


def get_default_soundfont_path() -> Optional[str]:
    """
    Find default FluidR3_GM_GS.sf2 in bundle or project assets directory.

    Returns:
        Optional[str]: Absolute path to the soundfont file if found, else None.
    """
    sf2_filename = "FluidR3_GM_GS.sf2"

    # 1. PyInstaller bundled locations
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        meipass = Path(getattr(sys, "_MEIPASS", exe_dir))
        candidates = [
            exe_dir / "src" / "assets" / sf2_filename,
            exe_dir / "assets" / sf2_filename,
            exe_dir / sf2_filename,
            meipass / "src" / "assets" / sf2_filename,
            meipass / "assets" / sf2_filename,
            meipass / sf2_filename,
        ]
        for c in candidates:
            if c.exists():
                return str(c)

    # 2. Local development source tree relative to this file
    local_dev = Path(__file__).resolve().parent.parent / "assets" / sf2_filename
    if local_dev.exists():
        return str(local_dev)

    # 3. Check current working directory
    cwd_candidate = Path.cwd() / "src" / "assets" / sf2_filename
    if cwd_candidate.exists():
        return str(cwd_candidate)

    return None


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


_WINDOWS_JOB_OBJECT = None


def bind_subprocess_to_parent_lifecycle(process) -> None:
    """
    Ensure the child process automatically terminates when the parent process exits.
    On Windows, associates the child process with a Win32 Job Object configured with
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000), guaranteeing kernel-level termination
    even if the parent process crashes or terminates abruptly.
    """
    global _WINDOWS_JOB_OBJECT
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            if _WINDOWS_JOB_OBJECT is None:
                job = kernel32.CreateJobObjectW(None, None)
                if job:
                    class IO_COUNTERS(ctypes.Structure):
                        _fields_ = [
                            ("ReadOperationCount", ctypes.c_uint64),
                            ("WriteOperationCount", ctypes.c_uint64),
                            ("OtherOperationCount", ctypes.c_uint64),
                            ("ReadTransferCount", ctypes.c_uint64),
                            ("WriteTransferCount", ctypes.c_uint64),
                            ("OtherTransferCount", ctypes.c_uint64),
                        ]

                    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", ctypes.c_uint32),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", ctypes.c_uint32),
                            ("Affinity", ctypes.c_size_t),
                            ("PriorityClass", ctypes.c_uint32),
                            ("SchedulingClass", ctypes.c_uint32),
                        ]

                    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                            ("IoInfo", IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryLimit", ctypes.c_size_t),
                            ("PeakJobMemoryLimit", ctypes.c_size_t),
                        ]

                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    kernel32.SetInformationJobObject(
                        job, 9, ctypes.byref(info), ctypes.sizeof(info)
                    )
                    _WINDOWS_JOB_OBJECT = job

            if _WINDOWS_JOB_OBJECT and hasattr(process, "_handle") and process._handle:
                kernel32.AssignProcessToJobObject(_WINDOWS_JOB_OBJECT, int(process._handle))
        except Exception:
            pass

