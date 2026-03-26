# Drone Frame Extractor

Local-first desktop app for picking individual still frames from drone videos, aligning them against GPX tracks, and exporting the selected images with timestamp and GPS metadata.

The main workflow is visual:

1. load a video
2. optionally load a GPX track
3. scrub to the exact frames you want
4. align video time against GPX time when needed
5. export only the selected photos

No uploads or cloud processing are required.

## Status

This repository is an MVP with a working desktop UI and CLI.

What already works:

- local video loading
- optional GPX loading
- visual frame selection in a PySide6 UI
- play/pause, scrubbing, and `1` / `5` frame stepping
- `video-first` and `gpx-first` sync reference modes
- second offset and hour shift controls
- GPX cursor alignment on a zoomable OpenStreetMap view
- JPG export for standard footage
- TIFF export for wide-gamut / HDR-like footage
- EXIF timestamp writing and GPS tagging through `exiftool`
- JSON or CSV manifest export
- remembered last output folder in the UI

Current limitations:

- playback performance depends heavily on Qt Multimedia codec support on the local machine
- GPX matching uses nearest-point matching, not interpolation
- macOS is the main tested platform right now
- the map baselayer uses online OpenStreetMap tiles, so internet access is needed for the basemap

## Features

- Local-first workflow
  - no uploads
  - no cloud dependency
  - local file selection and local export
- Visual still selection
  - video scrubber
  - play / pause toggle
  - `-1`, `+1`, `-5`, `+5` frame stepping
  - marker-based selection of individual photos
- Flexible sync workflow
  - `offset`
  - `relative-start`
  - `absolute-video`
  - `video-first` or `gpx-first`
  - second-level offset
  - fixed hour shift from `-5 h` to `+5 h`
- Map-based positioning
  - zoomable OpenStreetMap-based track view
  - current video position on the GPX track
  - GPX cursor scrubbing
  - align current frame to GPX cursor
- Export pipeline
  - automatic export format selection
  - `jpg` for standard footage
  - `tiff` for detected wide-gamut / HDR-like footage
  - EXIF timestamp writing
  - optional GPS metadata when GPX is loaded
  - JSON or CSV manifest
  - custom filename middle segment

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
git clone https://github.com/derfrankie/drone-frame-exporter.git
cd drone-frame-exporter
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
drone-frame-extractor --help
.venv/bin/pytest
```

## Launching The App

After `pip install -e .`, the easiest way to launch the GUI is:

```bash
drone-frame-extractor ui
```

You can also launch it directly through Python:

```bash
python -m app.main ui
```

To open the UI with files preloaded:

```bash
drone-frame-extractor ui \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output
```

`--gpx` is optional. If no GPX is loaded, exports still work and use the resolved video timestamp plus the configured sync offset / shift, but no GPS tags are written.

## Desktop UI Workflow

### 1. Load your files

- choose a video
- optionally choose a GPX file
- choose an output folder

The UI remembers the last output folder you used.

### 2. Check sync settings

The Sync panel exposes:

- `Mode`
  - `offset`
  - `relative-start`
  - `absolute-video`
- `Reference`
  - `video-first`
  - `gpx-first`
- `Offset`
  - fine adjustment in seconds
- `Shift Hours`
  - coarse correction from `-5 h` to `+5 h`
  - default is `0 h`
- `Relative Start`
  - used only in `relative-start` mode

### 3. Scrub to the exact frame

- drag the playhead
- use `Play` / `Pause`
- use `-1 Frame`, `+1 Frame`, `-5 Frames`, `+5 Frames`
- click `Add Current Frame` to mark a photo candidate

Only marked frames are exported.

### 4. Align on the map

When a GPX file is loaded, the map shows:

- the GPX track on a real OpenStreetMap basemap
- the current resolved video position
- the GPX cursor position
- marker locations for selected photos

You can scrub on the track and use `Align Current Video Frame To GPX Cursor` to derive a practical hour shift plus second offset.

### 5. Export

The Export panel supports:

- `JPG Quality`
  - default `10`
- `Export Format`
  - automatically switches to `tiff` for detected wide-gamut / HDR-like sources
  - otherwise defaults to `jpg`
- `Manifest`
  - `json` or `csv`
- `Filename Middle`
  - inserted between the original filename stem and the export timestamp

Example output filename:

```text
HOVER_X1PROMAX_0080_hero_2024-12-31_13-40-55.tiff
```

Example manifest filename:

```text
HOVER_X1PROMAX_0080_hero_export.json
```

## CLI Usage

The CLI is useful for inspection, scripted export, and debugging the sync pipeline.

### Inspect video metadata

```bash
drone-frame-extractor inspect-video --video /path/to/video.mp4
```

### Inspect GPX timing

```bash
drone-frame-extractor inspect-gpx --gpx /path/to/track.gpx
```

### Export selected frames with GPX

```bash
drone-frame-extractor export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 12.5,44.2,91.0 \
  --sync-mode offset \
  --reference-mode video-first \
  --shift-hours 0 \
  --offset-seconds 37 \
  --export-format jpg \
  --jpg-quality 10 \
  --manifest-format json
