from app.ui.map_panel import _web_map_enabled
from app.ui.web_map import LeafletMapWidget, _leaflet_document, _map_state_payload


def test_map_state_payload_uses_javascript_keys() -> None:
    payload = _map_state_payload(
        track_points=[{"latitude": 1.0, "longitude": 2.0}],
        markers=[{"latitude": 3.0, "longitude": 4.0, "color": "#fff", "label": "A", "radius": 6}],
        current_point={"latitude": 5.0, "longitude": 6.0, "timestamp": "2026-04-07T00:00:00+00:00"},
        scrub_point=None,
        track_key="track-1",
    )

    assert payload == {
        "trackPoints": [{"latitude": 1.0, "longitude": 2.0}],
        "markers": [{"latitude": 3.0, "longitude": 4.0, "color": "#fff", "label": "A", "radius": 6}],
        "currentPoint": {"latitude": 5.0, "longitude": 6.0, "timestamp": "2026-04-07T00:00:00+00:00"},
        "scrubPoint": None,
        "trackKey": "track-1",
    }


def test_on_load_finished_replays_pending_state_with_python_argument_names() -> None:
    class FakeWidget:
        def __init__(self) -> None:
            self._loaded = False
            self._pending_state = {
                "track_points": [{"latitude": 1.0, "longitude": 2.0}],
                "markers": [],
                "current_point": None,
                "scrub_point": None,
                "track_key": "track-1",
            }
            self.calls: list[dict] = []

        def set_map_state(self, **kwargs) -> None:
            self.calls.append(kwargs)

    widget = FakeWidget()

    LeafletMapWidget._on_load_finished(widget, True)

    assert widget._loaded is True
    assert widget.calls == [
        {
            "track_points": [{"latitude": 1.0, "longitude": 2.0}],
            "markers": [],
            "current_point": None,
            "scrub_point": None,
            "track_key": "track-1",
        }
    ]
    assert widget._pending_state is None


def test_web_map_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("DRONE_FRAME_EXTRACTOR_WEB_MAP", raising=False)
    assert _web_map_enabled() is True


def test_web_map_can_be_enabled_with_env(monkeypatch) -> None:
    monkeypatch.setenv("DRONE_FRAME_EXTRACTOR_WEB_MAP", "1")
    assert _web_map_enabled() is True


def test_web_map_can_be_disabled_with_env(monkeypatch) -> None:
    monkeypatch.setenv("DRONE_FRAME_EXTRACTOR_WEB_MAP", "0")
    assert _web_map_enabled() is False


def test_leaflet_document_includes_osm_and_satellite_layers() -> None:
    document = _leaflet_document()

    assert "tile.openstreetmap.org" in document
    assert "World_Imagery/MapServer/tile" in document
    assert "OpenStreetMap" in document
    assert "Satellite" in document
