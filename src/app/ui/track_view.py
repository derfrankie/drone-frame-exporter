from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from core.gpx import GpxTrackIndex
from core.models import GpxPoint


class TrackMapWidget(QWidget):
    pointScrubbed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._gpx_index: GpxTrackIndex | None = None
        self._marker_points: list[dict] = []
        self._current_point: GpxPoint | None = None
        self._scrub_point: GpxPoint | None = None
        self._display_points: list[tuple[int, GpxPoint]] = []
        self._projected_points: list[tuple[int, GpxPoint, QPointF]] = []
        self._cached_frame: QRectF | None = None
        self._bounds: tuple[float, float, float, float] | None = None
        self.setMinimumSize(320, 280)

    def set_track(self, gpx_index: GpxTrackIndex | None) -> None:
        if self._gpx_index is gpx_index:
            return
        self._gpx_index = gpx_index
        self._display_points = gpx_index.downsampled_points() if gpx_index else []
        self._bounds = self._compute_bounds()
        self._rebuild_projection_cache()
        self.update()

    def set_markers(self, markers: list[dict]) -> None:
        self._marker_points = markers
        self.update()

    def set_current_point(self, point: GpxPoint | None) -> None:
        self._current_point = point
        self.update()

    def set_scrub_point(self, point: GpxPoint | None) -> None:
        self._scrub_point = point
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0a0c0f"))

        frame = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(frame, QColor("#12161b"))
        painter.setPen(QPen(QColor(255, 255, 255, 22), 1))
        painter.drawRoundedRect(frame, 18, 18)

        if not self._gpx_index or not self._gpx_index.points:
            painter.setPen(QColor("#98a8b5"))
            painter.drawText(frame, Qt.AlignCenter, "Load a GPX track to place the video on the map.")
            return

        if self._cached_frame != frame:
            self._rebuild_projection_cache(frame)

        projected = [projected_point for _, _, projected_point in self._projected_points]
        path = QPainterPath(projected[0])
        for point in projected[1:]:
            path.lineTo(point)

        painter.setPen(QPen(QColor("#5f7686"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

        self._draw_point(painter, self._gpx_index.points[0], frame, QColor("#7ae582"), 6)
        self._draw_point(painter, self._gpx_index.points[-1], frame, QColor("#ff5964"), 6)

        for marker in self._marker_points:
            self._draw_point(painter, marker["point"], frame, QColor(marker["color"]), 5)

        if self._current_point is not None:
            self._draw_point(painter, self._current_point, frame, QColor("#f3b95f"), 7, outline=QColor("white"))
        if self._scrub_point is not None:
            self._draw_point(painter, self._scrub_point, frame, QColor("#7bdff2"), 6, outline=QColor("#0a0c0f"))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rebuild_projection_cache()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._scrub_to_position(event.position())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton:
            self._scrub_to_position(event.position())

    def _draw_point(
        self,
        painter: QPainter,
        point: GpxPoint,
        frame: QRectF,
        color: QColor,
        radius: int,
        outline: QColor | None = None,
    ) -> None:
        projected = self._project_point(point, frame)
        painter.setBrush(color)
        painter.setPen(QPen(outline or color.darker(160), 1.5))
        painter.drawEllipse(projected, radius, radius)

    def _project_point(self, point: GpxPoint, frame: QRectF) -> QPointF:
        min_lat, max_lat, min_lon, max_lon = self._bounds or (point.latitude, point.latitude, point.longitude, point.longitude)
        lon_span = max(max_lon - min_lon, 0.00001)
        lat_span = max(max_lat - min_lat, 0.00001)
        x = frame.left() + ((point.longitude - min_lon) / lon_span) * frame.width()
        y = frame.bottom() - ((point.latitude - min_lat) / lat_span) * frame.height()
        return QPointF(x, y)

    def _compute_bounds(self) -> tuple[float, float, float, float] | None:
        if not self._gpx_index or not self._gpx_index.points:
            return None
        points = self._gpx_index.points
        min_lat = min(point.latitude for point in points)
        max_lat = max(point.latitude for point in points)
        min_lon = min(point.longitude for point in points)
        max_lon = max(point.longitude for point in points)
        return min_lat, max_lat, min_lon, max_lon

    def _rebuild_projection_cache(self, frame: QRectF | None = None) -> None:
        if not self._gpx_index or not self._display_points:
            self._projected_points = []
            self._cached_frame = frame
            return
        cached_frame = frame or self.rect().adjusted(12, 12, -12, -12)
        self._cached_frame = cached_frame
        self._projected_points = [
            (index, point, self._project_point(point, cached_frame))
            for index, point in self._display_points
        ]

    def _scrub_to_position(self, position: QPointF) -> None:
        if not self._projected_points:
            return
        nearest = min(
            self._projected_points,
            key=lambda item: (item[2].x() - position.x()) ** 2 + (item[2].y() - position.y()) ** 2,
        )
        self.pointScrubbed.emit(nearest[0])
