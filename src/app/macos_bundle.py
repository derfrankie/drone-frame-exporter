from __future__ import annotations

import sys

from app.ui.launcher import run_ui


def main() -> int:
    # Ignore Finder's process serial number argument when the app is double-clicked.
    sys.argv = [arg for arg in sys.argv if not arg.startswith("-psn_")]
    return run_ui()


if __name__ == "__main__":
    raise SystemExit(main())
