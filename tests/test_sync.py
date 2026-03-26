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
from core.video import (
    _parse_creation_time,
    _parse_embedded_gps_lines,
    _parse_embedded_gps_points,
    _rebase_gps_points,
    is_wide_gamut_source,
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


def test_shift_hours_no_longer_changes_sync_mapping() -> None:
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

    assert resolved.resolved_timestamp == datetime(2025, 1, 1, 14, 0, 1, tzinfo=timezone.utc)
    assert resolved.gpx_point.longitude == 11.6
    assert resolved.shift_hours == 0.0


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


def test_offset_mode_uses_same_offset_direction_for_both_authorities() -> None:
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

    assert video_first.resolved_timestamp == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert gpx_first.resolved_timestamp == datetime(2025, 1, 1, 12, 0, 20, tzinfo=timezone.utc)


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


def test_parse_embedded_gps_points_reads_exiftool_json() -> None:
    points = _parse_embedded_gps_points(
        [
            {
                "GPSDateTime": "2025:07:19 09:12:43.100",
                "GPSLatitude": 48.5602,
                "GPSLongitude": 8.2202,
                "GPSAltitude": 959.66,
            }
        ]
    )
    assert len(points) == 1
    assert points[0].timestamp == datetime(2025, 7, 19, 9, 12, 43, 100000, tzinfo=timezone.utc)
    assert points[0].latitude == 48.5602


def test_parse_embedded_gps_lines_reads_multiple_points() -> None:
    points = _parse_embedded_gps_lines(
        "2025:07:19 09:12:43.000,48.560186,8.2201903,959.66\n"
        "2025:07:19 09:12:43.100,48.5601865,8.2201897,959.596\n"
    )
    assert len(points) == 2
    assert points[1].longitude == 8.2201897


def test_embedded_gps_offset_can_start_before_video_timestamp() -> None:
    video = VideoMetadata(
        path=Path("video.mp4"),
        duration_seconds=60.0,
        width=3840,
        height=2160,
        fps=59.94,
        creation_time=datetime(2025, 7, 19, 9, 13, 10, tzinfo=timezone.utc),
        raw_format_name="mov,mp4",
    )
    gpx = GpxTrackIndex(
        [
            GpxPoint(datetime(2025, 7, 19, 9, 12, 43, tzinfo=timezone.utc), 48.56, 8.22, 959.66),
            GpxPoint(datetime(2025, 7, 19, 9, 12, 44, tzinfo=timezone.utc), 48.57, 8.23, 958.0),
        ]
    )

    resolved = resolve_frame_time(
        0.0,
        video,
        gpx,
        SYNC_MODE_OFFSET,
        offset_seconds=-27.0,
    )

    assert resolved.gpx_point.timestamp == datetime(2025, 7, 19, 9, 12, 43, tzinfo=timezone.utc)


def test_rebase_gps_points_aligns_embedded_track_to_video_start() -> None:
    points = [
        GpxPoint(datetime(2025, 4, 3, 16, 0, 14, 99000, tzinfo=timezone.utc), 49.08, 9.19, 196.0),
        GpxPoint(datetime(2025, 4, 3, 16, 0, 15, 99000, tzinfo=timezone.utc), 49.09, 9.20, 197.0),
    ]
    rebased = _rebase_gps_points(
        points,
        datetime(2024, 8, 16, 14, 8, 59, tzinfo=timezone.utc),
    )
    assert rebased[0].timestamp == datetime(2024, 8, 16, 14, 8, 59, tzinfo=timezone.utc)
    assert rebased[1].timestamp == datetime(2024, 8, 16, 14, 9, 0, tzinfo=timezone.utc)
