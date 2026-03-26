from __future__ import annotations

import subprocess
from pathlib import Path

from core.models import GpxPoint
from core.utils import format_exif_timestamp, require_tool


def write_image_metadata(image_path: Path, timestamp, gpx_point: GpxPoint | None = None) -> None:
    exiftool = require_tool("exiftool")
    command = [
        exiftool,
        "-overwrite_original",
        f"-DateTimeOriginal={format_exif_timestamp(timestamp)}",
    ]

    if gpx_point is not None:
        lat_ref = "N" if gpx_point.latitude >= 0 else "S"
        lon_ref = "E" if gpx_point.longitude >= 0 else "W"
        command.extend(
            [
                f"-GPSLatitude={abs(gpx_point.latitude)}",
                f"-GPSLatitudeRef={lat_ref}",
                f"-GPSLongitude={abs(gpx_point.longitude)}",
                f"-GPSLongitudeRef={lon_ref}",
            ]
        )

        if gpx_point.elevation is not None:
            altitude_ref = "0" if gpx_point.elevation >= 0 else "1"
            command.extend(
                [
                    f"-GPSAltitude={abs(gpx_point.elevation)}",
                    f"-GPSAltitudeRef={altitude_ref}",
                ]
            )

    command.append(str(image_path))
    subprocess.run(command, capture_output=True, text=True, check=True)
