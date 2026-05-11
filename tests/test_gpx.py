from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.errors import GpxError
from core.gpx import load_fit_track, load_track


class FakeRecord:
    def __init__(self, values: dict) -> None:
        self._values = values

    def get_value(self, name: str):
        return self._values.get(name)


def test_load_track_rejects_unknown_track_type(tmp_path) -> None:
    track_path = tmp_path / "track.txt"
    track_path.write_text("", encoding="utf-8")

    with pytest.raises(GpxError, match="Unsupported track file type"):
        load_track(track_path)


def test_load_fit_track_converts_semicircle_coordinates(monkeypatch, tmp_path) -> None:
    fit_path = tmp_path / "track.fit"
    fit_path.write_bytes(b"fit")
    timestamp = datetime(2025, 6, 1, 8, 30, tzinfo=timezone.utc)

    class FakeFitFile:
        def __init__(self, path: str) -> None:
            self.path = path

        def get_messages(self, name: str):
            assert name == "record"
            return [
                FakeRecord(
                    {
                        "timestamp": timestamp,
                        "position_lat": int(48.25 * (2**31 / 180.0)),
                        "position_long": int(11.5 * (2**31 / 180.0)),
                        "enhanced_altitude": 535.2,
                    }
                )
            ]

    monkeypatch.setitem(sys.modules, "fitparse", SimpleNamespace(FitFile=FakeFitFile))

    track = load_fit_track(fit_path)

    assert len(track.points) == 1
    assert track.points[0].timestamp == timestamp
    assert track.points[0].latitude == pytest.approx(48.25)
    assert track.points[0].longitude == pytest.approx(11.5)
    assert track.points[0].elevation == pytest.approx(535.2)


def test_load_fit_track_accepts_degree_coordinates(monkeypatch, tmp_path) -> None:
    fit_path = tmp_path / "track.fit"
    fit_path.write_bytes(b"fit")

    class FakeFitFile:
        def __init__(self, path: str) -> None:
            self.path = path

        def get_messages(self, name: str):
            return [
                FakeRecord(
                    {
                        "timestamp": datetime(2025, 6, 1, 8, 30),
                        "position_lat": 48.25,
                        "position_long": 11.5,
                        "altitude": 535.2,
                    }
                )
            ]

    monkeypatch.setitem(sys.modules, "fitparse", SimpleNamespace(FitFile=FakeFitFile))

    track = load_fit_track(fit_path)

    assert track.points[0].latitude == pytest.approx(48.25)
    assert track.points[0].longitude == pytest.approx(11.5)
    assert track.points[0].elevation == pytest.approx(535.2)
    assert track.points[0].timestamp.tzinfo == timezone.utc
