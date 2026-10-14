"""MIDI port discovery and routing helpers."""

import mido
import subprocess


# ---------------------------------------------------------------------------
# Port management
# ---------------------------------------------------------------------------

from src.core.routing import RoutingType

class NativeFluidSynthPort:
    """
    Duck-types a mido port to send commands directly to a FluidSynth subprocess via stdin.
    This bypasses the need for virtual MIDI ports like loopMIDI.
    Supports cross-platform audio drivers (wasapi, pulseaudio, coreaudio, dsound).
    Configures internal Freeverb DSP and master gain headroom based on AUDIO_CONFIG.
    """
    def __init__(self, sf2_path: str, audio_driver: str = None, audio_config: dict = None, config: dict = None):
        if not audio_driver:
            from src.utils.audio import get_default_audio_driver
            audio_driver = get_default_audio_driver()
            if audio_driver == "unknown":
                audio_driver = "dsound"

        from src.utils.audio import get_fluidsynth_binary
        fs_bin = get_fluidsynth_binary()

        from src.core.configs import AUDIO_CONFIG
        cfg = config if config is not None else audio_config
        self.config = dict(cfg) if cfg is not None else dict(AUDIO_CONFIG)

        cmd = [fs_bin, "-n", "-a", audio_driver]

        # Configure Master Gain Headroom
        gain = float(self.config.get("master_gain", 0.65))
        cmd.extend(["-o", f"synth.gain={gain:.3f}"])

        # Configure Reverb DSP settings (Concert Hall)
        reverb_active = "yes" if self.config.get("reverb_enabled", True) else "no"
        cmd.extend(["-o", f"synth.reverb.active={reverb_active}"])
        if self.config.get("reverb_enabled", True):
            room_size = float(self.config.get("reverb_room_size", 0.80))
            damp = float(self.config.get("reverb_damping", 0.35))
            width = float(self.config.get("reverb_width", 1.0))
            level = float(self.config.get("reverb_level", 0.75))
            cmd.extend([
                "-o", f"synth.reverb.room-size={room_size:.3f}",
                "-o", f"synth.reverb.damp={damp:.3f}",
                "-o", f"synth.reverb.width={width:.3f}",
                "-o", f"synth.reverb.level={level:.3f}",
            ])

        cmd.append(sf2_path)
        print(f"Starting embedded FluidSynth ({audio_driver}) with {sf2_path} (gain={gain:.2f}, reverb={reverb_active})...")
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.closed = False
        self.audio_driver = audio_driver
        self.v_floor = int(self.config.get("velocity_floor", 15))
        self.v_ceiling = int(self.config.get("velocity_ceiling", 120))
        self.v_curve = str(self.config.get("velocity_curve", "soft_knee"))

    def _shape_velocity(self, velocity: int) -> int:
        """
        Calibrate velocity into the audible, unclipped dynamic range [v_floor, v_ceiling].
        Uses soft-knee scaling to preserve dynamic contrast between presets without harsh clipping.
        """
        if velocity <= 0:
            return 0
        v_norm = max(0.0, min(1.0, (velocity - 1) / 126.0))
        if self.v_curve == "soft_knee":
            v_shaped = v_norm ** 0.90
        elif self.v_curve == "compressed":
            v_shaped = v_norm ** 0.75
        else:
            v_shaped = v_norm

        out_vel = int(round(self.v_floor + v_shaped * (self.v_ceiling - self.v_floor)))
        return max(1, min(127, out_vel))

    def send(self, msg):
        if self.closed or not self.process.stdin:
            return
        
        try:
            if msg.type == 'note_on':
                # FluidSynth convention: velocity 0 is note_off
                if msg.velocity == 0:
                    cmd = f"noteoff {msg.channel} {msg.note}\n"
                else:
                    shaped_vel = self._shape_velocity(msg.velocity)
                    cmd = f"noteon {msg.channel} {msg.note} {shaped_vel}\n"
                self.process.stdin.write(cmd.encode('utf-8'))
                self.process.stdin.flush()
            elif msg.type == 'note_off':
                cmd = f"noteoff {msg.channel} {msg.note}\n"
                self.process.stdin.write(cmd.encode('utf-8'))
                self.process.stdin.flush()
            elif msg.type == 'program_change':
                cmd = f"prog {msg.channel} {msg.program}\n"
                self.process.stdin.write(cmd.encode('utf-8'))
                self.process.stdin.flush()
            elif msg.type == 'control_change':
                cmd = f"cc {msg.channel} {msg.control} {msg.value}\n"
                self.process.stdin.write(cmd.encode('utf-8'))
                self.process.stdin.flush()
            elif msg.type == 'pitchwheel':
                # mido pitchwheel is -8192 to 8191. fluidsynth expects 0 to 16383
                fs_val = msg.pitch + 8192
                cmd = f"pitch_bend {msg.channel} {fs_val}\n"
                self.process.stdin.write(cmd.encode('utf-8'))
                self.process.stdin.flush()
        except Exception:
            pass

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                if self.process.stdin:
                    self.process.stdin.write(b"quit\n")
                    self.process.stdin.flush()
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                pass


