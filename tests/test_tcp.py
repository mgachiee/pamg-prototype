import asyncio
import json
import pytest

from src.core.tcp_server import start_tcp_server
from src.models.game_state import GameState

TCP_TEST_TIMEOUT_SECONDS = 5


async def _open_connection(port: int):
    return await asyncio.wait_for(
        asyncio.open_connection("127.0.0.1", port),
        timeout=TCP_TEST_TIMEOUT_SECONDS,
    )


async def _read_json(reader):
    line = await asyncio.wait_for(
        reader.readline(),
        timeout=TCP_TEST_TIMEOUT_SECONDS,
    )
    return json.loads(line.decode("utf-8"))


def test_tcp_server_updates_game_state_flat():
    async def _run():
        state = GameState(tempo=120, loop_size=4, grain=4, base_seed=42)
        server = await start_tcp_server(host="127.0.0.1", port=9091, state=state)

        async with server:
            reader, writer = await _open_connection(9091)
            try:
                # Send valid flat payload
                payload = {
                    "x": 0.85,
                    "y": 0.15,
                    "tempo": 140,
                    "seed": 999,
                    "loop_size": 8,
                }
                writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                await writer.drain()

                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                assert resp["x"] == 0.85
                assert resp["y"] == 0.15
                assert resp["tempo"] == 140
                assert resp["seed"] == 999

                # Check state mutations
                assert state.x == 0.85
                assert state.y == 0.15
                assert state.tempo == 140
                assert state.base_seed == 999
                assert state.loop_size == 8
                assert state.structure_dirty is True

                # Send invalid JSON
                writer.write(b"NOT_A_JSON_STRING\n")
                await writer.drain()
                err_resp = await _read_json(reader)
                assert err_resp["status"] == "error"

            finally:
                writer.close()
                await writer.wait_closed()

    asyncio.run(_run())


def test_tcp_handshake_and_sidecar():
    async def _run():
        state = GameState()
        server = await start_tcp_server(host="127.0.0.1", port=9092, state=state)

        async with server:
            reader, writer = await _open_connection(9092)
            try:
                # Send handshake packet
                handshake_packet = {"action": "handshake", "sidecar": True}
                writer.write((json.dumps(handshake_packet) + "\n").encode("utf-8"))
                await writer.drain()

                resp = await _read_json(reader)
                assert resp["status"] == "ready"
                assert resp["engine_state"] == "ready"
                assert resp["sidecar"] is True
            finally:
                writer.close()
                await writer.wait_closed()

    asyncio.run(_run())


def test_tcp_telemetry_valence_arousal():
    async def _run():
        state = GameState()
        server = await start_tcp_server(host="127.0.0.1", port=9093, state=state)

        async with server:
            reader, writer = await _open_connection(9093)
            try:
                # Affective aliases remain diagnostic; direct XY controls
                # generation state.
                telemetry_packet = {
                    "action": "telemetry",
                    "valence": 1.0,
                    "arousal": -1.0,
                    "tempo": 128,
                    "seed": 555,
                    "x": 0.8,
                    "y": 0.2,
                }
                writer.write((json.dumps(telemetry_packet) + "\n").encode("utf-8"))
                await writer.drain()

                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                assert state.x == 0.8
                assert state.y == 0.2
                assert state.tempo == 128
                assert state.base_seed == 555

                # A second diagnostic packet must not overwrite XY.
                telemetry_center = {
                    "action": "telemetry",
                    "valence": -0.5,
                    "arousal": 0.5,
                }
                writer.write((json.dumps(telemetry_center) + "\n").encode("utf-8"))
                await writer.drain()

                resp2 = await _read_json(reader)
                assert resp2["status"] == "ok"
                assert abs(state.x - 0.8) < 1e-4
                assert abs(state.y - 0.2) < 1e-4
            finally:
                writer.close()
                await writer.wait_closed()

    asyncio.run(_run())


