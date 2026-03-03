# views/video_player_widget.py

import cv2
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QStyle)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap


class VideoPlayerWidget(QWidget):
    """Modern video player widget with playback controls"""

    closed = pyqtSignal()

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.is_playing = False
        self.total_frames = 0
        self.current_frame = 0
        self.fps = 30

        self._init_ui()
        self._load_video()

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Video display area
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000;
                border: 2px solid rgba(88, 166, 255, 0.3);
                border-radius: 8px;
            }
        """)
        self.video_label.setMinimumSize(640, 480)
        layout.addWidget(self.video_label)

        # Controls panel
        controls_widget = QWidget()
        controls_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(22, 27, 34, 0.9);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        controls_layout = QVBoxLayout(controls_widget)

        # Progress slider
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid rgba(48, 54, 61, 0.5);
                height: 8px;
                background: rgba(13, 17, 23, 0.8);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #58a6ff;
                border: 2px solid #1f6feb;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background: #1f6feb;
                border-radius: 4px;
            }
        """)
        controls_layout.addWidget(self.progress_slider)

        # Buttons row
        buttons_layout = QHBoxLayout()

        # Play/Pause button
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.clicked.connect(self._toggle_play)
        self.play_button.setFixedSize(40, 40)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: #58a6ff;
            }
            QPushButton:pressed {
                background-color: #0969da;
            }
        """)
        buttons_layout.addWidget(self.play_button)

        # Time label
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        buttons_layout.addWidget(self.time_label)

        buttons_layout.addStretch()

        # Close button
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self._on_close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(177, 24, 24, 0.8);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(218, 54, 51, 0.9);
            }
        """)
        buttons_layout.addWidget(close_button)

        controls_layout.addLayout(buttons_layout)
        layout.addWidget(controls_widget)

    def _load_video(self):
        """Load video file"""
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                self.video_label.setText("Ошибка: не удалось открыть видео")
                return

            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30

            self.progress_slider.setRange(0, self.total_frames)
            self._update_time_label()
            self._update_frame()

        except Exception as e:
            self.video_label.setText(f"Ошибка загрузки видео: {e}")

    def _update_frame(self):
        """Update video frame"""
        if self.cap is None or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if ret:
            self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.progress_slider.setValue(self.current_frame)
            self._update_time_label()

            # Convert frame to QPixmap
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            # Scale to fit label while maintaining aspect ratio
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)
        else:
            # End of video
            self.timer.stop()
            self.is_playing = False
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            # Reset to beginning
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.current_frame = 0
            self._update_frame()

    def _toggle_play(self):
        """Toggle play/pause"""
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            interval = int(1000 / self.fps)
            self.timer.start(interval)
            self.is_playing = True
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def _on_slider_pressed(self):
        """Handle slider press"""
        if self.is_playing:
            self.timer.stop()

    def _on_slider_released(self):
        """Handle slider release"""
        if self.cap:
            frame_pos = self.progress_slider.value()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            self.current_frame = frame_pos
            self._update_frame()

            if self.is_playing:
                interval = int(1000 / self.fps)
                self.timer.start(interval)

    def _update_time_label(self):
        """Update time display"""
        if self.fps > 0:
            current_sec = int(self.current_frame / self.fps)
            total_sec = int(self.total_frames / self.fps)

            current_time = f"{current_sec // 60:02d}:{current_sec % 60:02d}"
            total_time = f"{total_sec // 60:02d}:{total_sec % 60:02d}"

            self.time_label.setText(f"{current_time} / {total_time}")

    def _on_close(self):
        """Handle close button"""
        if self.timer.isActive():
            self.timer.stop()
        if self.cap:
            self.cap.release()
        self.closed.emit()
        self.close()

    def closeEvent(self, event):
        """Handle widget close event"""
        if self.timer.isActive():
            self.timer.stop()
        if self.cap:
            self.cap.release()
        event.accept()
