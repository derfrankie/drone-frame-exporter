from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from core.gpx import GpxTrackIndex
from core.metadata import write_image_metadata
from core.models import ExportFrameRequest, ExportedFrameRecord, VideoMetadata
from core.sync import ResolvedFrameTime, resolve_frame_time
from core.utils import ensure_utc, format_filename_timestamp
from core.video import extract_frame


def export_frames(
    video_metadata: VideoMetadata,
    gpx_index: GpxTrackIndex | None,
    output_dir: Path,
    frames: list[ExportFrameRequest],
    sync_mode: str,
    offset_seconds: float | None = None,
    relative_start_time: datetime | None = None,
    shift_hours: float = 0.0,
    jpg_quality: int = 10,
    manifest_format: str = "json",
    filename_middle: str = "",
    reference_mode: str = "video-first",
    export_format: str = "jpg",
) -> tuple[list[ExportedFrameRecord], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not frames:
        raise ValueError("At least one frame selection is required.")

    records: list[ExportedFrameRecord] = []
    used_paths: set[Path] = set()
    for frame_request in frames:
        resolved = resolve_frame_time(
            frame_seconds=frame_request.frame_seconds,
            video_metadata=video_metadata,
            gpx_index=gpx_index,
            sync_mode=sync_mode,
            offset_seconds=offset_seconds,
            relative_start_time=relative_start_time,
            shift_hours=shift_hours,
            reference_mode=reference_mode,
        )
        output_path = _build_output_path(
            output_dir=output_dir,
            video_metadata=video_metadata,
            resolved=resolved,
            export_shift_hours=shift_hours,
            filename_middle=filename_middle,
            used_paths=used_paths,
            export_format=export_format,
        )
        extract_frame(
            video_path=video_metadata.path,
            frame_seconds=frame_request.frame_seconds,
            output_path=output_path,
            quality=jpg_quality,
            output_format=export_format,
        )
        export_timestamp = _apply_export_shift(resolved.resolved_timestamp, shift_hours)
        write_image_metadata(output_path, export_timestamp, resolved.gpx_point)
        records.append(_record_from_export(video_metadata, output_path, resolved, export_shift_hours=shift_hours))

    manifest_path = write_manifest(
        output_dir=output_dir,
        records=records,
        manifest_format=manifest_format,
        video_metadata=video_metadata,
        filename_middle=filename_middle,
    )
    return records, manifest_path


def write_manifest(
    output_dir: Path,
    records: list[ExportedFrameRecord],
    manifest_format: str,
    video_metadata: VideoMetadata,
    filename_middle: str = "",
) -> Path:
    manifest_format = manifest_format.lower()
    manifest_name = build_manifest_filename(video_metadata.path.stem, manifest_format, filename_middle)
    if manifest_format == "json":
        manifest_path = output_dir / manifest_name
        payload = [record.to_dict() for record in records]
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return manifest_path

    if manifest_format == "csv":
        manifest_path = output_dir / manifest_name
        fieldnames = list(ExportedFrameRecord.__dataclass_fields__.keys())
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())
        return manifest_path

    raise ValueError(f"Unsupported manifest format: {manifest_format}")


def _build_output_path(
    output_dir: Path,
    video_metadata: VideoMetadata,
    resolved: ResolvedFrameTime,
    export_shift_hours: float = 0.0,
    filename_middle: str = "",
    used_paths: set[Path] | None = None,
    export_format: str = "jpg",
) -> Path:
    filename = build_output_filename(
        original_stem=video_metadata.path.stem,
        timestamp=_apply_export_shift(resolved.resolved_timestamp, export_shift_hours),
        filename_middle=filename_middle,
        extension=export_format,
    )
    candidate = output_dir / filename
    if used_paths is None:
        return candidate

    counter = 2
    while candidate in used_paths or candidate.exists():
        candidate = output_dir / build_output_filename(
            original_stem=video_metadata.path.stem,
            timestamp=_apply_export_shift(resolved.resolved_timestamp, export_shift_hours),
            filename_middle=filename_middle,
            suffix=f"{counter:02d}",
            extension=export_format,
        )
        counter += 1
    used_paths.add(candidate)
    return candidate


def build_output_filename(
    original_stem: str,
    timestamp: datetime,
    filename_middle: str = "",
    suffix: str = "",
    extension: str = "jpg",
) -> str:
    parts = [original_stem]
    middle = filename_middle.strip().strip("_").strip()
    if middle:
        parts.append(middle)
    parts.append(format_filename_timestamp(timestamp))
    if suffix:
        parts.append(suffix)
    return "_".join(parts) + f".{extension}"


def build_manifest_filename(original_stem: str, manifest_format: str, filename_middle: str = "") -> str:
    parts = [original_stem]
    middle = filename_middle.strip().strip("_").strip()
    if middle:
        parts.append(middle)
    parts.append("export")
    return "_".join(parts) + f".{manifest_format}"


def _record_from_export(
    video_metadata: VideoMetadata,
    output_path: Path,
    resolved: ResolvedFrameTime,
    export_shift_hours: float = 0.0,
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
        resolved_timestamp=ensure_utc(_apply_export_shift(resolved.resolved_timestamp, export_shift_hours)).isoformat(),
        gpx_timestamp=ensure_utc(resolved.gpx_point.timestamp).isoformat() if resolved.gpx_point else None,
        latitude=resolved.gpx_point.latitude if resolved.gpx_point else None,
        longitude=resolved.gpx_point.longitude if resolved.gpx_point else None,
        elevation=resolved.gpx_point.elevation if resolved.gpx_point else None,
        output_file=str(output_path),
        sync_mode=resolved.sync_mode,
        offset_seconds=resolved.offset_seconds,
        shift_hours=export_shift_hours,
    )


def _apply_export_shift(timestamp: datetime, shift_hours: float) -> datetime:
    return timestamp + timedelta(hours=shift_hours)
