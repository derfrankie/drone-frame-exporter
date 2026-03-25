from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from core.errors import FrameExtractionError, VideoInspectionError
from core.models import VideoMetadata
from core.utils import require_tool


def inspect_video(video_path: Path) -> VideoMetadata:
    ffprobe = require_tool("ffprobe")
    if not video_path.exists():
        raise VideoInspectionError(f"Video file does not exist: {video_path}")

    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "format=duration:format_tags=creation_time:stream=codec_type,width,height,r_frame_rate",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise VideoInspectionError(result.stderr.strip() or "ffprobe failed to inspect video.")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoInspectionError("ffprobe returned invalid JSON.") from exc

    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    video_format = payload.get("format", {})

    return VideoMetadata(
        path=video_path,
        duration_seconds=_parse_float(video_format.get("duration")),
        width=_parse_int(video_stream.get("width") if video_stream else None),
        height=_parse_int(video_stream.get("height") if video_stream else None),
        fps=_parse_fps(video_stream.get("r_frame_rate") if video_stream else None),
        creation_time=_parse_creation_time(video_format.get("tags", {}).get("creation_time")),
        raw_format_name=video_format.get("format_name"),
    )


def extract_frame(video_path: Path, frame_seconds: float, output_path: Path, quality: int = 2) -> None:
    ffmpeg = require_tool("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-ss",
        f"{frame_seconds:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        str(quality),
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FrameExtractionError(
            result.stderr.strip() or f"ffmpeg failed to export frame at {frame_seconds:.3f}s."
        )


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    numerator, _, denominator = value.partition("/")
    try:
        if denominator:
            return float(numerator) / float(denominator)
        return float(numerator)
    except ValueError:
        return None


def _parse_creation_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
