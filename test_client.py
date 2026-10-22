"""
PAMG TCP Socket Test Client.

A real-time simulation client for PAMG that connects over TCP, performs
handshake, and streams telemetry across the 4 PAMG preset quadrants:
  - Preset A: Somber / Subdued   (-V, -A) [4/4, 84 BPM]
  - Preset B: Calm / Sanctuary   (+V, -A) [4/4, 96 BPM]
  - Preset C: Tense / Danger     (-V, +A) [4/4, 90 BPM]
  - Preset D: Heroic / Victory   (+V, +A) [4/4, 90 BPM]

Usage:
  python test_client.py --host 127.0.0.1 --port 9000
  python test_client.py --measures-per-phase 2 --shutdown
  python test_client.py --interactive
"""

import argparse
import json
import socket
import sys
import time
from typing import Any, Dict, Optional


PAMG_PHASES = [
    {
        "phase_name": "PHASE 1: PRESET A - SUBDUED / SOMBER (-V, -A)",
        "preset": "A",
        "quad_label": "[-V, -A] (Corner 0,0)",
        "valence": -0.85,
        "arousal": -0.80,
        "tempo": 90.0,
        "time_signature": "4/4",
        "seed": 101,
        "description": "Sparse, low velocity, quiet harmony, minimal percussion",
    },
    {
        "phase_name": "PHASE 2: PRESET B - CALM / SANCTUARY (+V, -A)",
        "preset": "B",
        "quad_label": "[+V, -A] (Corner 1,0)",
        "valence": 0.80,
        "arousal": -0.65,
        "tempo": 90.0,
        "time_signature": "4/4",
        "seed": 202,
        "description": "Open harmony, peaceful motif, moderate tempo in 4/4 waltz",
    },
    {
        "phase_name": "PHASE 3: PRESET C - TENSE / DANGER COMBAT (-V, +A)",
        "preset": "C",
        "quad_label": "[-V, +A] (Corner 0,1)",
        "valence": -0.75,
        "arousal": 0.85,
        "tempo": 90.0,
        "time_signature": "4/4",
        "seed": 303,
        "description": "Driving rhythms, high tension chords, rapid steps in 4/4",
    },
    {
        "phase_name": "PHASE 4: PRESET D - HEROIC / TRIUMPHANT (+V, +A)",
        "preset": "D",
        "quad_label": "[+V, +A] (Corner 1,1)",
        "valence": 0.90,
        "arousal": 0.80,
        "tempo": 90.0,
        "time_signature": "4/4",
        "seed": 404,
        "description": "Full orchestral density, high energy, triumphant resolution",
    },
]


