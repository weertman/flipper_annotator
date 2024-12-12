import sys
import os
import cv2
from PySide6.QtWidgets import QWidget, QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QFileDialog, QMenu, QMenuBar, QSizePolicy
from PySide6.QtGui import QAction, QShortcut, QKeySequence, QImage, QPixmap, QPainter, QColor, QPen
from PySide6.QtCore import QTimer, Qt, QRect, Signal
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import linregress

class CustomTimeline(QWidget):
    frameSelected = Signal(int)  # Signal to emit when a frame is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_frame = 0
        self.annotations = []
        self.total_frames = 0

    def set_current_frame(self, frame):
        self.current_frame = frame
        self.update()

    def set_annotations(self, annotations, total_frames):
        self.annotations = annotations
        self.total_frames = total_frames
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()

        # Background
        painter.fillRect(rect, QColor(255, 255, 255))

        if self.total_frames:
            for annotation in self.annotations:
                start_frame = annotation['start_frame']
                end_frame = annotation['end_frame']
                annotation_type = annotation['type']

                if annotation_type == "Upside Down":
                    color = QColor(30, 136, 229)  # Blue
                elif annotation_type == "Right Side Up":
                    color = QColor(0, 77, 64)  # Green
                elif annotation_type == "Being flipped":
                    color = QColor(255, 165, 0)  # Orange
                else:
                    color = QColor(0, 0, 0)

                # Compute pixel coordinates
                # Using (end_frame + 1) ensures the block covers end_frame inclusively.
                start_x = int(round((start_frame / self.total_frames) * rect.width()))
                end_x = int(round(((end_frame + 1) / self.total_frames) * rect.width()))

                width = end_x - start_x
                if width < 1:
                    width = 1  # Ensure at least 1 pixel in width

                painter.fillRect(QRect(start_x, 0, width, rect.height()), color)

        # Time indicator line
        if self.total_frames > 0:
            painter.setPen(QPen(QColor(216, 27, 96), 2))  # Magenta
            current_x = int(round((self.current_frame / self.total_frames) * rect.width()))
            painter.drawLine(current_x, 0, current_x, rect.height())

        # Border
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if self.total_frames > 0:
            clicked_frame = int((event.position().x() / self.width()) * self.total_frames)
            self.frameSelected.emit(clicked_frame)

def create_and_save_plots(annotation_df, video_fps, video_file):
    # Filter for 'Upside Down' annotations and create a copy
    upside_down_df = annotation_df[annotation_df['type'] == 'Upside Down'].copy()
    upside_down_df['time'] = (upside_down_df['start_frame'] + upside_down_df['end_frame']) / 2 / video_fps
    upside_down_df['time_upside_down'] = (upside_down_df['end_frame'] - upside_down_df['start_frame']) / video_fps

    # Calculate linear regression
    slope, intercept, r_value, p_value, std_err = linregress(upside_down_df['time'], upside_down_df['time_upside_down'])

    # Time vs Time Upside Down Scatter Plot with Regression
    plt.figure()
    plt.scatter(upside_down_df['time'], upside_down_df['time_upside_down'], label='Data')
    plt.plot(upside_down_df['time'], intercept + slope * upside_down_df['time'], 'r', label=f'y = {slope:.2f}x + {intercept:.2f}\n R^2 = {r_value**2:.2f}\n p = {p_value:.4f}')
    plt.xlabel('Time (s)')
    plt.ylabel('Righting time (s)')
    plt.title('Time (s) vs Time to right')
    plt.legend()
    time_plot_file = os.path.splitext(video_file)[0] + '_time_plot.png'
    plt.savefig(time_plot_file)
    plt.show()

    # Violin + Swarm Plot
    plt.figure()
    sns.violinplot(data=upside_down_df, y='time_upside_down', inner=None, color='lightgray')
    sns.swarmplot(data=upside_down_df, y='time_upside_down', color='black')
    plt.ylabel('Time Upside Down (s)')
    plt.title('Violin + Swarm Plot of Time Upside Down')
    violin_plot_file = os.path.splitext(video_file)[0] + '_violin_plot.png'
    plt.savefig(violin_plot_file)
    plt.show()

class VideoAnnotationApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Annotation Tool")
        self.setGeometry(100, 100, 1200, 800)  # Set default window size

        # Main layout
        layout = QVBoxLayout()

        # Video display label
        self.video_label = QLabel()
        layout.addWidget(self.video_label)

        # Initialize and add the CustomTimeline widget with a fixed height
        self.timeline = CustomTimeline(self)
        self.timeline.setFixedHeight(20)  # Adjust this value as needed
        layout.addWidget(self.timeline)

        # Play button
        self.play_button = QPushButton("Play (space)")
        self.play_button.clicked.connect(self.play_video)
        layout.addWidget(self.play_button)

        # Annotation buttons
        self.annotation_buttons = {
            "Upside Down": QPushButton("Upside Down (A)"),
            "Being flipped": QPushButton("Being flipped (S)"),
            "Right Side Up": QPushButton("Right Side Up (D)")
        }

        # Set button text and background colors
        self.annotation_buttons["Upside Down"].setStyleSheet("QPushButton { color: rgb(30, 136, 229); }")  # Blue text
        self.annotation_buttons["Being flipped"].setStyleSheet("QPushButton { color: rgb(255, 165, 0); }")  # Orange text
        self.annotation_buttons["Right Side Up"].setStyleSheet("QPushButton { color: rgb(0, 77, 64); }")  # Green text

        # Create a horizontal layout for the annotation buttons
        buttons_layout = QHBoxLayout()
        for annotation_type, button in self.annotation_buttons.items():
            button.clicked.connect(self.annotate)
            buttons_layout.addWidget(button)

        layout.addLayout(buttons_layout)

        # Save button
        self.save_button = QPushButton("Save Annotations (T)")
        self.save_button.clicked.connect(self.save_annotations)
        layout.addWidget(self.save_button)

        # Add playback speed slider
        self.speed_slider = QSlider(Qt.Horizontal, self)
        self.speed_slider.setMinimum(1)  # Minimum value
        self.speed_slider.setMaximum(150)  # Maximum value
        self.speed_slider.setValue(75)  # Default value
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(10)
        self.speed_slider.setFocusPolicy(Qt.StrongFocus)
        self.speed_slider.valueChanged.connect(self.adjust_playback_speed)

        # Set the central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Menu for loading video
        self.menu_bar = QMenuBar(self)
        self.file_menu = QMenu("&File", self)
        self.menu_bar.addMenu(self.file_menu)
        self.setMenuBar(self.menu_bar)

        self.open_action = QAction("&Open Video", self)
        self.open_action.triggered.connect(self.open_video_file)
        self.file_menu.addAction(self.open_action)

        # Placeholder for video capture
        self.capture = None

        # Placeholder for annotations
        self.annotations = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        # Connect the frameSelected signal from the timeline to the set_frame method
        self.timeline.frameSelected.connect(self.set_frame)

        # Current annotation state
        self.current_annotation = None
        self.current_annotation_start = None

        self.current_video_file = None  # Placeholder for the current video file path

        # Set up hotkeys
        self.setup_hotkeys()

        # Load annotations button
        self.load_annotations_button = QPushButton("Load Annotations (W)")
        self.load_annotations_button.clicked.connect(self.load_annotations)
        self.load_annotations_button.setEnabled(False)  # Disabled initially
        layout.addWidget(self.load_annotations_button)

        self.speed_slider.setStyleSheet("""
                    QSlider::groove:horizontal {
                        height: 6px;
                        background: #B5B5B5;
                        margin: 2px 0;
                    }
                    QSlider::handle:horizontal {
                        background: #5C5C5C;
                        border: 1px solid #5C5C5C;
                        width: 18px;
                        margin: -2px 0;
                        border-radius: 3px;
                    }
                """)

        self.speed_slider.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.speed_slider.setMaximumHeight(20)  # Adjust as needed
        layout.addWidget(self.speed_slider)

    def setup_hotkeys(self):
        # Play/Pause
        QShortcut(QKeySequence("Space"), self, self.toggle_play_pause)

        # Upside Down
        QShortcut(QKeySequence("A"), self, lambda: self.trigger_annotation("Upside Down"))

        # Being flipped
        QShortcut(QKeySequence("S"), self, lambda: self.trigger_annotation("Being flipped"))

        # Right Side Up
        QShortcut(QKeySequence("D"), self, lambda: self.trigger_annotation("Right Side Up"))

        # Save Annotations
        QShortcut(QKeySequence("T"), self, self.save_annotations)

        # Open Video
        QShortcut(QKeySequence("Q"), self, self.open_video_file)

        # Load Annotations
        QShortcut(QKeySequence("W"), self, self.load_annotations)

    def toggle_play_pause(self):
        if self.timer.isActive():
            self.play_video()  # This will pause if already playing
        else:
            self.play_video()

    def adjust_playback_speed(self, interval):
        if self.timer.isActive():
            self.timer.start(interval)

    def trigger_annotation(self, annotation_type):
        for button_text, button in self.annotation_buttons.items():
            if button_text == annotation_type:
                button.click()
                break

    def load_video(self, file_path):
        if self.capture:
            self.capture.release()

        self.capture = cv2.VideoCapture(file_path)
        self.total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.play_button.setEnabled(True)
        self.timeline.set_annotations(self.annotations, self.total_frames)  # Update the custom timeline
        self.current_video_file = file_path  # Store the video file path

    def load_annotations(self):
        default_dir = os.path.dirname(self.current_video_file) if self.current_video_file else ''
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Annotations", default_dir, "CSV Files (*.csv)")
        if file_name:
            self.annotations = pd.read_csv(file_name).to_dict('records')
            self.timeline.set_annotations(self.annotations, self.total_frames)
            print(f'Annotations loaded from: {file_name}')

    def play_video(self):
        if not self.timer.isActive():
            self.timer.start(self.speed_slider.value())  # Use the value from the slider
            self.play_button.setText('Pause')
        else:
            self.timer.stop()
            self.play_button.setText('Play')

    def next_frame(self):
        if self.capture and self.capture.isOpened():
            current_frame = int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
            ret, frame = self.capture.read()
            if ret:
                self.display_frame(frame)
                self.timeline.set_current_frame(current_frame)

                if self.current_annotation:
                    # Extend the end frame of the current annotation
                    self.current_annotation['end_frame'] = current_frame
                    self.timeline.set_annotations(self.annotations, self.total_frames)
            else:
                self.timer.stop()
                self.play_button.setText('Play')
        self.timer.start(self.speed_slider.value())

    def display_frame(self, frame):
        # Convert the frame color to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Display current annotation text overlay
        text_scale = 3
        text_thickness = 4
        rect_height = 80
        rect_margin = 10
        rect_width = 700
        text_x = frame.shape[1] - rect_width - rect_margin
        text_y = 120

        if self.current_annotation and isinstance(self.current_annotation, dict):
            annotation_type = self.current_annotation['type']
            if annotation_type == "Upside Down":
                color = (30, 136, 229)
            elif annotation_type == "Right Side Up":
                color = (0, 77, 64)
            elif annotation_type == "Being flipped":
                color = (255, 165, 0)
            else:
                color = (0, 0, 0)

            # Draw rectangle background for text
            cv2.rectangle(frame, (text_x, text_y - rect_height), (text_x + rect_width, text_y), (255, 255, 255), -1)

            # Draw text
            cv2.putText(frame, annotation_type,
                        (text_x, text_y - rect_margin),
                        cv2.FONT_HERSHEY_SIMPLEX, text_scale,
                        color, text_thickness, cv2.LINE_AA)

        # Convert to QPixmap
        image = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio))

    def set_frame(self, frame_number):
        if self.capture and self.capture.isOpened():
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.capture.read()
            if ret:
                self.display_frame(frame)
                self.timeline.set_current_frame(frame_number)

    def open_video_file(self):
        default_dir = '../../data'  # Default directory

        # Check if the default directory exists
        if not os.path.isdir(default_dir):
            print(f"Warning: Default directory '{default_dir}' not found. Falling back to script's location.")
            default_dir = os.path.dirname(os.path.abspath(__file__))

        file_name, _ = QFileDialog.getOpenFileName(self, "Open Video File", default_dir, "Video Files (*.mp4 *.avi *.mov)")
        if file_name:
            self.load_video(file_name)
            self.current_video_file = file_name
            self.load_annotations_button.setEnabled(True)
            print(f'loading video file from: {file_name}')

    def annotate(self):
        new_annotation_type = self.sender().text().split(' (')[0]
        current_frame = self.get_current_video_frame()

        # End the current annotation if any
        if self.current_annotation:
            self.current_annotation['end_frame'] = current_frame
            self.current_annotation = None

        # Process overlapping annotations first
        self.process_overlapping_annotations(current_frame)

        # Start a new annotation
        self.current_annotation = {
            'start_frame': current_frame,
            'end_frame': current_frame,
            'type': new_annotation_type
        }
        self.annotations.append(self.current_annotation)

        # Update the custom timeline with new annotations
        self.timeline.set_annotations(self.annotations, self.total_frames)

    def process_overlapping_annotations(self, current_frame):
        updated_annotations = []
        for annotation in self.annotations:
            # Check if current_frame lies within this annotation
            if annotation['start_frame'] <= current_frame <= annotation['end_frame']:
                # If part of the annotation is before current_frame
                if annotation['start_frame'] < current_frame:
                    updated_annotations.append({
                        'start_frame': annotation['start_frame'],
                        'end_frame': current_frame - 1,
                        'type': annotation['type']
                    })

                # If part of the annotation is after current_frame
                if annotation['end_frame'] > current_frame:
                    updated_annotations.append({
                        'start_frame': current_frame + 1,
                        'end_frame': annotation['end_frame'],
                        'type': annotation['type']
                    })

                # The frame at `current_frame` is effectively "freed up"
                # by not adding any annotation covering this exact frame.
            else:
                # No overlap; keep the annotation as is.
                updated_annotations.append(annotation)

        self.annotations = updated_annotations

    def get_current_video_frame(self):
        if self.capture:
            return int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
        return 0

    def save_annotations(self):
        if self.current_video_file:
            default_save_path = os.path.splitext(self.current_video_file)[0] + '.csv'
        else:
            default_save_path = ''

        file_name, _ = QFileDialog.getSaveFileName(self, "Save Annotations", default_save_path, "CSV Files (*.csv)")
        if file_name:
            # Save annotations to CSV
            df = pd.DataFrame(self.annotations)
            print(f'saving annotations and plots to: {file_name}')
            df.to_csv(file_name, index=False)
            self.annotations = []

            # Create and save plots
            video_fps = self.capture.get(cv2.CAP_PROP_FPS)  # Get the FPS of the video
            create_and_save_plots(df, video_fps, file_name)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = VideoAnnotationApp()
    mainWin.show()
    sys.exit(app.exec())
