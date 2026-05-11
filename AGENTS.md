# AGENTS.md

## Project

Local-first Python desktop/CLI app for extracting still frames from drone videos, syncing them against GPS tracks, and exporting images with timestamp/GPS metadata.

## Layout

- `src/app/main.py`: Typer CLI entrypoint.
- `src/app/ui/main_window.py`: PySide6 desktop UI and file selection flow.
- `src/app/services/presentation.py`: UI-facing track/frame presentation helpers.
- `src/core/gpx.py`: GPX/FIT track loading and `GpxTrackIndex`.
- `src/core/video.py`: ffprobe/video inspection and embedded GPS extraction.
- `src/core/sync.py`: timestamp authority and frame-to-track sync logic.
- `src/core/export.py`: frame extraction, manifest generation, metadata write orchestration.
- `tests/`: pytest coverage for core logic and CLI helpers.

## Commands

- Install dev dependencies: `python -m pip install -e ".[dev]"`
- Run tests: `.venv/bin/pytest`
- Run UI from source: `PYTHONPATH=src python -m app.main ui`
- Inspect video: `PYTHONPATH=src python -m app.main inspect-video --video /path/to/video.mp4`
- Inspect track: `PYTHONPATH=src python -m app.main inspect-track --track /path/to/track.gpx`

## Dependencies

- Python 3.11+.
- Runtime Python packages are declared in `pyproject.toml`.
- System tools expected on PATH: `ffmpeg`, `ffprobe`, and `exiftool`.
- FIT track support uses `fitparse`; keep imports lazy where possible so GPX-only code paths stay import-safe.

## Development Notes

- Preserve the existing local-first model; do not add cloud upload or network processing paths.
- Use `GpxTrackIndex` and `GpxPoint` as the common internal representation for all track formats.
- `--gpx` is retained for compatibility but accepts both `.gpx` and `.fit`; prefer user-facing copy that says "track" when touching new UI/CLI text.
- Do not rename persisted settings keys or UI object attributes casually; the UI uses `QSettings` and many slots reference instance attributes directly.
- Avoid broad rewrites in `main_window.py`; make surgical changes because UI state, video playback, and map refresh paths are tightly coupled.
- For sync behavior, update or add tests in `tests/test_sync.py` before changing timestamp semantics.
- For file format loading, add focused tests in `tests/test_gpx.py`.

## Packaging

- macOS app packaging uses `setup.py` and `py2app`.
- If adding runtime imports needed in the bundled app, update the `OPTIONS["includes"]` list in `setup.py`.