```

### Export selected frames without GPX

```bash
drone-frame-extractor export \
  --video /path/to/video.mp4 \
  --out /path/to/output \
  --times 12.5,44.2 \
  --sync-mode offset \
  --shift-hours 0 \
  --offset-seconds 37
```

Without a GPX file, the exported image still receives `DateTimeOriginal`, but no GPS fields are written.

### Export with relative-start mode

```bash
drone-frame-extractor export \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out /path/to/output \
  --times 8.0,12.0 \
  --sync-mode relative-start \
  --reference-mode gpx-first \
  --shift-hours 0 \
  --start-time 2025-06-01T08:30:00Z
```

### Create a preview map HTML

```bash
drone-frame-extractor preview-map \
  --video /path/to/video.mp4 \
  --gpx /path/to/track.gpx \
  --out preview/video-placement.html \
  --times 4.0,18.5,33.2 \
  --sync-mode offset \
  --reference-mode video-first \
  --shift-hours 0 \
  --offset-seconds 37
```

## How Export Timing Works

This project is designed for the reality that drone-camera timestamps can be wrong.

The important rule is:

- with GPX loaded, the final export timestamp comes from the resolved sync result
- without GPX, the export timestamp falls back to the resolved video time plus offset / hour shift

Video metadata such as `creation_time`, `encoded_date`, or `tagged_date` is mainly used as an initial reference, not as absolute truth.

## Color And Export Format Detection

The app inspects the video stream and automatically prefers `tiff` when footage looks like wide-gamut / HDR-like material, for example:

- `10-bit` video
- `BT.2020` primaries
- `HLG` / `arib-std-b67`
- `PQ` / `smpte2084`

For standard footage such as typical `8-bit` AVC / BT.601 or BT.709 files, `jpg` remains the default.

## Output Metadata

For each exported still, the app can write:

- `DateTimeOriginal`
- GPS latitude / longitude
- optional altitude

The manifest also includes values such as:

- source video filename
- frame time in the source video
- resolved export timestamp
- GPX timestamp, if available
- latitude / longitude / altitude, if available
- sync mode
- offset seconds
- shift hours

## Repository Layout

```text
drone-frame-exporter/
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
      metadata.py
      sync.py
      video.py
  tests/
```

## Development

Run tests:

```bash
.venv/bin/pytest
```

Run the UI directly from source:

```bash
PYTHONPATH=src python -m app.main ui
```

## Roadmap

- better playback performance for difficult codecs
- timeline thumbnails
- GPX interpolation between track points
- packaging as a distributable macOS app bundle
- more visible timestamp-source diagnostics in the UI
