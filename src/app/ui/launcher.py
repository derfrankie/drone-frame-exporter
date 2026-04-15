from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo
from PySide6.QtWidgets import QApplication

from app.ui.main_window import DroneFrameExtractorWindow


def run_ui(
    initial_video: Path | None = None,
    initial_gpx: Path | None = None,
    initial_output_dir: Path | None = None,
) -> int:
    _configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    window = DroneFrameExtractorWindow(
        initial_video=initial_video,
        initial_gpx=initial_gpx,
        initial_output_dir=initial_output_dir,
    )
    window.show()
    return app.exec()


def _configure_qt_runtime() -> None:
    qt_prefix = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath))
    if not qt_prefix.exists():
        return

    plugin_path = qt_prefix / "plugins"
    if plugin_path.exists():
        QCoreApplication.setLibraryPaths([str(plugin_path)])
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugin_path))

    helper_candidates = [
        qt_prefix / "lib/QtWebEngineCore.framework/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess",
        qt_prefix
        / "lib/QtWebEngineCore.framework/Versions/A/Helpers/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess",
    ]
    for helper_path in helper_candidates:
        if helper_path.exists():
            os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(helper_path))
            break

    resources_candidates = [
        qt_prefix / "lib/QtWebEngineCore.framework/Resources",
        qt_prefix / "lib/QtWebEngineCore.framework/Versions/A/Resources",
    ]
    for resources_path in resources_candidates:
        if resources_path.exists():
            os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", str(resources_path))
            locales_path = resources_path / "qtwebengine_locales"
            if locales_path.exists():
                os.environ.setdefault("QTWEBENGINE_LOCALES_PATH", str(locales_path))
            break
