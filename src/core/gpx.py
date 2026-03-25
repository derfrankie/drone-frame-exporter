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

    def contains_time(self, target_time: datetime) -> bool:
        normalized = ensure_utc(target_time)
        return self.start_time <= normalized <= self.end_time

    def distance_to_range_seconds(self, target_time: datetime) -> float:
        normalized = ensure_utc(target_time)
        if normalized < self.start_time:
            return (self.start_time - normalized).total_seconds()
        if normalized > self.end_time:
            return (normalized - self.end_time).total_seconds()
        return 0.0

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

    def point_at_index(self, index: int) -> GpxPoint:
        bounded = min(max(index, 0), len(self.points) - 1)
        return self.points[bounded]

    def point_at_ratio(self, ratio: float) -> tuple[int, GpxPoint]:
        bounded_ratio = min(max(ratio, 0.0), 1.0)
        index = int(round((len(self.points) - 1) * bounded_ratio))
        return index, self.points[index]

    def downsampled_points(self, max_points: int = 1400) -> list[tuple[int, GpxPoint]]:
        if len(self.points) <= max_points:
            return list(enumerate(self.points))
        step = max(1, len(self.points) // max_points)
        samples = [(index, self.points[index]) for index in range(0, len(self.points), step)]
        if samples[-1][0] != len(self.points) - 1:
            samples.append((len(self.points) - 1, self.points[-1]))
        return samples

    def sampled_points_by_seconds(self, interval_seconds: float = 5.0) -> list[tuple[int, GpxPoint]]:
        if not self.points:
            return []
        samples: list[tuple[int, GpxPoint]] = [(0, self.points[0])]
        last_timestamp = self.points[0].timestamp
        for index, point in enumerate(self.points[1:], start=1):
            if (point.timestamp - last_timestamp).total_seconds() >= interval_seconds:
                samples.append((index, point))
                last_timestamp = point.timestamp
        if samples[-1][0] != len(self.points) - 1:
            samples.append((len(self.points) - 1, self.points[-1]))
        return samples


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
