from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from core.gpx import GpxTrackIndex
from core.metadata import write_image_metadata
from core.models import ExportFrameRequest, ExportedFrameRecord, VideoMetadata
from core.sync import ResolvedFrameTime, resolve_frame_time
from core.utils import ensure_utc, format_filename_timestamp
from core.video import extract_frame


def export_frames(
    video_metadata: VideoMetadata,
    gpx_index: GpxTrackIndex,
    output_dir: Path,
    frames: list[ExportFrameRequest],
    sync_mode: str,
    offset_seconds: float | None = None,
    relative_start_time: datetime | None = None,
    jpg_quality: int = 2,
    manifest_format: str = "json",
) -> tuple[list[ExportedFrameRecord], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not frames:
        raise ValueError("At least one frame selection is required.")

    records: list[ExportedFrameRecord] = []
    for frame_request in frames:
        resolved = resolve_frame_time(
            frame_seconds=frame_request.frame_seconds,
            video_metadata=video_metadata,
            gpx_index=gpx_index,
            sync_mode=sync_mode,
            offset_seconds=offset_seconds,
            relative_start_time=relative_start_time,
        )
        output_path = _build_output_path(output_dir, resolved)
        extract_frame(
            video_path=video_metadata.path,
            frame_seconds=frame_request.frame_seconds,
            output_path=output_path,
            quality=jpg_quality,
        )
        write_image_metadata(output_path, resolved.resolved_timestamp, resolved.gpx_point)
        records.append(_record_from_export(video_metadata, output_path, resolved))

    manifest_path = write_manifest(output_dir, records, manifest_format)
    return records, manifest_path


def write_manifest(output_dir: Path, records: list[ExportedFrameRecord], manifest_format: str) -> Path:
    manifest_format = manifest_format.lower()
    if manifest_format == "json":
        manifest_path = output_dir / "export-manifest.json"
        payload = [record.to_dict() for record in records]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return manifest_path

    if manifest_format == "csv":
        manifest_path = output_dir / "export-manifest.csv"
        fieldnames = list(ExportedFrameRecord.__dataclass_fields__.keys())
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())
        return manifest_path

    raise ValueError(f"Unsupported manifest format: {manifest_format}")


def _build_output_path(output_dir: Path, resolved: ResolvedFrameTime) -> Path:
    filename = f"{format_filename_timestamp(resolved.gpx_point.timestamp)}.jpg"
    return output_dir / filename


def _record_from_export(
    video_metadata: VideoMetadata,
    output_path: Path,
    resolved: ResolvedFrameTime,
) -> ExportedFrameRecord:
    video_timestamp = (
        ensure_utc(video_metadata.creation_time).isoformat()
        if video_metadata.creation_time is not None
        else None
    )
    return ExportedFrameRecord(
        source_video=str(video_metadata.path),
        frame_seconds=resolved.video_time_seconds,
        video_timestamp=video_timestamp,
        resolved_timestamp=ensure_utc(resolved.resolved_timestamp).isoformat(),
        gpx_timestamp=ensure_utc(resolved.gpx_point.timestamp).isoformat(),
        latitude=resolved.gpx_point.latitude,
        longitude=resolved.gpx_point.longitude,
        elevation=resolved.gpx_point.elevation,
        output_file=str(output_path),
        sync_mode=resolved.sync_mode,
        offset_seconds=resolved.offset_seconds,
    )