def test_tcp_telemetry_preserves_raw_va_and_key_center():
    from src.core.packet_handler import PacketHandler

    state = GameState()
    handler = PacketHandler(state)

    response = handler.handle_packet(
        {
            "action": "telemetry",
            "valence": -0.5,
            "arousal": 0.75,
            "key": "f#",
        }
    )

    assert state.raw_valence == -0.5
    assert state.raw_arousal == 0.75
    assert state.x is None
    assert state.y is None
    assert state.key_center == "F#"
    assert response["key_center"] == "F#"
    assert response["raw_valence"] == -0.5
    assert response["raw_arousal"] == 0.75


def test_tcp_telemetry_time_signatures():
    async def _run():
        state = GameState()
        server = await start_tcp_server(host="127.0.0.1", port=9094, state=state)

        async with server:
            reader, writer = await _open_connection(9094)
            try:
                # 1. 3/4 meter
                packet_34 = {
                    "action": "telemetry",
                    "macro_state": {"music_config": {"time_signature": "3/4"}},
                }
                writer.write((json.dumps(packet_34) + "\n").encode("utf-8"))
                await writer.drain()
                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                assert state.loop_size == 3
                assert state.grain == 4
                assert state.time_signature == "3/4"

                # 2. 6/8 meter
                packet_68 = {
                    "action": "telemetry",
                    "macro_state": {"music_config": {"time_signature": "6/8"}},
                }
                writer.write((json.dumps(packet_68) + "\n").encode("utf-8"))
                await writer.drain()
                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                assert state.loop_size == 6
                assert state.grain == 2
                assert state.time_signature == "6/8"

                # 3. 6/4 meter
                packet_64 = {
                    "action": "telemetry",
                    "macro_state": {"music_config": {"time_signature": "6/4"}},
                }
                writer.write((json.dumps(packet_64) + "\n").encode("utf-8"))
                await writer.drain()
                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                assert state.loop_size == 6
                assert state.grain == 4
                assert state.time_signature == "6/4"

                # 4. 4/4 meter
                packet_44 = {
                    "action": "telemetry",
                    "macro_state": {"music_config": {"time_signature": "4/4"}},
                }
                writer.write((json.dumps(packet_44) + "\n").encode("utf-8"))
                await writer.drain()
                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                assert state.loop_size == 4
                assert state.grain == 4
                assert state.time_signature == "4/4"

                # Invalid time signature returns error
                packet_invalid = {
                    "action": "telemetry",
                    "macro_state": {"music_config": {"time_signature": "11/8"}},
                }
                writer.write((json.dumps(packet_invalid) + "\n").encode("utf-8"))
                await writer.drain()
                err_resp = await _read_json(reader)
                assert err_resp["status"] == "error"
            finally:
                writer.close()
                await writer.wait_closed()

    asyncio.run(_run())


def test_tcp_lifecycle_actions():
    async def _run():
        state = GameState()
        server = await start_tcp_server(host="127.0.0.1", port=9095, state=state)

        async with server:
            reader, writer = await _open_connection(9095)
            try:
                # 1. Status query (initial state is paused in standby)
                writer.write(b'{"action": "status"}\n')
                await writer.drain()
                status_resp = await _read_json(reader)
                assert status_resp["status"] == "ok"
                assert status_resp["engine_state"] == "paused"

                # 2. Resume
                writer.write(b'{"action": "resume"}\n')
                await writer.drain()
                resume_resp = await _read_json(reader)
                assert resume_resp["status"] == "resumed"
                assert state.paused is False

                # 3. Pause
                writer.write(b'{"action": "pause"}\n')
                await writer.drain()
                pause_resp = await _read_json(reader)
                assert pause_resp["status"] == "paused"
                assert state.paused is True

                # 4. Reset
                state.x = 0.9
                writer.write(b'{"action": "reset"}\n')
                await writer.drain()
                reset_resp = await _read_json(reader)
                assert reset_resp["status"] == "ok"
                assert state.x is None

                # 5. Shutdown
                writer.write(b'{"action": "shutdown"}\n')
                await writer.drain()
                shut_resp = await _read_json(reader)
                assert shut_resp["status"] == "shutting_down"
                assert state.is_alive is False
            finally:
                writer.close()
                await writer.wait_closed()

    asyncio.run(_run())


