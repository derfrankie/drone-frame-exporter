# Drone Frame Extractor

Local-first desktop tool for extracting individual JPG stills from drone videos, matching them to GPX tracks, and writing timestamp and GPS metadata into the exported images.

This project is built for workflows where you want to scrub through a video, pick only a few good frames, align the video against a GPX track, and export geotagged photos without uploading anything to a cloud service.

## Status

This repository is currently an MVP.

What already works:

- local video + GPX loading
- PySide6 desktop UI for visual frame selection
- single-photo marker workflow
- frame stepping by `1` and `5` frames
- GPX alignment with reference mode selection
- hour shift and second offset controls
- JPG export through `ffmpeg`
- EXIF timestamp and GPS writing through `exiftool`
- JSON or CSV manifest export
- zoomable online map with OpenStreetMap tiles in the UI

Current limitations:

- playback performance depends on codec/container support in Qt Multimedia
- GPX matching currently uses the nearest GPX point, not interpolation
- macOS is the primary tested platform right now
- the map uses online tiles, so internet access is required for the basemap

## Why This Exists

Many drone videos contain usable still frames, but turning them into clean, timestamped, geotagged JPGs is awkward. This tool tries to make that workflow direct:

1. load a video
2. load a GPX track
3. visually scrub to the frames you want
4. align video time against GPX time
5. export only the selected stills

## Features

- Local-first workflow
  - no uploads
  - no cloud processing
  - local file selection and local export
- Visual still selection
  - video scrubber
  - add/remove individual photo markers
  - step playhead by `1` or `5` frames
- GPX-aware sync workflow
  - `video-first` or `gpx-first` reference mode
  - second-level offset
  - fixed hour shift selection
  - relative-start and absolute-video modes
- Map-based positioning
  - zoomable OpenStreetMap-based track view
  - GPX cursor and video-position visualization
  - click/scrub on the track to help alignment
- Export pipeline
  - JPG extraction with `ffmpeg`
  - EXIF metadata via `exiftool`
  - JSON or CSV manifest
  - optional custom filename middle segment

## Tech Stack

- Python 3.11+
- PySide6
- ffmpeg / ffprobe
- gpxpy
- exiftool
- typer
- rich

## Installation

### 1. Install system tools

On macOS with Homebrew:

```bash
brew install ffmpeg exiftool
```

### 2. Clone the repository

```bash
git clone <your-repo-url>
cd hover-frame-extractor
```

### 3. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Verify the installation

```bash
python -m app.main --help
pytest
```

## Quick Start

Launch the desktop UI:

```bash
python -m app.main ui
```

## Desktop UI Workflow

### 1. Load files

- choose a video file
- choose a GPX file
- choose an output folder

### 2. Set the sync model

The UI exposes two concepts that matter:

- `Reference`
  - `video-first`: interpret the offset from the video timeline toward the GPX timeline
  - `gpx-first`: interpret the offset from the GPX timeline toward the video timeline
- `Shift Hours`
  - coarse timezone/daylight-saving style correction
  - currently offered as a fixed dropdown from `-5 h` to `+5 h`

You can then refine with:

- `Offset`: precise offset in seconds
- `Relative Start`: map video time `00:00:00` to a chosen GPX time when using `relative-start`

### 3. Scrub visually

- drag the video playhead
- use `-1 Frame`, `+1 Frame`, `-5 Frames`, `+5 Frames`
- add photo markers only on the frames you want to export

### 4. Use the map for alignment

- inspect the current video position against the GPX track
- move the GPX cursor with the track controls
- use `Align Current Video Frame To GPX Cursor` to derive shift/offset values

### 5. Export

- choose JPG quality
- optionally provide a filename middle segment
- export the selected photos

Example output filename:

```text
HOVER_20250611_1749636341404_hero_2025-06-01_08-30-00.jpg
```

Example manifest filename:

```text
HOVER_20250611_1749636341404_hero_export.json
```

## CLI Usage

The CLI is useful for inspection, debugging, scripted exports, and validating the sync pipeline. The main end-user workflow is the desktop UI.

### Inspect video metadata

```bash
python -m app.main inspect-video --video /path/to/video.mp4
```

### Inspect GPX timing

```bash
python -m app.main inspect-gpx --gpx /path/to/track.gpx
```

### Export selected frames

```bash
python -m app.main export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 12.5,44.2,91.0 \
  --sync-mode offset \
  --reference-mode video-first \
  --shift-hours 2 \
  --offset-seconds 37 \
  --jpg-quality 10 \
  --manifest-format json
```

### Export with relative-start mode

```bash
python -m app.main export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 8.0,12.0 \
  --sync-mode relative-start \
  --reference-mode gpx-first \
  --shift-hours 2 \
  --start-time 2025-06-01T08:30:00Z
```

### Create a preview map HTML

```bash
python -m app.main preview-map \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out preview/video-placement.html \
  --times 4.0,18.5,33.2 \
  --sync-mode offset \
  --reference-mode video-first \
  --shift-hours 2 \
  --offset-seconds 37
```

## Sync Model

This project has to deal with a messy real-world problem: video timestamps and GPX timestamps often do not line up cleanly.

The tool currently supports:

- `offset`
  - the main practical mode
  - apply a second-level offset between the two timelines
- `relative-start`
  - define where video time `00:00:00` should land on the GPX timeline
- `absolute-video`
  - trust the video timestamp directly

Important details:

- GPX timestamps are treated as UTC
- naive video timestamps may come from local device time
- the UI lets you choose who should be treated as the reference timeline
- the UI also shows when a resolved frame time falls outside the GPX window and is being clamped to the nearest track endpoint

## Output

For each exported still, the tool can write:

- `DateTimeOriginal`
- GPS latitude / longitude
- optional altitude

It also writes a manifest containing data such as:

- source video
- frame position in seconds
- resolved timestamp
- GPX timestamp
- latitude / longitude / elevation
- output filename
- sync mode
- offset
- hour shift

## Repository Layout

```text
hover-frame-extractor/
  README.md
  pyproject.toml
  src/
    app/
      main.py
      services/
      ui/
    core/
      export.py
      gpx.py
      map_preview.py
      metadata.py
      sync.py
      video.py
  tests/
  docs/
```

## Development

Run tests:

```bash
pytest
```

Run the CLI:

```bash
python -m app.main --help
```

Run the UI:

```bash
python -m app.main ui
```

## Roadmap

- smoother playback and codec fallback handling
- GPX interpolation between points
- richer marker editing on the map
- persistent project/session files
- packaged app builds for macOS

## Known Caveats

- Some videos produce decoder warnings in the terminal through the Qt/FFmpeg stack.
- Playback responsiveness depends heavily on codec/container support and hardware decoding.
- If the resolved timestamp is outside the GPX time window, the track position will clamp to the nearest start/end point.
- Online map tiles are currently used for the zoomable basemap.

## License

Add your preferred license here.
