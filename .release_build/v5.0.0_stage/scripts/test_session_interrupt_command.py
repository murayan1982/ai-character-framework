from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.session import is_interrupt_command


def main() -> None:
    assert is_interrupt_command("/interrupt") is True
    assert is_interrupt_command(" /interrupt ") is True
    assert is_interrupt_command("/INTERRUPT") is True

    assert is_interrupt_command("interrupt") is False
    assert is_interrupt_command("/stop") is False
    assert is_interrupt_command("") is False

    print("[OK] session interruption debug command detection works")


if __name__ == "__main__":
    main()
