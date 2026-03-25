from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from core.errors import DroneFrameExtractorError
from core.export import export_frames
from core.gpx import load_gpx_track
from core.models import ExportFrameRequest
from core.sync import (
    SYNC_MODE_ABSOLUTE_VIDEO,
    SYNC_MODE_OFFSET,
    SYNC_MODE_RELATIVE_START,
)
from core.video import inspect_video

app = typer.Typer(help="Extract JPG frames from local drone videos and sync them with GPX tracks.")
console = Console()


@app.command("inspect-video")
def inspect_video_command(video: Path = typer.Option(..., exists=True, dir_okay=False, file_okay=True)) -> None:
    """Show detected video metadata from ffprobe."""
    metadata = inspect_video(video)
    table = Table(title="Video Metadata")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Path", str(metadata.path))
    table.add_row("Duration", f"{metadata.duration_seconds or 'unknown'}")
    table.add_row("Dimensions", f"{metadata.width or '?'}x{metadata.height or '?'}")
    table.add_row("FPS", f"{metadata.fps or 'unknown'}")
    table.add_row("Creation Time", metadata.creation_time.isoformat() if metadata.creation_time else "missing")
    table.add_row("Format", metadata.raw_format_name or "unknown")
    console.print(table)


@app.command("inspect-gpx")
def inspect_gpx_command(gpx: Path = typer.Option(..., exists=True, dir_okay=False, file_okay=True)) -> None:
    """Show basic GPX timing information."""
    index = load_gpx_track(gpx)
    table = Table(title="GPX Track Info")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Start", index.start_time.isoformat())
    table.add_row("End", index.end_time.isoformat())
    table.add_row("Point Count", str(len(index.points)))
    console.print(table)


@app.command("export")
def export_command(
    video: Path = typer.Option(..., exists=True, dir_okay=False, file_okay=True),
    gpx: Path = typer.Option(..., exists=True, dir_okay=False, file_okay=True),
    output_dir: Path = typer.Option(..., "--out", file_okay=False, dir_okay=True),
    times: str | None = typer.Option(
        None,
        help="Comma-separated video times in seconds, for example 12.5,44.2,91.0.",
    ),
    frame: list[float] = typer.Option(
        None,
        help="Optional compatibility mode: repeat --frame for each video position in seconds.",
    ),
    sync_mode: str = typer.Option(
        SYNC_MODE_OFFSET,
        help="offset, relative-start, or absolute-video",
    ),
    offset_seconds: float | None = typer.Option(None, help="Used in manual-offset mode."),
    start_time: str | None = typer.Option(
        None, help="ISO-8601 timestamp for relative-start mode, for example 2025-06-01T08:30:00Z."
    ),
    jpg_quality: int = typer.Option(2, min=2, max=31, help="Lower means better quality in ffmpeg."),
    manifest_format: str = typer.Option("json", help="json or csv"),
) -> None:
    """Export selected frames, write EXIF, and generate a manifest."""
    try:
        frame_values = _parse_frame_values(times=times, frame=frame)
        video_metadata = inspect_video(video)
        gpx_index = load_gpx_track(gpx)
        relative_start_time = _parse_iso_datetime(start_time) if start_time else None
        frame_requests = [ExportFrameRequest(frame_seconds=value) for value in frame_values]
        records, manifest_path = export_frames(
            video_metadata=video_metadata,
            gpx_index=gpx_index,
            output_dir=output_dir,
            frames=frame_requests,
            sync_mode=sync_mode,
            offset_seconds=offset_seconds,
            relative_start_time=relative_start_time,
            jpg_quality=jpg_quality,
            manifest_format=manifest_format,
        )
    except typer.BadParameter as exc:
        console.print(f"[red]Argument error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except DroneFrameExtractorError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # pragma: no cover - last-resort UX guard
        console.print(f"[red]Unexpected error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="Exported Frames")
    table.add_column("Frame (s)")
    table.add_column("Resolved Time")
    table.add_column("GPS")
    table.add_column("Output")
    for record in records:
        gps = f"{record.latitude:.6f}, {record.longitude:.6f}"
        table.add_row(
            f"{record.frame_seconds:.3f}",
            record.resolved_timestamp,
            gps,
            record.output_file,
        )
    console.print(table)
    console.print(f"Manifest written to {manifest_path}")


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _parse_frame_values(times: str | None, frame: list[float] | None) -> list[float]:
    if times:
        try:
            values = [float(part.strip()) for part in times.split(",") if part.strip()]
        except ValueError as exc:
            raise typer.BadParameter("--times must contain only comma-separated numbers.") from exc
        if values:
            return values

    if frame:
        return frame

    raise typer.BadParameter("Provide either --times or one or more --frame values.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
