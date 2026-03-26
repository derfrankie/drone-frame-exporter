from datetime import datetime, timezone

from core.export import build_manifest_filename, build_output_filename
from core.models import ExportedFrameRecord, GpxPoint
from core.utils import format_exif_timestamp, format_filename_timestamp


def test_filename_timestamp_format_is_stable() -> None:
    timestamp = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert format_filename_timestamp(timestamp) == "2025-06-01_08-30-00"


def test_exif_timestamp_format_is_stable() -> None:
    timestamp = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert format_exif_timestamp(timestamp) == "2025:06:01 08:30:00"


def test_gpx_point_keeps_optional_altitude() -> None:
    point = GpxPoint(
        timestamp=datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc),
        latitude=48.123,
        longitude=11.456,
        elevation=None,
    )
    assert point.elevation is None


def test_build_output_filename_inserts_middle_between_original_and_timestamp() -> None:
    timestamp = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert (
        build_output_filename("HOVER_20250611_1749636341404", timestamp, "hero")
        == "HOVER_20250611_1749636341404_hero_2025-06-01_08-30-00.jpg"
    )


def test_build_output_filename_skips_empty_middle() -> None:
    timestamp = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert (
        build_output_filename("HOVER_20250611_1749636341404", timestamp, "")
        == "HOVER_20250611_1749636341404_2025-06-01_08-30-00.jpg"
    )


def test_build_output_filename_appends_suffix_for_duplicates() -> None:
    timestamp = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert (
        build_output_filename("HOVER_20250611_1749636341404", timestamp, "hero", "02")
        == "HOVER_20250611_1749636341404_hero_2025-06-01_08-30-00_02.jpg"
    )


def test_build_manifest_filename_uses_video_name_and_middle() -> None:
    assert (
        build_manifest_filename("HOVER_20250611_1749636341404", "json", "hero")
        == "HOVER_20250611_1749636341404_hero_export.json"
    )


def test_build_output_filename_supports_tiff_extension() -> None:
    timestamp = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert (
        build_output_filename("HOVER_20250611_1749636341404", timestamp, "hero", extension="tiff")
        == "HOVER_20250611_1749636341404_hero_2025-06-01_08-30-00.tiff"
    )


def test_export_record_allows_missing_gpx_metadata() -> None:
    record = ExportedFrameRecord(
        source_video="video.mp4",
        frame_seconds=12.5,
        video_timestamp="2025-06-01T08:30:00+00:00",
        resolved_timestamp="2025-06-01T08:30:12.500000+00:00",
        gpx_timestamp=None,
        latitude=None,
        longitude=None,
        elevation=None,
        output_file="frame.jpg",
        sync_mode="offset",
        offset_seconds=0.0,
        shift_hours=0.0,
    )
    assert record.to_dict()["gpx_timestamp"] is None
