from __future__ import annotations

import sys
from pathlib import Path
from queue import Queue

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tts.voice_engine import VoiceEngine


class DummyProcess:
    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        self.killed = True


def main() -> None:
    engine = VoiceEngine.__new__(VoiceEngine)
    engine.msg_queue = Queue()
    engine.text_buffer = "pending text"
    engine.current_process = DummyProcess()

    engine.msg_queue.put("queued text")

    process = engine.current_process

    engine.stop()

    assert process.killed is True
    assert engine.current_process is None
    assert engine.text_buffer == ""
    assert engine.msg_queue.empty()

    engine.stop()

    assert engine.current_process is None
    assert engine.text_buffer == ""
    assert engine.msg_queue.empty()

    print("[OK] TTS stop boundary clears process, buffer, and queue")


if __name__ == "__main__":
    main()