from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedLayout, QWidget

from app.ui.track_view import TrackMapWidget
from core.gpx import GpxTrackIndex


class MapPanel(QWidget):
    pointScrubbed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QStackedLayout(self)
        self._fallback = TrackMapWidget(self)
        self._layout.addWidget(self._fallback)
        self._active = self._fallback
        self._fallback.pointScrubbed.connect(self.pointScrubbed)

        self._web_map = None

    @property
    def uses_web_map(self) -> bool:
        return self._web_map is not None and self._active is self._web_map

    def set_track(self, gpx_index: GpxTrackIndex | None) -> None:
        self._fallback.set_track(gpx_index)
        if gpx_index is not None:
            self._ensure_web_map()

    def set_markers(self, markers: list[dict]) -> None:
        self._fallback.set_markers(markers)

    def set_current_point(self, point) -> None:
        self._fallback.set_current_point(point)

    def set_scrub_point(self, point) -> None:
        self._fallback.set_scrub_point(point)

    def set_web_map_state(
        self,
        track_points: list[dict],
        markers: list[dict],
        current_point: dict | None,
        scrub_point: dict | None,
    ) -> None:
        self._ensure_web_map()
        if self._web_map is not None:
            self._web_map.set_map_state(
                track_points=track_points,
                markers=markers,
                current_point=current_point,
                scrub_point=scrub_point,
            )

    def _ensure_web_map(self) -> None:
        if self._web_map is not None:
            return
        try:
            from app.ui.web_map import LeafletMapWidget
        except Exception:  # pragma: no cover - fallback when WebEngine is unavailable
            return
        self._web_map = LeafletMapWidget(self)
        self._layout.addWidget(self._web_map)
        self._layout.setCurrentWidget(self._web_map)
        self._active = self._web_map
        self._web_map.pointScrubbed.connect(self.pointScrubbed)
