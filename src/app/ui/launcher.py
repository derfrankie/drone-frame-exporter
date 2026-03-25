from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.main_window import DroneFrameExtractorWindow


def run_ui(
    initial_video: Path | None = None,
    initial_gpx: Path | None = None,
    initial_output_dir: Path | None = None,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = DroneFrameExtractorWindow(
        initial_video=initial_video,
        initial_gpx=initial_gpx,
        initial_output_dir=initial_output_dir,
    )
    window.show()
    return app.exec()
