from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from core.errors import ToolMissingError


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        path = _find_tool_in_common_locations(name)
    if not path:
        raise ToolMissingError(
            f"Required tool '{name}' was not found in PATH. Install it first."
        )
    return path


def _find_tool_in_common_locations(name: str) -> str | None:
    search_dirs = [
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
    ]
    for directory in search_dirs:
        candidate = directory / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_utc_assuming_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        return dt.replace(tzinfo=local_tz).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def format_filename_timestamp(dt: datetime) -> str:
    utc_dt = ensure_utc(dt)
    return utc_dt.strftime("%Y-%m-%d_%H-%M-%S")


def format_exif_timestamp(dt: datetime) -> str:
    utc_dt = ensure_utc(dt)
    return utc_dt.strftime("%Y:%m:%d %H:%M:%S")
