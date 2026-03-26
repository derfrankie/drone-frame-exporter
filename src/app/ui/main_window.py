from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDateTime, QSettings, QSignalBlocker, QTimer, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.presentation import build_track_markers, build_track_samples
from app.ui.map_panel import MapPanel
from core.errors import DroneFrameExtractorError
from core.export import export_frames
from core.gpx import GpxTrackIndex, load_gpx_track
from core.models import ExportFrameRequest, VideoMetadata
from core.sync import (
    REFERENCE_GPX_FIRST,
    REFERENCE_VIDEO_FIRST,
    SYNC_MODE_ABSOLUTE_VIDEO,
    SYNC_MODE_OFFSET,
    SYNC_MODE_RELATIVE_START,
    resolve_frame_time,
)
from core.utils import ensure_utc_assuming_local
from core.video import inspect_video, is_wide_gamut_source, load_embedded_gps_track


@dataclass(slots=True)
class MarkerEntry:
    frame_seconds: float


class DroneFrameExtractorWindow(QMainWindow):
    def __init__(
        self,
        initial_video: Path | None = None,
        initial_gpx: Path | None = None,
        initial_output_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Drone Frame Extractor")
        self.resize(1560, 940)
        self.settings = QSettings("derfrankie", "drone-frame-exporter")

        self.video_metadata: VideoMetadata | None = None
        self.gpx_index: GpxTrackIndex | None = None
        stored_output_dir = self.settings.value("last_output_dir", "", str)
        self.output_dir: Path | None = initial_output_dir or (Path(stored_output_dir) if stored_output_dir else None)
        self.marker_entries: list[MarkerEntry] = []
        self._is_scrubbing = False
        self._gpx_scrub_index = 0
        self._cached_track_samples: list[dict] = []
        self._current_map_point = None
        self._pending_first_frame_seek = False
        self._pause_after_first_frame = False
        self._gpx_source: str | None = "external" if initial_gpx is not None else None
        self._current_track_key: str | None = None
        self._auto_embedded_offset_applied = False
        self._relative_start_override_utc: datetime | None = None
        self._map_sync_timer = QTimer(self)
        self._map_sync_timer.setSingleShot(True)
        self._map_sync_timer.timeout.connect(self._sync_map_state)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.0)
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget(self)
        self.player.setVideoOutput(self.video_widget)

        self._build_ui()
        self._connect_signals()

        self._pending_initial_video = initial_video
        self._pending_initial_gpx = initial_gpx

        if self.output_dir is not None:
            self.output_edit.setText(str(self.output_dir))
        if initial_video is not None:
            self.video_path_edit.setText(str(initial_video))
        if initial_gpx is not None:
            self.gpx_path_edit.setText(str(initial_gpx))
        QTimer.singleShot(0, self._load_initial_files)

    def _build_ui(self) -> None:
        root = QWidget(self)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)

        outer.addWidget(splitter)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Load a video and GPX track to start.")

        self.setStyleSheet(
            """
            QWidget {
                background: #0a0c0f;
                color: #eef3f7;
                font-family: "Avenir Next", "Helvetica Neue", sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                margin-top: 12px;
                padding-top: 14px;
                background: #12161b;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #98a8b5;
            }
            QPushButton {
                background: #1c232b;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
                padding: 8px 12px;
            }
            QPushButton:hover { background: #27303a; }
            QLineEdit, QComboBox, QDoubleSpinBox, QDateTimeEdit, QTextEdit, QListWidget {
                background: #0f1318;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 10px;
                padding: 6px 8px;
            }
            QSlider::groove:horizontal {
                background: #1b2129;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f3b95f;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background: #27303a;
            }
            """
        )

    def _build_left_panel(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        files_group = QGroupBox("Files", widget)
        files_layout = QGridLayout(files_group)
        self.video_path_edit = QLineEdit()
        self.gpx_path_edit = QLineEdit()
        self.output_edit = QLineEdit()
        files_layout.addWidget(QLabel("Video"), 0, 0)
        files_layout.addWidget(self.video_path_edit, 0, 1)
        self.video_button = QPushButton("Choose…")
        files_layout.addWidget(self.video_button, 0, 2)
        files_layout.addWidget(QLabel("GPX"), 1, 0)
        files_layout.addWidget(self.gpx_path_edit, 1, 1)
        self.gpx_button = QPushButton("Choose…")
        files_layout.addWidget(self.gpx_button, 1, 2)
        files_layout.addWidget(QLabel("Output"), 2, 0)
        files_layout.addWidget(self.output_edit, 2, 1)
        self.output_button = QPushButton("Choose…")
        files_layout.addWidget(self.output_button, 2, 2)

        sync_group = QGroupBox("Sync", widget)
        sync_form = QFormLayout(sync_group)
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems([SYNC_MODE_OFFSET, SYNC_MODE_RELATIVE_START, SYNC_MODE_ABSOLUTE_VIDEO])
        self.reference_mode_combo = QComboBox()
        self.reference_mode_combo.addItem("Video", REFERENCE_VIDEO_FIRST)
        self.reference_mode_combo.addItem("GPX", REFERENCE_GPX_FIRST)
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-864000.0, 864000.0)
        self.offset_spin.setDecimals(3)
        self.offset_spin.setSuffix(" s")
        self.shift_hours_combo = QComboBox()
        for hour in range(-5, 6):
            self.shift_hours_combo.addItem(f"{hour:+d} h", hour)
        zero_shift_index = self.shift_hours_combo.findData(0)
        if zero_shift_index >= 0:
            self.shift_hours_combo.setCurrentIndex(zero_shift_index)
        self.start_time_edit = QDateTimeEdit(self)
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setDateTime(datetime.utcnow())
        sync_form.addRow("Mode", self.sync_mode_combo)
        sync_form.addRow("Timestamp Authority", self.reference_mode_combo)
        sync_form.addRow("Derived Offset", self.offset_spin)
        sync_form.addRow("Export Time Shift", self.shift_hours_combo)
        sync_form.addRow("Relative Start", self.start_time_edit)

        markers_group = QGroupBox("Selected Photos", widget)
        markers_layout = QVBoxLayout(markers_group)
        self.marker_list = QListWidget()
        self.marker_list.setSelectionMode(QAbstractItemView.SingleSelection)
        markers_layout.addWidget(self.marker_list)
        marker_buttons = QHBoxLayout()
        self.remove_marker_button = QPushButton("Remove Selected")
        self.jump_marker_button = QPushButton("Jump To Marker")
        marker_buttons.addWidget(self.remove_marker_button)
        marker_buttons.addWidget(self.jump_marker_button)
        markers_layout.addLayout(marker_buttons)

        export_group = QGroupBox("Export", widget)
        export_form = QFormLayout(export_group)
        self.quality_spin = QDoubleSpinBox()
        self.quality_spin.setRange(2, 31)
        self.quality_spin.setDecimals(0)
        self.quality_spin.setValue(10)
        self.manifest_combo = QComboBox()
        self.manifest_combo.addItems(["json", "csv"])
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["jpg", "tiff"])
        self.filename_middle_edit = QLineEdit()
        self.filename_middle_edit.setPlaceholderText("tour / bestshot / hero")
        self.export_button = QPushButton("Export Photos")
        export_form.addRow("JPG Quality", self.quality_spin)
        export_form.addRow("Export Format", self.export_format_combo)
        export_form.addRow("Manifest", self.manifest_combo)
        export_form.addRow("Filename Middle", self.filename_middle_edit)
        export_form.addRow("", self.export_button)

        layout.addWidget(files_group)
        layout.addWidget(sync_group)
        layout.addWidget(markers_group, 1)
        layout.addWidget(export_group)
        return widget

    def _build_center_panel(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(12)

        header = QLabel("Visual Frame Selection")
        header.setStyleSheet("font-size: 26px; font-weight: 600; color: #f5f8fb;")
        subtitle = QLabel("Scrub the video, preview the current frame location on the GPX track, and mark only the still photos you want.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #98a8b5;")

        self.video_widget.setMinimumHeight(420)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_label = QLabel("00:00.000 / 00:00.000")
        self.current_info = QTextEdit()
        self.current_info.setReadOnly(True)
        self.current_info.setMinimumHeight(132)
        self.track_summary = QTextEdit()
        self.track_summary.setReadOnly(True)
        self.track_summary.setMinimumHeight(132)

        transport = QHBoxLayout()
        self.step_back_5_button = QPushButton("-5 Frames")
        self.step_back_1_button = QPushButton("-1 Frame")
        self.play_pause_button = QPushButton("Play")
        self.step_forward_1_button = QPushButton("+1 Frame")
        self.step_forward_5_button = QPushButton("+5 Frames")
        transport.addWidget(self.step_back_5_button)
        transport.addWidget(self.step_back_1_button)
        transport.addWidget(self.play_pause_button)
        transport.addWidget(self.step_forward_1_button)
        transport.addWidget(self.step_forward_5_button)
        transport.addStretch(1)
        self.add_marker_button = QPushButton("Add Current Frame")
        transport.addWidget(self.add_marker_button)

        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addWidget(self.video_widget, 1)
        layout.addLayout(transport)
        layout.addWidget(self.position_slider)
        layout.addWidget(self.position_label)
        info_row = QHBoxLayout()
        info_row.addWidget(self.current_info, 1)
        info_row.addWidget(self.track_summary, 1)
        layout.addLayout(info_row)
        return widget

    def _build_right_panel(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        heading = QLabel("Track Placement")
        heading.setStyleSheet("font-size: 22px; font-weight: 600;")
        description = QLabel("The yellow point follows the current video position after applying sync mode, second offset, and hour shift.")
        description.setWordWrap(True)
        description.setStyleSheet("color: #98a8b5;")

        self.track_widget = MapPanel(self)
        self.gpx_scrub_slider = QSlider(Qt.Horizontal)
        self.gpx_scrub_slider.setRange(0, 0)
        self.gpx_scrub_label = QLabel("GPX Cursor: no track loaded")
        self.align_button = QPushButton("Sync Current Video Frame To GPX Cursor")
        self.gpx_step_back_5_button = QPushButton("-5")
        self.gpx_step_back_1_button = QPushButton("-1")
        self.gpx_step_forward_1_button = QPushButton("+1")
        self.gpx_step_forward_5_button = QPushButton("+5")

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self.track_widget, 1)
        gpx_transport = QHBoxLayout()
        gpx_transport.addWidget(self.gpx_step_back_5_button)
        gpx_transport.addWidget(self.gpx_step_back_1_button)
        gpx_transport.addStretch(1)
        gpx_transport.addWidget(self.gpx_step_forward_1_button)
        gpx_transport.addWidget(self.gpx_step_forward_5_button)
        layout.addLayout(gpx_transport)
        layout.addWidget(self.gpx_scrub_slider)
        layout.addWidget(self.gpx_scrub_label)
        layout.addWidget(self.align_button)
        return widget

    def _load_initial_files(self) -> None:
        if self._pending_initial_video is not None:
            self._load_video(self._pending_initial_video)
            self._pending_initial_video = None
        if self._pending_initial_gpx is not None:
            self._load_gpx(self._pending_initial_gpx)
            self._pending_initial_gpx = None

    def _connect_signals(self) -> None:
        self.video_button.clicked.connect(self._choose_video)
        self.gpx_button.clicked.connect(self._choose_gpx)
        self.output_button.clicked.connect(self._choose_output_dir)
        self.step_back_5_button.clicked.connect(lambda: self._step_frames(-5))
        self.step_back_1_button.clicked.connect(lambda: self._step_frames(-1))
        self.play_pause_button.clicked.connect(self._toggle_playback)
        self.step_forward_1_button.clicked.connect(lambda: self._step_frames(1))
        self.step_forward_5_button.clicked.connect(lambda: self._step_frames(5))

        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._refresh_play_pause_button)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)

        self.add_marker_button.clicked.connect(self._add_current_marker)
        self.remove_marker_button.clicked.connect(self._remove_selected_marker)
        self.jump_marker_button.clicked.connect(self._jump_to_selected_marker)
        self.marker_list.itemSelectionChanged.connect(self._refresh_track_view)
        self.marker_list.itemDoubleClicked.connect(self._jump_to_marker_item)

        self.sync_mode_combo.currentTextChanged.connect(self._refresh_from_sync_change)
        self.reference_mode_combo.currentTextChanged.connect(self._refresh_from_sync_change)
        self.offset_spin.valueChanged.connect(self._refresh_from_sync_change)
        self.shift_hours_combo.currentIndexChanged.connect(self._refresh_from_sync_change)
        self.start_time_edit.dateTimeChanged.connect(self._on_relative_start_changed)
        self.export_button.clicked.connect(self._export_selected_frames)
        self.gpx_scrub_slider.valueChanged.connect(self._on_gpx_scrub_changed)
        self.align_button.clicked.connect(self._align_video_to_gpx_cursor)
        self.gpx_step_back_5_button.clicked.connect(lambda: self._step_gpx_cursor(-5))
        self.gpx_step_back_1_button.clicked.connect(lambda: self._step_gpx_cursor(-1))
        self.gpx_step_forward_1_button.clicked.connect(lambda: self._step_gpx_cursor(1))
        self.gpx_step_forward_5_button.clicked.connect(lambda: self._step_gpx_cursor(5))
        self.track_widget.pointScrubbed.connect(self._on_track_scrubbed)

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose video", "", "Videos (*.mp4 *.mov *.m4v *.avi);;All files (*)")
        if path:
            self.video_path_edit.setText(path)
            self._load_video(Path(path))

    def _choose_gpx(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose GPX", "", "GPX files (*.gpx);;All files (*)")
        if path:
            self.gpx_path_edit.setText(path)
            self._load_gpx(Path(path))

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_dir = Path(path)
            self.output_edit.setText(path)
            self.settings.setValue("last_output_dir", path)

    def _load_video(self, path: Path) -> None:
        self.statusBar().showMessage("Inspecting video metadata…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.video_metadata = inspect_video(path)
        except DroneFrameExtractorError as exc:
            QMessageBox.critical(self, "Video Error", str(exc))
            self.statusBar().showMessage("Video loading failed.")
            return
        finally:
            QApplication.restoreOverrideCursor()
        preferred_export_format = "tiff" if is_wide_gamut_source(self.video_metadata) else "jpg"
        export_index = self.export_format_combo.findText(preferred_export_format)
        if export_index >= 0:
            self.export_format_combo.setCurrentIndex(export_index)
        self._reset_embedded_auto_sync_if_needed()
        if self._gpx_source == "embedded":
            self._clear_track_state(clear_gpx_field=True)
        self._pending_first_frame_seek = True
        self.player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.statusBar().showMessage(f"Loaded video metadata: {path.name}  |  preparing first frame…")
        if self._gpx_source != "external":
            self._try_load_embedded_gpx(path)
        self._refresh_current_info()

    def _load_gpx(self, path: Path) -> None:
        self.statusBar().showMessage("Loading GPX track…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.gpx_index = load_gpx_track(path)
        except DroneFrameExtractorError as exc:
            QMessageBox.critical(self, "GPX Error", str(exc))
            self.statusBar().showMessage("GPX loading failed.")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.gpx_path_edit.setText(str(path))
        self._load_track_index(self.gpx_index, source="external", status_label=f"Loaded GPX: {path.name}")

    def _load_track_index(self, track_index: GpxTrackIndex, source: str, status_label: str) -> None:
        self.gpx_index = track_index
        self._gpx_source = source
        self._current_track_key = (
            f"{source}:{len(track_index.points)}:{track_index.start_time.isoformat()}:{track_index.end_time.isoformat()}"
        )
        self.track_widget.set_track(self.gpx_index)
        self._cached_track_samples = [
            {
                "index": sample.index,
                "timestamp": sample.timestamp,
                "latitude": sample.latitude,
                "longitude": sample.longitude,
            }
            for sample in build_track_samples(self.gpx_index, interval_seconds=5.0)
        ]
        with QSignalBlocker(self.gpx_scrub_slider):
            self.gpx_scrub_slider.setRange(0, len(self.gpx_index.points) - 1)
            self.gpx_scrub_slider.setValue(0)
        self._gpx_scrub_index = 0
        self._refresh_gpx_scrub_label()
        self.statusBar().showMessage(status_label)
        self._refresh_track_view()

    def _clear_track_state(self, clear_gpx_field: bool = False) -> None:
        self.gpx_index = None
        self._gpx_source = None
        self._current_track_key = None
        self._current_map_point = None
        if clear_gpx_field:
            self.gpx_path_edit.clear()
        self.track_widget.set_track(None)
        self.track_widget.set_markers([])
        self.track_widget.set_current_point(None)
        self.track_widget.set_scrub_point(None)
        self.track_widget.set_web_map_state(
            track_points=[],
            markers=[],
            current_point=None,
            scrub_point=None,
            track_key="empty",
        )
        self._cached_track_samples = []
        with QSignalBlocker(self.gpx_scrub_slider):
            self.gpx_scrub_slider.setRange(0, 0)
            self.gpx_scrub_slider.setValue(0)
        self._gpx_scrub_index = 0
        self._refresh_gpx_scrub_label()
        self._refresh_track_summary(self.player.position() / 1000.0)

    def _reset_embedded_auto_sync_if_needed(self) -> None:
        if not self._auto_embedded_offset_applied:
            return
        self.sync_mode_combo.setCurrentText(SYNC_MODE_OFFSET)
        reference_index = self.reference_mode_combo.findData(REFERENCE_VIDEO_FIRST)
        if reference_index >= 0:
            self.reference_mode_combo.setCurrentIndex(reference_index)
        self.offset_spin.setValue(0.0)
        zero_shift_index = self.shift_hours_combo.findData(0)
        if zero_shift_index >= 0:
            self.shift_hours_combo.setCurrentIndex(zero_shift_index)
        self._auto_embedded_offset_applied = False

    def _try_load_embedded_gpx(self, video_path: Path) -> None:
        if self.video_metadata is None or not self.video_metadata.has_embedded_gps:
            if self._gpx_source == "embedded":
                self._clear_track_state(clear_gpx_field=True)
            return

        self.statusBar().showMessage("Loading embedded GoPro GPS track…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            embedded_track = load_embedded_gps_track(
                video_path,
                anchor_timestamp=self.video_metadata.creation_time,
            )
        except DroneFrameExtractorError:
            embedded_track = None
        finally:
            QApplication.restoreOverrideCursor()

        if embedded_track is None:
            self._clear_track_state(clear_gpx_field=True)
            self._reset_embedded_auto_sync_if_needed()
            self.statusBar().showMessage("Embedded telemetry found, but no usable GPS track was extracted.")
            return
        self.gpx_path_edit.setText("[Embedded GPS from video]")
        self.sync_mode_combo.setCurrentText(SYNC_MODE_OFFSET)
        reference_index = self.reference_mode_combo.findData(REFERENCE_VIDEO_FIRST)
        if reference_index >= 0:
            self.reference_mode_combo.setCurrentIndex(reference_index)
        self.offset_spin.setValue(0.0)
        zero_shift_index = self.shift_hours_combo.findData(0)
        if zero_shift_index >= 0:
            self.shift_hours_combo.setCurrentIndex(zero_shift_index)
        self._auto_embedded_offset_applied = True
        self._load_track_index(
            embedded_track,
            source="embedded",
            status_label=f"Loaded embedded GPS track from {video_path.name}",
        )

    def _on_duration_changed(self, duration_ms: int) -> None:
        with QSignalBlocker(self.position_slider):
            self.position_slider.setRange(0, max(duration_ms, 0))
        self._refresh_position_label(self.player.position(), duration_ms)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.LoadedMedia and self._pending_first_frame_seek:
            self._pending_first_frame_seek = False
            self._pause_after_first_frame = True
            self.player.setPosition(0)
            self.player.play()
            QTimer.singleShot(250, self._finalize_first_frame_seek)
            if self.video_metadata is not None:
                self.statusBar().showMessage(
                    f"Loaded video: {self.video_metadata.path.name}  |  rendering first frame…"
                )

    def _on_position_changed(self, position_ms: int) -> None:
        if not self._is_scrubbing:
            with QSignalBlocker(self.position_slider):
                self.position_slider.setValue(position_ms)
        self._refresh_position_label(position_ms, self.player.duration())
        if self._pause_after_first_frame and position_ms > 0:
            self._finalize_first_frame_seek()
        self._refresh_current_info()

    def _finalize_first_frame_seek(self) -> None:
        if not self._pause_after_first_frame:
            return
        self._pause_after_first_frame = False
        self.player.pause()
        if self.player.position() <= 0:
            self.player.setPosition(1)
        if self.video_metadata is not None:
            self.statusBar().showMessage(
                f"Loaded video: {self.video_metadata.path.name}  |  first frame ready"
            )

    def _on_slider_pressed(self) -> None:
        self._is_scrubbing = True

    def _on_slider_released(self) -> None:
        self._is_scrubbing = False
        self.player.setPosition(self.position_slider.value())

    def _on_slider_moved(self, value: int) -> None:
        self._refresh_position_label(value, self.player.duration())
        if self._is_scrubbing:
            self.player.setPosition(value)

    def _toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _refresh_play_pause_button(self, _state: QMediaPlayer.PlaybackState | None = None) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.play_pause_button.setText("Pause")
        else:
            self.play_pause_button.setText("Play")

    def _step_frames(self, frame_count: int) -> None:
        if self.video_metadata is None:
            return
        fps = self.video_metadata.fps or 30.0
        delta_ms = max(int(round((1000.0 / fps) * abs(frame_count))), 1)
        new_position = self.player.position() + (delta_ms if frame_count > 0 else -delta_ms)
        bounded = min(max(new_position, 0), self.player.duration() or 0)
        self.player.setPosition(bounded)

    def _add_current_marker(self) -> None:
        if self.video_metadata is None:
            QMessageBox.information(self, "No Video", "Load a video before adding markers.")
            return
        frame_seconds = round(self.player.position() / 1000.0, 3)
        if any(abs(marker.frame_seconds - frame_seconds) < 0.001 for marker in self.marker_entries):
            self.statusBar().showMessage("This frame is already marked.")
            return
        self.marker_entries.append(MarkerEntry(frame_seconds=frame_seconds))
        self.marker_entries.sort(key=lambda entry: entry.frame_seconds)
        self._refresh_marker_list()
        self.statusBar().showMessage(f"Added photo marker at {frame_seconds:.3f}s")

    def _remove_selected_marker(self) -> None:
        current_row = self.marker_list.currentRow()
        if current_row < 0:
            return
        self.marker_entries.pop(current_row)
        self._refresh_marker_list()

    def _jump_to_selected_marker(self) -> None:
        current_row = self.marker_list.currentRow()
        if current_row < 0:
            return
        marker = self.marker_entries[current_row]
        self.player.setPosition(int(marker.frame_seconds * 1000))

    def _jump_to_marker_item(self, item: QListWidgetItem) -> None:
        row = self.marker_list.row(item)
        if row < 0 or row >= len(self.marker_entries):
            return
        self.player.setPosition(int(self.marker_entries[row].frame_seconds * 1000))

    def _refresh_marker_list(self) -> None:
        self.marker_list.clear()
        for index, marker in enumerate(self.marker_entries, start=1):
            item = QListWidgetItem(f"Photo {index}  {marker.frame_seconds:.3f}s")
            self.marker_list.addItem(item)
        self._refresh_track_view()

    def _refresh_from_sync_change(self) -> None:
        self._refresh_current_info()
        self._refresh_track_view()

    def _refresh_position_label(self, position_ms: int, duration_ms: int) -> None:
        self.position_label.setText(
            f"{_format_ms(position_ms)} / {_format_ms(duration_ms)}"
        )

    def _refresh_current_info(self) -> None:
        if self.video_metadata is None:
            self.current_info.setPlainText("Load a video to start scrubbing through frames.")
            return

        frame_seconds = self.player.position() / 1000.0
        lines = [
            f"Video: {self.video_metadata.path.name}",
            f"Frame position: {frame_seconds:.3f}s",
            f"Creation time: {self.video_metadata.creation_time.isoformat() if self.video_metadata.creation_time else 'missing'}",
            f"Resolution: {self.video_metadata.width}x{self.video_metadata.height}",
        ]
        if self._gpx_source == "embedded":
            lines.append("Embedded GPS: loaded")
        elif self.video_metadata.has_embedded_gps:
            lines.append("Embedded telemetry: detected, but no usable GPS track loaded")
        if is_wide_gamut_source(self.video_metadata):
            lines.extend(
                [
                    "Detected source: wide gamut / HDR-like",
                    f"Codec: {self.video_metadata.codec_name or 'unknown'}",
                    f"Primaries/Transfer: {self.video_metadata.color_primaries or 'unknown'} / {self.video_metadata.color_transfer or 'unknown'}",
                    "Suggested export format: tiff",
                ]
            )

        try:
            resolved = self._resolve_frame(frame_seconds)
        except DroneFrameExtractorError as exc:
            lines.extend(["", f"Sync issue: {exc}"])
            self._current_map_point = None
            self.track_widget.set_current_point(None)
            self.current_info.setPlainText("\n".join(lines))
            self._refresh_track_summary(frame_seconds)
            self._map_sync_timer.start(80)
            return

        lines.extend(["", f"Resolved timestamp: {resolved.resolved_timestamp.isoformat()}"])
        if resolved.gpx_point is not None:
            try:
                lines.extend(
                    [
                        f"GPX point time: {resolved.gpx_point.timestamp.isoformat()}",
                        f"Location: {resolved.gpx_point.latitude:.6f}, {resolved.gpx_point.longitude:.6f}",
                        f"Altitude: {resolved.gpx_point.elevation if resolved.gpx_point.elevation is not None else 'n/a'}",
                    ]
                )
                self._current_map_point = resolved.gpx_point
                self.track_widget.set_current_point(resolved.gpx_point)
            except DroneFrameExtractorError:
                pass
        else:
            lines.append("GPX: not loaded, export will use video timestamp plus sync settings only")
            self._current_map_point = None
            self.track_widget.set_current_point(None)
        self.current_info.setPlainText("\n".join(lines))
        self._refresh_track_summary(frame_seconds)
        self._map_sync_timer.start(80)

    def _refresh_track_summary(self, frame_seconds: float) -> None:
        if self.video_metadata is None:
            self.track_summary.setPlainText("Load a video to see the current placement.")
            return
        try:
            resolved = self._resolve_frame(frame_seconds)
        except DroneFrameExtractorError as exc:
            self.track_summary.setPlainText(str(exc))
            return

        self.track_summary.setPlainText(
            "\n".join(
                self._build_track_summary_lines(frame_seconds, resolved)
            )
        )

    def _refresh_track_view(self) -> None:
        if self.video_metadata is None or self.gpx_index is None:
            return
        frame_values = [entry.frame_seconds for entry in self.marker_entries]
        markers = build_track_markers(
            video_metadata=self.video_metadata,
            gpx_index=self.gpx_index,
            frame_values=frame_values,
            sync_mode=self.sync_mode_combo.currentText(),
            offset_seconds=self._effective_offset_seconds(),
            relative_start_time=self._relative_start_datetime(),
            shift_hours=self._selected_shift_hours(),
            reference_mode=self._selected_reference_mode(),
        )
        selected_row = self.marker_list.currentRow()
        selected_frame_seconds = (
            self.marker_entries[selected_row].frame_seconds if 0 <= selected_row < len(self.marker_entries) else None
        )
        marker_payload: list[dict] = []
        for marker in markers:
            try:
                resolved = self._resolve_frame(marker.frame_seconds)
            except DroneFrameExtractorError:
                continue
            color = marker.color
            if marker.kind == "frame" and selected_frame_seconds is not None:
                if abs(marker.frame_seconds - selected_frame_seconds) < 0.001:
                    color = "#f3b95f"
            marker_payload.append({"point": resolved.gpx_point, "color": color, "label": marker.label})
        self.track_widget.set_track(self.gpx_index)
        self.track_widget.set_markers(marker_payload)
        self.track_widget.set_scrub_point(self._current_gpx_scrub_point())
        self._sync_map_state(track_marker_payload=marker_payload)

    def _resolve_frame(self, frame_seconds: float):
        if self.video_metadata is None:
            raise DroneFrameExtractorError("Load a video first.")
        return resolve_frame_time(
            frame_seconds=frame_seconds,
            video_metadata=self.video_metadata,
            gpx_index=self.gpx_index,
            sync_mode=self.sync_mode_combo.currentText(),
            offset_seconds=self._effective_offset_seconds(),
            relative_start_time=self._relative_start_datetime(),
            shift_hours=self._selected_shift_hours(),
            reference_mode=self._selected_reference_mode(),
        )

    def _effective_offset_seconds(self) -> float | None:
        if self.sync_mode_combo.currentText() == SYNC_MODE_OFFSET:
            return self.offset_spin.value()
        return None

    def _relative_start_datetime(self) -> datetime | None:
        if self.sync_mode_combo.currentText() == SYNC_MODE_RELATIVE_START:
            if self._relative_start_override_utc is not None:
                return self._relative_start_override_utc
            return ensure_utc_assuming_local(self.start_time_edit.dateTime().toPython())
        return None

    def _on_relative_start_changed(self, _value) -> None:
        self._relative_start_override_utc = None
        self._refresh_from_sync_change()

    def _on_gpx_scrub_changed(self, index: int) -> None:
        self._gpx_scrub_index = index
        self._refresh_gpx_scrub_label()
        self.track_widget.set_scrub_point(self._current_gpx_scrub_point())
        self._refresh_track_summary(self.player.position() / 1000.0)
        self._sync_map_state()

    def _step_gpx_cursor(self, delta: int) -> None:
        if self.gpx_index is None:
            return
        new_index = min(max(self._gpx_scrub_index + delta, 0), len(self.gpx_index.points) - 1)
        self.gpx_scrub_slider.setValue(new_index)

    def _on_track_scrubbed(self, index: int) -> None:
        with QSignalBlocker(self.gpx_scrub_slider):
            self.gpx_scrub_slider.setValue(index)
        self._gpx_scrub_index = index
        self._refresh_gpx_scrub_label()
        self.track_widget.set_scrub_point(self._current_gpx_scrub_point())
        self._refresh_track_summary(self.player.position() / 1000.0)
        self._sync_map_state()

    def _current_gpx_scrub_point(self):
        if self.gpx_index is None:
            return None
        return self.gpx_index.point_at_index(self._gpx_scrub_index)

    def _refresh_gpx_scrub_label(self) -> None:
        point = self._current_gpx_scrub_point()
        if point is None:
            self.gpx_scrub_label.setText("GPX Cursor: no track loaded")
            return
        self.gpx_scrub_label.setText(
            f"GPX Cursor: {point.timestamp.isoformat()}  |  {point.latitude:.6f}, {point.longitude:.6f}"
        )

    def _build_track_summary_lines(self, frame_seconds: float, resolved) -> list[str]:
        lines = [
            f"Sync mode: {self.sync_mode_combo.currentText()}",
            f"Timestamp authority: {self.reference_mode_combo.currentText()}",
            f"Derived offset: {self.offset_spin.value():.3f}s",
            f"Export time shift: {self._selected_shift_hours():.2f}h",
            f"Current frame: {frame_seconds:.3f}s",
            f"Resolved time: {resolved.resolved_timestamp.isoformat()}",
        ]
        if self._selected_shift_hours() != 0:
            lines.append(
                f"Export time: {(resolved.resolved_timestamp + timedelta(hours=self._selected_shift_hours())).isoformat()}"
            )
        if self.gpx_index is None or resolved.gpx_point is None:
            lines.append("Track location: no GPX loaded")
            return lines
        lines.extend(
            [
                f"Track source: {self._gpx_source or 'unknown'}",
                f"Track location: {resolved.gpx_point.latitude:.6f}, {resolved.gpx_point.longitude:.6f}",
                f"GPX cursor: {self._current_gpx_scrub_point().timestamp.isoformat() if self._current_gpx_scrub_point() else 'n/a'}",
                f"Track window: {self.gpx_index.start_time.isoformat()} -> {self.gpx_index.end_time.isoformat()}",
            ]
        )
        if not self.gpx_index.contains_time(resolved.resolved_timestamp):
            delta_seconds = self.gpx_index.distance_to_range_seconds(resolved.resolved_timestamp)
            if resolved.resolved_timestamp < self.gpx_index.start_time:
                direction = "before"
                endpoint = "start"
            else:
                direction = "after"
                endpoint = "end"
            lines.append(
                f"Range status: outside GPX window ({delta_seconds:.1f}s {direction}); clamped to nearest {endpoint} point"
            )
        else:
            lines.append("Range status: inside GPX window")
        return lines

    def _align_video_to_gpx_cursor(self) -> None:
        if self.video_metadata is None or self.gpx_index is None:
            QMessageBox.information(self, "Missing Data", "Load both video and GPX before aligning.")
            return
        if self._selected_reference_mode() == REFERENCE_VIDEO_FIRST and self.video_metadata.creation_time is None:
            QMessageBox.information(
                self,
                "Missing Video Timestamp",
                "The current video has no readable creation time, so automatic offset alignment is not available.",
            )
            return

        current_frame_seconds = self.player.position() / 1000.0
        target_point = self._current_gpx_scrub_point()
        if target_point is None:
            return

        if self._selected_reference_mode() == REFERENCE_GPX_FIRST:
            relative_start_time = target_point.timestamp - timedelta(seconds=current_frame_seconds)
            self.sync_mode_combo.setCurrentText(SYNC_MODE_RELATIVE_START)
            local_display_time = relative_start_time.astimezone().replace(tzinfo=None)
            with QSignalBlocker(self.start_time_edit):
                self.start_time_edit.setDateTime(QDateTime(local_display_time))
            self._relative_start_override_utc = relative_start_time
            self.offset_spin.setValue(0.0)
            zero_shift_index = self.shift_hours_combo.findData(0)
            if zero_shift_index >= 0:
                self.shift_hours_combo.setCurrentIndex(zero_shift_index)
            self.statusBar().showMessage(
                f"Aligned current frame to GPX cursor with GPX as authority: video start set to {relative_start_time.isoformat()}"
            )
            self._refresh_from_sync_change()
            return

        video_start_time = ensure_utc_assuming_local(self.video_metadata.creation_time)
        video_frame_time = video_start_time + timedelta(seconds=current_frame_seconds)
        total_delta_seconds = (target_point.timestamp - video_frame_time).total_seconds()
        residual_offset = total_delta_seconds

        self.sync_mode_combo.setCurrentText(SYNC_MODE_OFFSET)
        self.offset_spin.setValue(residual_offset)
        self.statusBar().showMessage(
            f"Aligned current frame to GPX cursor: derived offset {residual_offset:+.3f}s"
        )
        self._refresh_from_sync_change()

    @staticmethod
    def _point_to_map_dict(point) -> dict | None:
        if point is None:
            return None
        return {
            "latitude": point.latitude,
            "longitude": point.longitude,
            "timestamp": point.timestamp.isoformat(),
        }

    def _sync_map_state(self, track_marker_payload: list[dict] | None = None) -> None:
        if self.gpx_index is None:
            return
        marker_payload = track_marker_payload if track_marker_payload is not None else [
            {
                "point": self._resolve_frame(entry.frame_seconds).gpx_point,
                "color": "#7bdff2",
                "label": f"Photo {index + 1}",
            }
            for index, entry in enumerate(self.marker_entries)
        ]
        self.track_widget.set_web_map_state(
            track_points=self._cached_track_samples,
            markers=[
                {
                    "latitude": item["point"].latitude,
                    "longitude": item["point"].longitude,
                    "color": item["color"],
                    "label": item.get("label", ""),
                    "radius": 6,
                }
                for item in marker_payload
            ],
            current_point=self._point_to_map_dict(self._current_map_point),
            scrub_point=self._point_to_map_dict(self._current_gpx_scrub_point()),
            track_key=self._current_track_key,
        )

    def _export_selected_frames(self) -> None:
        if self.video_metadata is None:
            QMessageBox.information(self, "Missing Files", "Load a video first.")
            return
        if not self.marker_entries:
            QMessageBox.information(self, "No Photos Selected", "Add at least one photo marker before exporting.")
            return
        if not self.output_edit.text().strip():
            QMessageBox.information(self, "Missing Output", "Choose an output folder before exporting.")
            return

        self.output_dir = Path(self.output_edit.text().strip())
        self.settings.setValue("last_output_dir", str(self.output_dir))
        frame_requests = [ExportFrameRequest(frame_seconds=entry.frame_seconds) for entry in self.marker_entries]

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            records, manifest_path = export_frames(
                video_metadata=self.video_metadata,
                gpx_index=self.gpx_index,
                output_dir=self.output_dir,
                frames=frame_requests,
                sync_mode=self.sync_mode_combo.currentText(),
                offset_seconds=self._effective_offset_seconds(),
                relative_start_time=self._relative_start_datetime(),
                shift_hours=self._selected_shift_hours(),
                jpg_quality=int(self.quality_spin.value()),
                export_format=self.export_format_combo.currentText(),
                manifest_format=self.manifest_combo.currentText(),
                filename_middle=self.filename_middle_edit.text(),
            reference_mode=self._selected_reference_mode(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            self.statusBar().showMessage("Export failed.")
            return
        finally:
            QApplication.restoreOverrideCursor()

        QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {len(records)} photos.\nManifest: {manifest_path}",
        )
        self.statusBar().showMessage(f"Exported {len(records)} photos to {self.output_dir}")

    def _selected_shift_hours(self) -> float:
        return float(self.shift_hours_combo.currentData() or 0.0)

    def _selected_reference_mode(self) -> str:
        return str(self.reference_mode_combo.currentData() or REFERENCE_VIDEO_FIRST)


def _format_ms(value: int) -> str:
    total_seconds = max(value, 0) / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}"