# ------------------------------------------------------------------
# Open ports
# ------------------------------------------------------------------

def open_midi_ports(
    routing_mode: RoutingType,
    melody_port_name: str,
    drum_port_name: str,
    single_port_name: str,
    sf2_path: str = None,
    audio_driver: str = None,
    audio_config: dict = None,
):
    """
    Open MIDI output ports according to the routing mode, or bypass MIDI completely 
    and use an embedded FluidSynth process if sf2_path is provided.

    Args:
        routing_mode (RoutingType): Selected routing strategy.
        melody_port_name (str): Output port for melody events.
        drum_port_name (str): Output port for percussion events.
        single_port_name (str): Shared port for single-port routing.
        sf2_path (str, optional): Path to .sf2 file to embed FluidSynth directly.
        audio_driver (str, optional): FluidSynth audio driver (wasapi, pulseaudio, coreaudio, etc.).
        audio_config (dict, optional): Audio DSP and reverb configuration.

    Returns:
        tuple: (melody_port, drum_port) outputs.
    """
    if sf2_path:
        # Bypass MIDI port creation entirely and use direct embedded FluidSynth
        synth_port = NativeFluidSynthPort(sf2_path, audio_driver=audio_driver, audio_config=audio_config)
        return synth_port, synth_port

    # Discover available output ports before validating names.
    available_ports = list_midi_ports()
    print(f"Available MIDI output ports: {available_ports}")

    # Validate and open ports based on routing mode
    if routing_mode == RoutingType.single_port:
        # Single-port mode sends both streams through the same output.
        if single_port_name not in available_ports:
            raise ValueError(
                f"Single-port mode requires '{single_port_name}', but it is not available."
            )
        shared_port = mido.open_output(single_port_name)
        return shared_port, shared_port

    if routing_mode == RoutingType.split_ports:
        # Split-port mode validates both melody and drum outputs.
        missing_ports = []
        if melody_port_name not in available_ports:
            missing_ports.append(melody_port_name)
        if drum_port_name not in available_ports:
            missing_ports.append(drum_port_name)
        if missing_ports:
            raise ValueError(
                f"Missing MIDI output ports for split mode: {missing_ports}."
            )

        melody_port = mido.open_output(melody_port_name)
        drum_port = mido.open_output(drum_port_name)
        return melody_port, drum_port

    raise ValueError(
        f"Invalid routing mode '{routing_mode}'. Use 'single_port' or 'split_ports'."
    )

# ------------------------------------------------------------------
# Close ports
# ------------------------------------------------------------------

def close_midi_ports(*ports):
    """
    Close any provided MIDI output ports or synth subprocesses.

    Deduplicates port references and checks closed state to prevent closing
    the same port multiple times in single-port routing mode.

    Args:
        *ports: Variable list of ports to close; None values are ignored.
    """
    seen_ids = set()
    for port in ports:
        if port is not None and id(port) not in seen_ids:
            seen_ids.add(id(port))
            try:
                # Support both mido ports and our custom NativeFluidSynthPort
                if hasattr(port, 'closed'):
                    is_closed = port.closed
                else:
                    is_closed = False
                    
                if not is_closed:
                    port.close()
            except Exception:
                pass

# ------------------------------------------------------------------
# Discovery helpers
# ------------------------------------------------------------------

def list_midi_ports():
    """
    Return the available MIDI output port names.

    Returns:
        list: A list of available MIDI output port names.
    """
    try:
        return mido.get_output_names()
    except Exception:
        return []