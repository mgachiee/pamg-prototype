"""
Async TCP socket server for real-time game engine parameter integration.
"""

import asyncio
import json
import socket
from typing import Optional

from src.core.logger import Logger
from src.core.packet_handler import PacketHandler
from src.models.game_state import GameState

logger = Logger()


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: GameState,
    packet_handler: PacketHandler,
    server_holder: dict,
) -> None:
    """
    Handle a single client connection, parsing line-delimited JSON payloads
    and delegating action routing to PacketHandler.
    """
    addr = writer.get_extra_info("peername")
    logger.info(f"[TCP Server] Client connected from {addr}")

    # Set TCP_NODELAY for minimal transmission latency
    sock = writer.get_extra_info("socket")
    if sock is not None:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

    try:
        while state.is_alive and not packet_handler.shutdown_requested:
            line = await reader.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                payload = json.loads(line_str)
            except json.JSONDecodeError as err:
                logger.warning(f"[TCP Server] Invalid JSON received from {addr}: {err}")
                writer.write(b'{"status": "error", "message": "invalid_json"}\n')
                await writer.drain()
                continue

            if not isinstance(payload, dict):
                logger.warning(f"[TCP Server] Received non-dict packet from {addr}.")
                writer.write(b'{"status": "error", "message": "packet_must_be_dict"}\n')
                await writer.drain()
                continue

            response = packet_handler.handle_packet(payload)
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

            # Detect shutdown request from client
            if packet_handler.shutdown_requested or response.get("status") == "shutting_down":
                logger.info(f"[TCP Server] Shutdown requested by client {addr}.")
                break

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning(f"[TCP Server] Error handling client {addr}: {exc}")
    finally:
        logger.info(f"[TCP Server] Client disconnected: {addr}")
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        if packet_handler.shutdown_requested or packet_handler.sidecar_mode:
            logger.info("[TCP Server] Client session finished in sidecar/shutdown mode. Stopping server.")
            server = server_holder.get("server")
            if server is not None:
                server.close()
        else:
            state.reset()
            logger.info("[TCP Server] Client disconnected. Engine state reset. Standing by for next connection.")


async def start_tcp_server(
    host: str = "127.0.0.1",
    port: int = 9000,
    state: Optional[GameState] = None,
    sidecar: bool = False,
) -> asyncio.Server:
    """
    Start the async TCP server on the specified host and port.

    Args:
        host (str): Listening IP / hostname.
        port (int): Listening TCP port.
        state (Optional[GameState]): Shared GameState container.
        sidecar (bool): If True, server terminates when client disconnects.

    Returns:
        asyncio.Server: Running server instance.
    """
    if state is None:
        state = GameState()

    packet_handler = PacketHandler(state=state, sidecar_mode=sidecar)
    server_holder: dict = {}

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, state, packet_handler, server_holder),
        host=host,
        port=port,
    )
    server_holder["server"] = server
    logger.info(f"[TCP Server] Listening on {host}:{port} (sidecar={sidecar})")
    return server
