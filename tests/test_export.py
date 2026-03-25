from datetime import datetime, timezone

from core.models import GpxPoint
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
