from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.errors import SyncConfigurationError
from core.gpx import GpxTrackIndex
from core.models import GpxPoint, VideoMetadata
from core.utils import ensure_utc, ensure_utc_assuming_local

SYNC_MODE_OFFSET = "offset"
SYNC_MODE_MANUAL_OFFSET = SYNC_MODE_OFFSET
SYNC_MODE_RELATIVE_START = "relative-start"
SYNC_MODE_ABSOLUTE_VIDEO = "absolute-video"
REFERENCE_VIDEO_FIRST = "video-first"
REFERENCE_GPX_FIRST = "gpx-first"


@dataclass(slots=True)
class ResolvedFrameTime:
    video_time_seconds: float
    resolved_timestamp: datetime
    gpx_point: GpxPoint
    sync_mode: str
    offset_seconds: float | None
    shift_hours: float | None


def resolve_frame_time(
    frame_seconds: float,
    video_metadata: VideoMetadata,
    gpx_index: GpxTrackIndex,
    sync_mode: str,
    offset_seconds: float | None = None,
    relative_start_time: datetime | None = None,
    shift_hours: float = 0.0,
    reference_mode: str = REFERENCE_VIDEO_FIRST,
) -> ResolvedFrameTime:
    if frame_seconds < 0:
        raise SyncConfigurationError("Frame positions must be >= 0 seconds.")

    base_timestamp, applied_offset = _resolve_base_timestamp(
        video_metadata=video_metadata,
        gpx_index=gpx_index,
        sync_mode=sync_mode,
        offset_seconds=offset_seconds,
        relative_start_time=relative_start_time,
        shift_hours=shift_hours,
        reference_mode=reference_mode,
    )

    resolved_timestamp = base_timestamp + timedelta(seconds=frame_seconds)
    gpx_point = gpx_index.nearest_point(resolved_timestamp)
    return ResolvedFrameTime(
        video_time_seconds=frame_seconds,
        resolved_timestamp=resolved_timestamp,
        gpx_point=gpx_point,
        sync_mode=sync_mode,
        offset_seconds=applied_offset,
        shift_hours=shift_hours,
    )


def _resolve_base_timestamp(
    video_metadata: VideoMetadata,
    gpx_index: GpxTrackIndex,
    sync_mode: str,
    offset_seconds: float | None,
    relative_start_time: datetime | None,
    shift_hours: float,
    reference_mode: str,
) -> tuple[datetime, float | None]:
    if sync_mode in {SYNC_MODE_MANUAL_OFFSET, "manual-offset"}:
        if offset_seconds is None:
            raise SyncConfigurationError("Offset mode requires --offset-seconds.")
        directional_offset = offset_seconds if reference_mode == REFERENCE_VIDEO_FIRST else -offset_seconds
        if video_metadata.creation_time is not None:
            base = ensure_utc_assuming_local(video_metadata.creation_time) + timedelta(
                hours=shift_hours,
                seconds=directional_offset,
            )
            return base, offset_seconds
        base = gpx_index.start_time + timedelta(hours=shift_hours, seconds=directional_offset)
        return base, offset_seconds

    if sync_mode == SYNC_MODE_RELATIVE_START:
        if relative_start_time is None:
            raise SyncConfigurationError("Relative start mode requires --start-time.")
        normalized = ensure_utc(relative_start_time) + timedelta(hours=shift_hours)
        offset = (normalized - gpx_index.start_time).total_seconds()
        return normalized, offset

    if sync_mode == SYNC_MODE_ABSOLUTE_VIDEO:
        if video_metadata.creation_time is None:
            raise SyncConfigurationError(
                "Absolute video mode requires a readable video creation timestamp."
            )
        base = ensure_utc_assuming_local(video_metadata.creation_time) + timedelta(hours=shift_hours)
        return base, 0.0

    raise SyncConfigurationError(f"Unsupported sync mode: {sync_mode}")