def send_packet(sock: socket.socket, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a JSON dictionary packet followed by newline and parse response.

    Args:
        sock (socket.socket): Active TCP socket connection.
        payload (dict): Python dictionary to serialize.

    Returns:
        dict: Parsed JSON response from server.
    """
    message = json.dumps(payload) + "\n"
    sock.sendall(message.encode("utf-8"))

    buffer = ""
    while "\n" not in buffer:
        chunk = sock.recv(4096).decode("utf-8")
        if not chunk:
            raise ConnectionError("Server disconnected unexpectedly.")
        buffer += chunk

    line = buffer.split("\n", 1)[0].strip()
    if line:
        try:
            return json.loads(line)
        except json.JSONDecodeError as err:
            print(f"[Client Warning] Received non-JSON response: {line} ({err})")
    return {}


def query_status(sock: socket.socket) -> Dict[str, Any]:
    """Query current engine status (measure, step, BPM, meter, XY coords)."""
    return send_packet(sock, {"action": "status"})


def build_telemetry_payload(phase: Dict[str, Any]) -> Dict[str, Any]:
    """Construct a telemetry packet matching the specified PAMG phase."""
    # VA remains compatibility telemetry; XY is the documented preset input.
    x = (max(-1.0, min(1.0, phase["valence"])) + 1.0) / 2.0
    y = (max(-1.0, min(1.0, phase["arousal"])) + 1.0) / 2.0
    return {
        "action": "telemetry",
        "valence": phase["valence"],
        "arousal": phase["arousal"],
        "x": x,
        "y": y,
        "macro_state": {
            "music_config": {
                "time_signature": phase["time_signature"],
                "tempo": phase["tempo"],
            }
        },
        "seed": phase["seed"],
    }


def wait_until_measure(
    sock: socket.socket,
    target_measure: int,
    phase_label: str,
    timeout_sec: float = 60.0,
) -> Dict[str, Any]:
    """
    Poll status until the clock reaches target_measure, printing a live progress indicator.
    """
    start_time = time.perf_counter()
    last_status: Dict[str, Any] = {}
    last_reported_m = -1

    while (time.perf_counter() - start_time) < timeout_sec:
        last_status = query_status(sock)
        curr_m = last_status.get("measure", 0)
        curr_s = last_status.get("step_in_measure", 0)
        bpm = last_status.get("bpm", 120.0)
        sig = last_status.get("time_signature", "4/4")
        x = last_status.get("x", 0.0)
        y = last_status.get("y", 0.0)

        if curr_m != last_reported_m:
            x_str = f"{x:.2f}" if x is not None else "0.00"
            y_str = f"{y:.2f}" if y is not None else "0.00"
            print(
                f"   [Playing {phase_label}] Measure: {curr_m:02d} | "
                f"Step: {curr_s:02d} | Meter: {sig} | Tempo: {bpm:5.1f} BPM | (x={x_str}, y={y_str})"
            )
            last_reported_m = curr_m

        if curr_m >= target_measure:
            return last_status

        time.sleep(0.08)

    return last_status


def run_automated_flow(
    host: str,
    port: int,
    measures_per_phase: int = 6,
    test_pause: bool = False,
    shutdown: bool = False,
    sidecar: bool = False,
) -> None:
    """Execute the full 4-quadrant benchmark flow."""
    print("=" * 80)
    print("PAMG TCP CLIENT - ADAPTIVE FLOW BENCHMARK")
    print(f"Connecting to PAMG server at {host}:{port} (sidecar={sidecar})...")
    print("=" * 80)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((host, port))
    except ConnectionRefusedError:
        print(f"\n[Error] Could not connect to {host}:{port}.")
        print("Please start the PAMG server first:")
        print(f"  python main.py --tcp --tcp-port {port}")
        sys.exit(1)

    try:
        # 1. Handshake
        print("\n1. Handshake Initiation...")
        handshake_resp = send_packet(sock, {"action": "handshake", "sidecar": sidecar})
        print(f"   Response: {handshake_resp}")
        if handshake_resp.get("status") != "ready":
            print("[Warning] Handshake did not return 'ready' status.")

        current_measure = handshake_resp.get("measure", 0)

        # Handshake resets the server to standby; telemetry never resumes it.
        print("\n2. Resume Playback...")
        resume_resp = send_packet(sock, {"action": "resume"})
        print(f"   Resume Response: {resume_resp}")
        if resume_resp.get("status") != "resumed":
            raise RuntimeError(f"Server did not resume playback: {resume_resp}")

        # 3. Iterate through the 4 Quadrant Phases
        for i, phase in enumerate(PAMG_PHASES, 1):
            print("\n" + "-" * 80)
            print(f">>> DISPATCHING {phase['phase_name']}")
            print(f"    Target: {phase['quad_label']} | Meter: {phase['time_signature']} | Tempo: {phase['tempo']} BPM")
            print(f"    Musical Style: {phase['description']}")

            telemetry = build_telemetry_payload(phase)
            resp = send_packet(sock, telemetry)
            print(f"    Server Acknowledged: status={resp.get('status')} | measure={resp.get('measure')}")

            target_measure = current_measure + measures_per_phase
            last_status = wait_until_measure(sock, target_measure, f"Preset {phase['preset']}")
            current_measure = last_status.get("measure", target_measure)

            # Test Pause/Resume during Phase 2
            if test_pause and i == 2:
                print("\n   [Test Action: PAUSE playback for 1.5 seconds...]")
                pause_resp = send_packet(sock, {"action": "pause"})
                print(f"   Pause Response: {pause_resp}")
                time.sleep(1.5)

                print("   [Test Action: RESUME playback...]")
                resume_resp = send_packet(sock, {"action": "resume"})
                print(f"   Resume Response: {resume_resp}")

        # 3. Final Status Query
        print("\n" + "=" * 80)
        final_status = query_status(sock)
        print(f"Final Engine Status: {final_status}")

        # 4. Teardown / Shutdown
        if shutdown:
            print("\nShutting down server gracefully...")
            shut_resp = send_packet(sock, {"action": "shutdown"})
            print(f"Shutdown Response: {shut_resp}")
        else:
            print("\nStopping client session (sending 'stop')...")
            stop_resp = send_packet(sock, {"action": "stop"})
            print(f"Stop Response: {stop_resp}")

        print("\n[OK] PAMG TCP Client benchmark flow completed successfully!")

    finally:
        sock.close()


def run_interactive_mode(host: str, port: int) -> None:
    """Run an interactive console allowing manual input of valence, arousal, or actions."""
    print("=" * 80)
    print("PAMG TCP CLIENT - INTERACTIVE REPL MODE")
    print(f"Connecting to {host}:{port}...")
    print("Commands:")
    print("  v <float> a <float>       Set Valence and Arousal (e.g., 'v 0.8 a -0.5')")
    print("  tempo <bpm>               Set Tempo in BPM (e.g., 'tempo 130')")
    print("  meter <sig>               Set Meter (4/4, 4/4, 6/8, 6/4)")
    print("  preset <A|B|C|D>          Jump to corner Preset (A, B, C, D)")
    print("  status                    Query engine status")
    print("  pause / resume / stop     Control playback")
    print("  quit                      Exit client")
    print("=" * 80)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((host, port))
        resp = send_packet(sock, {"action": "handshake"})
        print(f"Handshake: {resp}\n")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    try:
        while True:
            cmd = input("PAMG-Client> ").strip()
            if not cmd:
                continue
            if cmd in ("quit", "exit"):
                break

            parts = cmd.split()
            if cmd in ("pause", "resume", "stop", "reset", "status"):
                resp = send_packet(sock, {"action": cmd})
                print(f"Response: {resp}")
            elif cmd == "shutdown":
                resp = send_packet(sock, {"action": "shutdown"})
                print(f"Response: {resp}")
                break
            elif parts[0] == "tempo" and len(parts) > 1:
                resp = send_packet(sock, {"action": "telemetry", "tempo": float(parts[1])})
                print(f"Response: {resp}")
            elif parts[0] == "meter" and len(parts) > 1:
                resp = send_packet(sock, {"action": "telemetry", "time_signature": parts[1]})
                print(f"Response: {resp}")
            elif parts[0] == "preset" and len(parts) > 1:
                p = parts[1].upper()
                mapping = {
                    "A": (-0.85, -0.80),
                    "B": (0.85, -0.80),
                    "C": (-0.85, 0.85),
                    "D": (0.85, 0.85),
                }
                if p in mapping:
                    v, a = mapping[p]
                    resp = send_packet(
                        sock,
                        {
                            "action": "telemetry",
                            "valence": v,
                            "arousal": a,
                            "x": (v + 1.0) / 2.0,
                            "y": (a + 1.0) / 2.0,
                        },
                    )
                    print(f"Jumped to Preset {p}: {resp}")
                else:
                    print("Unknown preset. Choose from A, B, C, D.")
            elif "v" in parts and "a" in parts:
                v_idx = parts.index("v")
                a_idx = parts.index("a")
                val_v = float(parts[v_idx + 1])
                val_a = float(parts[a_idx + 1])
                resp = send_packet(
                    sock,
                    {
                        "action": "telemetry",
                        "valence": val_v,
                        "arousal": val_a,
                        "x": (max(-1.0, min(1.0, val_v)) + 1.0) / 2.0,
                        "y": (max(-1.0, min(1.0, val_a)) + 1.0) / 2.0,
                    },
                )
                print(f"Response: {resp}")
            else:
                # Try raw JSON
                try:
                    payload = json.loads(cmd)
                    resp = send_packet(sock, payload)
                    print(f"Response: {resp}")
                except Exception:
                    print("Unrecognized command. Type 'status', 'pause', 'v 0.5 a 0.5', etc.")

    finally:
        sock.close()
        print("Disconnected.")


def main() -> None:
    parser = argparse.ArgumentParser(description="PAMG TCP Test Client")
    parser.add_argument("--host", default="127.0.0.1", help="PAMG server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9000, help="PAMG server port (default: 9000)")
    parser.add_argument("--measures-per-phase", type=int, default=6, help="Measures to run per quadrant phase (default: 6)")
    parser.add_argument("--no-pause-test", action="store_true", help="Skip the pause/resume test")
    parser.add_argument("--shutdown", action="store_true", help="Request server shutdown after test flow")
    parser.add_argument("--sidecar", action="store_true", help="Request sidecar mode during handshake")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run interactive prompt")

    args = parser.parse_args()

    if args.interactive:
        run_interactive_mode(args.host, args.port)
    else:
        run_automated_flow(
            host=args.host,
            port=args.port,
            measures_per_phase=args.measures_per_phase,
            test_pause=not args.no_pause_test,
            shutdown=args.shutdown,
            sidecar=args.sidecar,
        )


if __name__ == "__main__":
    main()
