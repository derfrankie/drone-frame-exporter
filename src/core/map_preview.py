from __future__ import annotations

import json
from pathlib import Path

from core.gpx import GpxTrackIndex
from core.models import GpxPoint


def write_track_preview_html(
    output_path: Path,
    gpx_index: GpxTrackIndex,
    markers: list[dict],
    title: str = "Track Preview",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    points = [_point_to_dict(point) for point in gpx_index.points]
    bounds = _compute_bounds(points)
    document = _build_html_document(
        title=title,
        track_points=points,
        markers=markers,
        bounds=bounds,
    )
    output_path.write_text(document, encoding="utf-8")
    return output_path


def _point_to_dict(point: GpxPoint) -> dict:
    return {
        "timestamp": point.timestamp.isoformat(),
        "latitude": point.latitude,
        "longitude": point.longitude,
        "elevation": point.elevation,
    }


def _compute_bounds(points: list[dict]) -> dict:
    latitudes = [point["latitude"] for point in points]
    longitudes = [point["longitude"] for point in points]
    return {
        "min_lat": min(latitudes),
        "max_lat": max(latitudes),
        "min_lon": min(longitudes),
        "max_lon": max(longitudes),
    }


def _build_html_document(title: str, track_points: list[dict], markers: list[dict], bounds: dict) -> str:
    track_json = json.dumps(track_points)
    markers_json = json.dumps(markers)
    bounds_json = json.dumps(bounds)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0a0c0f;
      --panel: #12161b;
      --track: #5f7686;
      --text: #eef3f7;
      --muted: #98a8b5;
      --accent: #f3b95f;
      --frame: #7bdff2;
      --start: #7ae582;
      --end: #ff5964;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      background: radial-gradient(circle at top, #19212b 0%, var(--bg) 55%);
      color: var(--text);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      min-height: 100vh;
    }}
    .panel {{
      padding: 18px;
      background: rgba(18, 22, 27, 0.94);
      border-left: 1px solid rgba(255, 255, 255, 0.08);
      overflow: auto;
    }}
    .map {{
      padding: 20px;
    }}
    svg {{
      width: 100%;
      height: calc(100vh - 40px);
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
      border-radius: 20px;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}
    h1, h2 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 22px; }}
    h2 {{ font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .marker {{
      padding: 10px 0;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }}
    .marker strong {{ display: block; margin-bottom: 4px; }}
    .small {{ color: var(--muted); font-size: 13px; }}
    .swatch {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      margin-right: 8px;
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .panel {{ border-left: 0; border-top: 1px solid rgba(255,255,255,0.08); }}
      svg {{ height: 70vh; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <div class="map">
      <svg id="track" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid meet"></svg>
    </div>
    <aside class="panel">
      <h1>{title}</h1>
      <p class="small">Offline preview of GPX track placement for the video timeline and selected photo frames.</p>
      <h2>Markers</h2>
      <div id="markers"></div>
    </aside>
  </div>
  <script>
    const trackPoints = {track_json};
    const markers = {markers_json};
    const bounds = {bounds_json};
    const svg = document.getElementById("track");
    const markerList = document.getElementById("markers");
    const width = 1200;
    const height = 800;
    const padding = 48;

    const lonSpan = Math.max(bounds.max_lon - bounds.min_lon, 0.00001);
    const latSpan = Math.max(bounds.max_lat - bounds.min_lat, 0.00001);

    function project(point) {{
      const x = padding + ((point.longitude - bounds.min_lon) / lonSpan) * (width - padding * 2);
      const y = height - padding - ((point.latitude - bounds.min_lat) / latSpan) * (height - padding * 2);
      return {{ x, y }};
    }}

    const pathData = trackPoints
      .map((point, index) => {{
        const p = project(point);
        return `${{index === 0 ? "M" : "L"}} ${{p.x.toFixed(1)}} ${{p.y.toFixed(1)}}`;
      }})
      .join(" ");

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", pathData);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "var(--track)");
    path.setAttribute("stroke-width", "3");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);

    for (const marker of markers) {{
      const p = project(marker);
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", p.x);
      circle.setAttribute("cy", p.y);
      circle.setAttribute("r", marker.kind === "frame" ? 7 : 9);
      circle.setAttribute("fill", marker.color);
      circle.setAttribute("stroke", "#ffffff");
      circle.setAttribute("stroke-width", "1.5");
      svg.appendChild(circle);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", p.x + 10);
      label.setAttribute("y", p.y - 10);
      label.setAttribute("fill", "var(--text)");
      label.setAttribute("font-size", "14");
      label.textContent = marker.label;
      svg.appendChild(label);

      const item = document.createElement("div");
      item.className = "marker";
      item.innerHTML = `
        <strong><span class="swatch" style="background:${{marker.color}}"></span>${{marker.label}}</strong>
        <div class="small">${{marker.timestamp}}</div>
        <div class="small">${{marker.latitude.toFixed(6)}}, ${{marker.longitude.toFixed(6)}}</div>
      `;
      markerList.appendChild(item);
    }}
  </script>
</body>
</html>
"""
