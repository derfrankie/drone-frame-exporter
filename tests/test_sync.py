from datetime import datetime, timezone
from pathlib import Path

from core.gpx import GpxTrackIndex
from core.models import GpxPoint, VideoMetadata
from core.sync import (
    REFERENCE_GPX_FIRST,
    REFERENCE_VIDEO_FIRST,
    SYNC_MODE_OFFSET,
    SYNC_MODE_RELATIVE_START,
    resolve_frame_time,
)
from core.video import is_wide_gamut_source
from core.video import _parse_creation_time


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
    assert resolved.shift_hours == 0.0


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


def test_shift_hours_moves_video_time_before_matching_gpx() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        creation_time=datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 48.1, 11.5, 500.0),
            GpxPoint(datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc), 48.2, 11.6, 501.0),
        ]
    )

    resolved = resolve_frame_time(
        1.0,
        video,
        gpx,
        SYNC_MODE_OFFSET,
        offset_seconds=0.0,
        shift_hours=-2.0,
    )

    assert resolved.resolved_timestamp == datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
    assert resolved.gpx_point.longitude == 11.6
    assert resolved.shift_hours == -2.0


def test_naive_video_creation_time_is_treated_as_local_time() -> None:
    local_tz = datetime.now().astimezone().tzinfo
    naive_creation = datetime(2025, 7, 19, 13, 41, 15)
    expected_utc = naive_creation.replace(tzinfo=local_tz).astimezone(timezone.utc)
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=45.0,
        width=7680,
        height=4320,
        fps=30.0,
        creation_time=naive_creation,
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(expected_utc, 48.1, 11.5, 500.0),
            GpxPoint(expected_utc.replace(second=(expected_utc.second + 1) % 60), 48.2, 11.6, 501.0),
        ]
    )

    resolved = resolve_frame_time(
        0.0,
        video,
        gpx,
        SYNC_MODE_OFFSET,
        offset_seconds=0.0,
    )

    assert resolved.resolved_timestamp == expected_utc


def test_gpx_first_uses_inverse_offset_direction() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        creation_time=datetime(2025, 1, 1, 12, 0, 10, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 48.1, 11.5, 500.0),
            GpxPoint(datetime(2025, 1, 1, 12, 0, 10, tzinfo=timezone.utc), 48.2, 11.6, 501.0),
        ]
    )

    video_first = resolve_frame_time(
        0.0,
        video,
        gpx,
        SYNC_MODE_OFFSET,
        offset_seconds=-10.0,
        reference_mode=REFERENCE_VIDEO_FIRST,
    )
    gpx_first = resolve_frame_time(
        0.0,
        video,
        gpx,
        SYNC_MODE_OFFSET,
        offset_seconds=10.0,
        reference_mode=REFERENCE_GPX_FIRST,
    )

    assert video_first.resolved_timestamp == gpx_first.resolved_timestamp


def test_wide_gamut_detection_prefers_tiff_like_workflow() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=45.0,
        width=3840,
        height=2160,
        fps=30.0,
        creation_time=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
        codec_name="hevc",
        pixel_format="yuv420p10le",
        bit_depth=10,
        color_primaries="bt2020",
        color_transfer="arib-std-b67",
        color_space="bt2020nc",
    )
    assert is_wide_gamut_source(video) is True


def test_offset_mode_without_gpx_uses_video_timestamp_only() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        creation_time=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
    )

    resolved = resolve_frame_time(
        10.0,
        video,
        None,
        SYNC_MODE_OFFSET,
        offset_seconds=5.0,
    )

    assert resolved.resolved_timestamp == datetime(2025, 1, 1, 12, 0, 15, tzinfo=timezone.utc)
    assert resolved.gpx_point is None


def test_parse_creation_time_supports_mediainfo_utc_format() -> None:
    parsed = _parse_creation_time("2024-12-31 13:40:45 UTC")
    assert parsed == datetime(2024, 12, 31, 13, 40, 45, tzinfo=timezone.utc)
