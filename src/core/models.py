from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class VideoMetadata:
    path: Path
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    creation_time: datetime | None
    raw_format_name: str | None
    codec_name: str | None = None
    pixel_format: str | None = None
    bit_depth: int | None = None
    color_primaries: str | None = None
    color_transfer: str | None = None
    color_space: str | None = None


@dataclass(slots=True)
class GpxPoint:
    timestamp: datetime
    latitude: float
    longitude: float
    elevation: float | None = None


@dataclass(slots=True)
class ExportFrameRequest:
    frame_seconds: float


@dataclass(slots=True)
class ExportedFrameRecord:
    source_video: str
    frame_seconds: float
    video_timestamp: str | None
    resolved_timestamp: str
    gpx_timestamp: str | None
    latitude: float | None
    longitude: float | None
    elevation: float | None
    output_file: str
    sync_mode: str
    offset_seconds: float | None
    shift_hours: float | None

    def to_dict(self) -> dict:
        return asdict(self)
