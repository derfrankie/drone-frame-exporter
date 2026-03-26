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
        "format=duration:format_tags=creation_time,date,encoded_date,tagged_date:stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,bits_per_raw_sample,color_primaries,color_transfer,color_space:stream_tags=creation_time,date,encoded_date,tagged_date",
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

    creation_time = _pick_creation_time(video_format, video_stream)

    return VideoMetadata(
        path=video_path,
        duration_seconds=_parse_float(video_format.get("duration")),
        width=_parse_int(video_stream.get("width") if video_stream else None),
        height=_parse_int(video_stream.get("height") if video_stream else None),
        fps=_parse_fps(video_stream.get("r_frame_rate") if video_stream else None),
        creation_time=creation_time,
        raw_format_name=video_format.get("format_name"),
        codec_name=video_stream.get("codec_name") if video_stream else None,
        pixel_format=video_stream.get("pix_fmt") if video_stream else None,
        bit_depth=_parse_bit_depth(video_stream),
        color_primaries=video_stream.get("color_primaries") if video_stream else None,
        color_transfer=video_stream.get("color_transfer") if video_stream else None,
        color_space=video_stream.get("color_space") if video_stream else None,
    )


def extract_frame(
    video_path: Path,
    frame_seconds: float,
    output_path: Path,
    quality: int = 10,
    output_format: str = "jpg",
) -> None:
    ffmpeg = require_tool("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y", "-ss", f"{frame_seconds:.3f}", "-i", str(video_path), "-frames:v", "1"]
    if output_format == "jpg":
        command.extend(["-q:v", str(quality)])
    elif output_format == "tiff":
        command.extend(["-pix_fmt", "rgb48le", "-compression_algo", "lzw"])
    else:
        raise FrameExtractionError(f"Unsupported export format: {output_format}")
    command.append(str(output_path))
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
    normalized = value.strip().replace(" UTC", "+00:00").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None


def _pick_creation_time(video_format: dict, video_stream: dict | None) -> datetime | None:
    format_tags = video_format.get("tags", {})
    stream_tags = (video_stream or {}).get("tags", {})
    for key in ("creation_time", "date", "encoded_date", "tagged_date"):
        for tag_set in (format_tags, stream_tags):
            parsed = _parse_creation_time(tag_set.get(key))
            if parsed is not None:
                return parsed
    return None


def _parse_bit_depth(video_stream: dict | None) -> int | None:
    if not video_stream:
        return None
    raw_bits = _parse_int(video_stream.get("bits_per_raw_sample"))
    if raw_bits is not None:
        return raw_bits
    pix_fmt = video_stream.get("pix_fmt")
    if not pix_fmt:
        return None
    if "p10" in pix_fmt or "10le" in pix_fmt:
        return 10
    if "p12" in pix_fmt or "12le" in pix_fmt:
        return 12
    if "p16" in pix_fmt or "16le" in pix_fmt:
        return 16
    if "yuv420p" in pix_fmt or "rgb24" in pix_fmt:
        return 8
    return None


def is_wide_gamut_source(video_metadata: VideoMetadata) -> bool:
    primaries = (video_metadata.color_primaries or "").lower()
    transfer = (video_metadata.color_transfer or "").lower()
    return (
        (video_metadata.bit_depth or 0) >= 10
        or "bt2020" in primaries
        or transfer in {"arib-std-b67", "hlg", "smpte2084"}
    )
