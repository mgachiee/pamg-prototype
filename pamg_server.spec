# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).resolve()

# 1. Native FluidSynth Shared Libraries (*.dll, *.so, *.dylib) and CLI Binaries
binaries = []

if sys.platform == "win32":
    fluidsynth_bin_env = os.environ.get("FLUIDSYNTH_BIN")
    fluidsynth_bin = None
    if fluidsynth_bin_env and Path(fluidsynth_bin_env).exists():
        fluidsynth_bin = Path(fluidsynth_bin_env)
        if fluidsynth_bin.is_file():
            fluidsynth_bin = fluidsynth_bin.parent
    else:
        candidates = [
            Path(r"C:\Program Files\FluidSynth\fluidsynth-v2.5.5-win10-x64-cpp11\bin"),
            Path(r"C:\Program Files\FluidSynth\bin"),
            Path(r"C:\tools\fluidsynth\bin"),
            Path(r"C:\tools\fluidsynth"),
            Path(os.environ.get("ChocolateyInstall", r"C:\ProgramData\chocolatey")) / "lib" / "fluidsynth" / "tools",
        ]
        for c in candidates:
            if c.exists() and (any(c.glob("*.dll")) or any(c.glob("fluidsynth.exe"))):
                fluidsynth_bin = c
                break

    if fluidsynth_bin and fluidsynth_bin.exists():
        for item in fluidsynth_bin.glob("*"):
            if item.is_file() and (item.suffix.lower() in [".dll", ".exe"]):
                binaries.append((str(item), "."))

elif sys.platform == "darwin":
    mac_lib_candidates = [
        Path("/opt/homebrew/lib"),
        Path("/usr/local/lib"),
    ]
    for c in mac_lib_candidates:
        if c.exists():
            for dylib in c.glob("libfluidsynth*.dylib"):
                binaries.append((str(dylib), "."))

    mac_bin_candidates = [
        Path("/opt/homebrew/bin/fluidsynth"),
        Path("/usr/local/bin/fluidsynth"),
    ]
    for b in mac_bin_candidates:
        if b.exists() and b.is_file():
            binaries.append((str(b), "."))

elif sys.platform.startswith("linux"):
    linux_lib_candidates = [
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib"),
        Path("/usr/local/lib"),
    ]
    for c in linux_lib_candidates:
        if c.exists():
            for so in c.glob("libfluidsynth.so*"):
                binaries.append((str(so), "."))

    linux_bin_candidates = [
        Path("/usr/bin/fluidsynth"),
        Path("/usr/local/bin/fluidsynth"),
    ]
    for b in linux_bin_candidates:
        if b.exists() and b.is_file():
            binaries.append((str(b), "."))


# 2. Asset and Data files (SoundFont asset)
datas = []
sf2_asset = project_root / "src" / "assets" / "FluidR3_GM_GS.sf2"
if sf2_asset.exists():
    datas.append((str(sf2_asset), "src/assets"))

# 3. Analysis configuration
a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "mido",
        "mido.backends.rtmidi",
        "rtmidi",
        "ctypes",
        "ctypes.util",
        "asyncio",
        "socket",
        "src.core.clock",
        "src.core.configs",
        "src.core.logger",
        "src.core.midi_events",
        "src.core.midi_io",
        "src.core.note_logger",
        "src.core.packet_handler",
        "src.core.players",
        "src.core.preset_interpolator",
        "src.core.routing",
        "src.core.scheduler",
        "src.core.seeded_phrase_generator",
        "src.core.tcp_server",
        "src.core.chord_dictionary",
        "src.core.harmony_grammar",
        "src.models.game_state",
        "src.models.harmony_types",
        "src.models.midi_event",
        "src.models.preset",
        "src.models.seed_state",
        "src.models.time_signature",
        "src.modules.harmony_agent",
        "src.modules.melody_agent",
        "src.modules.orchestrator_agent",
        "src.modules.percussion_agent",
        "src.utils.audio",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "api",
        "fastapi",
        "uvicorn",
        "pydantic",
        "starlette",
        "tkinter",
        "matplotlib",
        "IPython",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pamg-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="pamg-server",
)
