from datetime import datetime, timezone
from pathlib import Path

from core.gpx import GpxTrackIndex
from core.models import GpxPoint, VideoMetadata
from core.sync import (
    SYNC_MODE_OFFSET,
    SYNC_MODE_RELATIVE_START,
    resolve_frame_time,
)


def test_manual_offset_uses_video_creation_time_when_available() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        creation_time=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(datetime(2025, 1, 1, 12, 0, 9, tzinfo=timezone.utc), 48.1, 11.5, 500.0),
            GpxPoint(datetime(2025, 1, 1, 12, 0, 12, tzinfo=timezone.utc), 48.2, 11.6, 501.0),
        ]
    )

    resolved = resolve_frame_time(10.0, video, gpx, SYNC_MODE_OFFSET, offset_seconds=1.0)

    assert resolved.resolved_timestamp == datetime(2025, 1, 1, 12, 0, 11, tzinfo=timezone.utc)
    assert resolved.gpx_point.latitude == 48.2


def test_relative_start_maps_zero_to_requested_gpx_time() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        creation_time=None,
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 48.1, 11.5, 500.0),
            GpxPoint(datetime(2025, 1, 1, 12, 0, 5, tzinfo=timezone.utc), 48.2, 11.6, 501.0),
            GpxPoint(datetime(2025, 1, 1, 12, 0, 9, tzinfo=timezone.utc), 48.3, 11.7, 502.0),
        ]
    )

    resolved = resolve_frame_time(
        4.0,
        video,
        gpx,
        SYNC_MODE_RELATIVE_START,
        relative_start_time=datetime(2025, 1, 1, 12, 0, 5, tzinfo=timezone.utc),
    )

    assert resolved.resolved_timestamp == datetime(2025, 1, 1, 12, 0, 9, tzinfo=timezone.utc)
    assert resolved.gpx_point.longitude == 11.7
