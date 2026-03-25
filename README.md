# Drone Frame Extractor

Local-first macOS tool for extracting selected JPG frames from drone videos, syncing them against GPX tracks, and writing GPS-aware EXIF metadata.

## MVP Scope

- Select a local video file, GPX file, and output directory
- Configure time sync with either:
  - manual offset between video time and GPX time
  - relative start time where video `00:00:00` maps to a chosen GPX timestamp
- Export selected frames as JPG via `ffmpeg`
- Write `DateTimeOriginal`, GPS latitude/longitude, and optional altitude via `exiftool`
- Write a JSON or CSV manifest per export
- Run fully offline on macOS

## Technical Decisions

- Python + `PySide6` is a good fit for the local desktop MVP:
  - native-enough desktop UX on macOS
  - solid file dialogs and timeline-friendly widgets
  - easy reuse of the same core services between CLI and UI
- CLI first, UI second:
  - the export and sync pipeline becomes testable before we add player controls
  - the later UI can call the same `core/*` modules
- Planned preview approach for the UI MVP: `Qt Multimedia`
  - simpler for a responsive scrubber/player than building a custom ffmpeg thumbnail transport
  - keeps frame export authoritative through `ffmpeg`, while playback stays in Qt
  - if codec support becomes unreliable for a specific drone format, we can add ffmpeg-backed preview thumbnails later without changing the export core

## External Tools

Install these tools on macOS before using the CLI:

```bash
brew install ffmpeg exiftool
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI Usage

Export two frames using a manual offset:

```bash
drone-frame-extractor export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --output-dir /path/to/output \
  --frame 12.5 \
  --frame 37.2 \
  --sync-mode manual-offset \
  --offset-seconds 4.25
```

Export using a relative GPX start time:

```bash
drone-frame-extractor export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --output-dir /path/to/output \
  --frame 8.0 \
  --sync-mode relative-start \
  --start-time 2025-06-01T08:30:00Z
```

Generate a CSV manifest instead of JSON:

```bash
drone-frame-extractor export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --output-dir /path/to/output \
  --frame 3.5 \
  --manifest-format csv
```

Inspect detected video metadata:

```bash
drone-frame-extractor inspect-video --video /path/to/video.mp4
```

Inspect GPX timing:

```bash
drone-frame-extractor inspect-gpx --gpx /path/to/track.gpx
```

## Repository Layout

```text
drone-frame-extractor/
  README.md
  pyproject.toml
  src/
    app/
      main.py
      ui/
      services/
      models/
    core/
      video.py
      gpx.py
      sync.py
      export.py
      metadata.py
  tests/
  docs/
```

## Assumptions

- Initial MVP uses the nearest GPX point; interpolation is intentionally deferred.
- If the video has no trustworthy creation timestamp, the CLI still works with manual offset or relative start time.
- Timestamps are normalized to UTC internally when GPX timestamps include timezone data.

## Next Steps

- PySide6 desktop MVP with:
  - file selection
  - Qt multimedia preview
  - timeline markers
  - export job progress
- optional GPX interpolation between track points
- packaged macOS app bundle
