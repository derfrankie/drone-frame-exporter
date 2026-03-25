# Drone Frame Extractor

Local-first macOS tool for extracting selected JPG frames from drone videos, syncing them against GPX tracks, and writing GPS-aware EXIF metadata.

## MVP Scope

- Select a local video file, GPX file, and output directory
- Determine export frames visually, not by entering arbitrary timestamps as the primary workflow
- Export only individual photos, never full image sequences
- Configure time sync with either:
  - manual offset between video time and GPX time
  - relative start time where video `00:00:00` maps to a chosen GPX timestamp
- Export selected frames as JPG via `ffmpeg`
- Write `DateTimeOriginal`, GPS latitude/longitude, and optional altitude via `exiftool`
- Write a JSON or CSV manifest per export
- Show a simple map-based location view so the current video/frame position can be understood spatially
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

The CLI remains a support tool for validating the export pipeline.
The primary end-user workflow for choosing photos should move into the UI, where frames are selected visually on a scrubber/timeline.

Export frames using the primary MVP interface:

```bash
python -m app.main export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 12.5,44.2,91.0 \
  --sync-mode offset \
  --offset-seconds 37
```

Export using a relative GPX start time:

```bash
python -m app.main export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 8.0,12.0 \
  --sync-mode relative-start \
  --start-time 2025-06-01T08:30:00Z
```

Generate a CSV manifest instead of JSON:

```bash
python -m app.main export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 3.5 \
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
- The final product should optimize for selecting a few best stills from a video, not for bulk frame extraction.
- A lightweight map panel is required in the UI so the user can see where the current frame is located along the GPX track.

## UI Direction

- Phase 2 remains a `PySide6` desktop UI on top of the existing core services.
- The UI should stay as platform-agnostic as practical even though macOS is the first target.
- Visual design should align with `https://onyx.scharz`.
- The UI should center around:
  - video preview with scrubber
  - single-photo marker selection
  - simple map-based geolocation preview for the current frame

## Local Sample Media

- Real test assets are available in `media/`.
- Current sample files:
  - `media/HOVER_20250611_1749636341404.MP4`
  - `media/2025-06-11_2315554315_Gravel-Fahrt.gpx`

## Next Steps

- PySide6 desktop MVP with:
  - file selection
  - Qt multimedia preview
  - timeline markers
  - simple map panel for frame location
  - export job progress
- optional GPX interpolation between track points
- packaged macOS app bundle
