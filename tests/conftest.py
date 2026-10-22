import asyncio
import sys
from pathlib import Path
import pytest


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


class DummyMidiPort:
    """Mock MIDI port for headless testing without hardware MIDI drivers."""

    def __init__(self, name: str = "dummy"):
        self.name = name
        self.messages = []
        self.closed = False

    def send(self, msg):
        if self.closed:
            raise RuntimeError("Cannot send on closed port")
        self.messages.append(msg)

    def close(self):
        self.closed = True


@pytest.fixture
def dummy_port():
    return DummyMidiPort()