def test_end_to_end_test_client_all_phases(dummy_port):
    from unittest.mock import patch
    import threading
    from src.core.clock import run_clock
    from src.core.routing import RoutingType
    from test_client import run_automated_flow

    state = GameState()

    async def _start_server_and_clock():
        server = await start_tcp_server(host="127.0.0.1", port=9096, state=state)
        clock_task = asyncio.create_task(
            run_clock(
                tempo=360,
                loop_size=4,
                grain=4,
                routing_mode=RoutingType.single_port,
                game_state=state,
            )
        )
        return server, clock_task

    async def _main():
        with patch("src.core.clock.open_midi_ports", return_value=(dummy_port, dummy_port)):
            server, clock_task = await _start_server_and_clock()
            async with server:
                # Run the automated client flow in a separate thread
                client_thread = threading.Thread(
                    target=run_automated_flow,
                    kwargs={
                        "host": "127.0.0.1",
                        "port": 9096,
                        "measures_per_phase": 1,
                        "test_pause": True,
                        "shutdown": True,
                    },
                )
                client_thread.start()
                await asyncio.wait_for(
                    asyncio.to_thread(client_thread.join, 30),
                    timeout=31,
                )
                assert not client_thread.is_alive(), "TCP client thread did not finish"
                # Wait for clock to exit cleanly on shutdown
                await clock_task

        assert state.is_alive is False
        assert dummy_port.closed is True

    asyncio.run(_main())


def test_tcp_client_disconnect_sidecar_shuts_down_cleanly(dummy_port):
    """Verify that in sidecar mode, an unexpected client disconnect shuts down clock and silences notes."""
    from unittest.mock import patch
    from src.core.clock import run_clock
    from src.core.routing import RoutingType

    state = GameState()

    async def _main():
        with patch("src.core.clock.open_midi_ports", return_value=(dummy_port, dummy_port)):
            server = await start_tcp_server(host="127.0.0.1", port=9097, state=state, sidecar=True)
            clock_task = asyncio.create_task(
                run_clock(
                    tempo=360,
                    loop_size=4,
                    grain=4,
                    routing_mode=RoutingType.single_port,
                    game_state=state,
                )
            )

            async with server:
                reader, writer = await _open_connection(9097)
                writer.write(b'{"action": "telemetry", "valence": 0.5, "arousal": 0.5}\n')
                await writer.drain()
                resp = await _read_json(reader)
                assert resp["status"] == "ok"
                # Abrupt client disconnection (simulating game closing or crashing)
                writer.close()
                await writer.wait_closed()

                # Wait for sidecar clock task to finish automatically
                await asyncio.wait_for(clock_task, timeout=3.0)

            assert state.is_alive is False
            assert state.shutdown_requested is True
            assert dummy_port.closed is True
            # Verify panic silence was sent to the port
            ccs = [(m.channel, m.control, m.value) for m in dummy_port.messages if m.type == "control_change"]
            assert (0, 64, 0) in ccs
            assert (0, 123, 0) in ccs

    asyncio.run(_main())


def test_tcp_client_disconnect_triggers_silence_non_sidecar():
    """Verify that in non-sidecar mode, client disconnection immediately triggers state.trigger_silence()."""
    state = GameState()
    silence_invoked = []
    state.silence_callbacks.append(lambda: silence_invoked.append(True))

    async def _main():
        server = await start_tcp_server(host="127.0.0.1", port=9098, state=state, sidecar=False)
        async with server:
            reader, writer = await _open_connection(9098)
            writer.write(b'{"action": "telemetry", "valence": 0.5, "arousal": 0.5}\n')
            await writer.drain()
            resp = await _read_json(reader)
            assert resp["status"] == "ok"
            assert state.paused is True

            # Disconnect client
            writer.close()
            await writer.wait_closed()
            # Allow server task loop to process disconnect
            await asyncio.sleep(0.05)

        assert len(silence_invoked) >= 1
        assert state.paused is True

    asyncio.run(_main())


