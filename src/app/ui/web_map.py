from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView


class MapBridge(QObject):
    pointScrubbed = Signal(int)

    @Slot(int)
    def map_point_selected(self, point_index: int) -> None:
        self.pointScrubbed.emit(point_index)


class LeafletMapWidget(QWebEngineView):
    pointScrubbed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bridge = MapBridge(self)
        self._bridge.pointScrubbed.connect(self.pointScrubbed)
        self._channel = QWebChannel(self.page())
        self.page().setWebChannel(self._channel)
        self._channel.registerObject("bridge", self._bridge)
        self._loaded = False
        self._pending_state: dict | None = None
        self.loadFinished.connect(self._on_load_finished)
        self.setHtml(_leaflet_document(), QUrl("https://app.local/"))

    def set_map_state(
        self,
        track_points: list[dict],
        markers: list[dict],
        current_point: dict | None,
        scrub_point: dict | None,
    ) -> None:
        state = {
            "trackPoints": track_points,
            "markers": markers,
            "currentPoint": current_point,
            "scrubPoint": scrub_point,
        }
        if not self._loaded:
            self._pending_state = state
            return
        self.page().runJavaScript(f"window.updateMapState({json.dumps(state)});")

    def _on_load_finished(self, ok: bool) -> None:
        self._loaded = ok
        if ok and self._pending_state is not None:
            self.set_map_state(**self._pending_state)
            self._pending_state = None


def _leaflet_document() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Track Map</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    html, body, #map { height: 100%; margin: 0; background: #0a0c0f; }
    .leaflet-control-zoom a { background: #12161b; color: #eef3f7; border-bottom-color: rgba(255,255,255,0.08); }
    .leaflet-control-attribution { background: rgba(18,22,27,0.84); color: #98a8b5; }
    .leaflet-control-attribution a { color: #eef3f7; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""></script>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <script>
    let bridge = null;
    let map = L.map('map', { zoomControl: true, preferCanvas: true });
    let tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    let trackLayer = L.polyline([], { color: '#5f7686', weight: 3, opacity: 0.85 }).addTo(map);
    let markerLayer = L.layerGroup().addTo(map);
    let currentMarker = null;
    let scrubMarker = null;
    let trackPoints = [];

    function makeCircle(latlng, color, radius) {
      return L.circleMarker(latlng, {
        radius: radius,
        color: '#ffffff',
        weight: 1.5,
        fillColor: color,
        fillOpacity: 1
      });
    }

    function nearestTrackPoint(latlng) {
      if (!trackPoints.length) return null;
      let best = trackPoints[0];
      let bestDistance = Infinity;
      for (const point of trackPoints) {
        const dx = point.latitude - latlng.lat;
        const dy = point.longitude - latlng.lng;
        const distance = dx * dx + dy * dy;
        if (distance < bestDistance) {
          bestDistance = distance;
          best = point;
        }
      }
      return best;
    }

    map.on('click', function(event) {
      const point = nearestTrackPoint(event.latlng);
      if (point && bridge) {
        bridge.map_point_selected(point.index);
      }
    });

    window.updateMapState = function(state) {
      trackPoints = state.trackPoints || [];
      const latlngs = trackPoints.map(point => [point.latitude, point.longitude]);
      trackLayer.setLatLngs(latlngs);

      markerLayer.clearLayers();
      for (const marker of state.markers || []) {
        const m = makeCircle([marker.latitude, marker.longitude], marker.color, marker.radius || 6);
        m.bindTooltip(marker.label || '', { direction: 'top' });
        markerLayer.addLayer(m);
      }

      if (currentMarker) map.removeLayer(currentMarker);
      if (state.currentPoint) {
        currentMarker = makeCircle([state.currentPoint.latitude, state.currentPoint.longitude], '#f3b95f', 8).addTo(map);
      } else {
        currentMarker = null;
      }

      if (scrubMarker) map.removeLayer(scrubMarker);
      if (state.scrubPoint) {
        scrubMarker = makeCircle([state.scrubPoint.latitude, state.scrubPoint.longitude], '#7bdff2', 7).addTo(map);
      } else {
        scrubMarker = null;
      }

      if (latlngs.length && !window.__fitDone) {
        map.fitBounds(trackLayer.getBounds(), { padding: [24, 24] });
        window.__fitDone = true;
      }
    };

    new QWebChannel(qt.webChannelTransport, function(channel) {
      bridge = channel.objects.bridge;
    });
  </script>
</body>
</html>
"""
