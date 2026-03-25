from datetime import datetime, timezone
from pathlib import Path

from app.main import _build_preview_markers
from core.gpx import GpxTrackIndex
from core.models import GpxPoint, VideoMetadata
from core.sync import REFERENCE_VIDEO_FIRST, SYNC_MODE_OFFSET


def test_build_preview_markers_contains_video_start_end_and_frames() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=10.0,
        width=1280,
        height=720,
        fps=30.0,
        creation_time=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 48.1, 11.5, None),
            GpxPoint(datetime(2025, 1, 1, 12, 0, 10, tzinfo=timezone.utc), 48.2, 11.6, None),
        ]
    )

    markers = _build_preview_markers(
        video_metadata=video,
        gpx_index=gpx,
        frame_values=[2.5, 5.0],
        sync_mode=SYNC_MODE_OFFSET,
        offset_seconds=0.0,
        relative_start_time=None,
        shift_hours=0.0,
        reference_mode=REFERENCE_VIDEO_FIRST,
    )

    labels = [marker["label"] for marker in markers]
    assert labels == ["Video Start", "Video End", "Photo 1", "Photo 2"]
