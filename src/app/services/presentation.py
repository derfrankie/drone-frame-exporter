from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.gpx import GpxTrackIndex
from core.models import VideoMetadata
from core.sync import resolve_frame_time


@dataclass(slots=True)
class TrackMarker:
    label: str
    kind: str
    color: str
    frame_seconds: float
    timestamp: str
    latitude: float
    longitude: float


@dataclass(slots=True)
class TrackSample:
    index: int
    timestamp: str
    latitude: float
    longitude: float


def build_track_markers(
    video_metadata: VideoMetadata,
    gpx_index: GpxTrackIndex,
    frame_values: list[float],
    sync_mode: str,
    offset_seconds: float | None,
    relative_start_time: datetime | None,
    shift_hours: float,
    reference_mode: str,
) -> list[TrackMarker]:
    marker_specs = [("Video Start", 0.0, "#7ae582", "start")]
    if video_metadata.duration_seconds is not None:
        marker_specs.append(("Video End", video_metadata.duration_seconds, "#ff5964", "end"))
    for index, frame_seconds in enumerate(frame_values, start=1):
        marker_specs.append((f"Photo {index}", frame_seconds, "#7bdff2", "frame"))

    markers: list[TrackMarker] = []
    for label, frame_seconds, color, kind in marker_specs:
        resolved = resolve_frame_time(
            frame_seconds=frame_seconds,
            video_metadata=video_metadata,
            gpx_index=gpx_index,
            sync_mode=sync_mode,
            offset_seconds=offset_seconds,
            relative_start_time=relative_start_time,
            shift_hours=shift_hours,
            reference_mode=reference_mode,
        )
        markers.append(
            TrackMarker(
                label=label,
                kind=kind,
                color=color,
                frame_seconds=frame_seconds,
                timestamp=resolved.gpx_point.timestamp.isoformat(),
                latitude=resolved.gpx_point.latitude,
                longitude=resolved.gpx_point.longitude,
            )
        )
    return markers


def build_track_samples(gpx_index: GpxTrackIndex, interval_seconds: float = 5.0) -> list[TrackSample]:
    return [
        TrackSample(
            index=index,
            timestamp=point.timestamp.isoformat(),
            latitude=point.latitude,
            longitude=point.longitude,
        )
        for index, point in gpx_index.sampled_points_by_seconds(interval_seconds=interval_seconds)
    ]
