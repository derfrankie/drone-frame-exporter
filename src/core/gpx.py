from __future__ import annotations

from bisect import bisect_left
from datetime import datetime
from pathlib import Path

import gpxpy

from core.errors import GpxError
from core.models import GpxPoint
from core.utils import ensure_utc


class GpxTrackIndex:
    def __init__(self, points: list[GpxPoint]) -> None:
        if not points:
            raise GpxError("GPX file contains no timestamped track points.")
        self.points = sorted(points, key=lambda point: point.timestamp)
        self._timestamps = [point.timestamp for point in self.points]

    @property
    def start_time(self) -> datetime:
        return self.points[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.points[-1].timestamp

    def nearest_point(self, target_time: datetime) -> GpxPoint:
        normalized = ensure_utc(target_time)
        position = bisect_left(self._timestamps, normalized)
        if position <= 0:
            return self.points[0]
        if position >= len(self.points):
            return self.points[-1]

        before = self.points[position - 1]
        after = self.points[position]
        before_delta = abs((normalized - before.timestamp).total_seconds())
        after_delta = abs((after.timestamp - normalized).total_seconds())
        return before if before_delta <= after_delta else after


def load_gpx_track(gpx_path: Path) -> GpxTrackIndex:
    if not gpx_path.exists():
        raise GpxError(f"GPX file does not exist: {gpx_path}")

    with gpx_path.open("r", encoding="utf-8") as handle:
        parsed = gpxpy.parse(handle)

    points: list[GpxPoint] = []
    for track in parsed.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time is None:
                    continue
                points.append(
                    GpxPoint(
                        timestamp=ensure_utc(point.time),
                        latitude=point.latitude,
                        longitude=point.longitude,
                        elevation=point.elevation,
                    )
                )

    if not points:
        raise GpxError("GPX file has no usable points with timestamps.")

    return GpxTrackIndex(points)
