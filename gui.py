from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog

import cv2
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget, QSlider, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QAction
from PySide6.QtGui import QFont
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout

import pandas as pd
import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window settings
        self.setWindowTitle('Video Scoring')
        self.setGeometry(300, 300, 800, 600)

        self.layout = QVBoxLayout()
        self.widget = QWidget()
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.slider_changed)

        self.label = QLabel()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.slider)

        self.load_button = QPushButton('Load Video')
        self.load_button.clicked.connect(self.load_video)
        self.layout.addWidget(self.load_button)

        button_layout = QHBoxLayout()  # Create a new horizontal layout

        self.button_A = QPushButton('FlipStart')
        self.button_A.clicked.connect(lambda: self.annotate('FlipStart'))
        button_layout.addWidget(self.button_A)  # Add the button to the horizontal layout

        self.button_B = QPushButton('FlipEnd')
        self.button_B.clicked.connect(lambda: self.annotate('FlipEnd'))
        button_layout.addWidget(self.button_B)  # Add the button to the horizontal layout

        self.layout.addLayout(button_layout)  # Add the horizontal layout to the main vertical layout

        self.annotations = []

        self.save_button = QPushButton('Save')
        self.save_button.clicked.connect(self.save_annotations)
        self.layout.addWidget(self.save_button)

        self.video = None
        self.video_path = ''

    def load_video(self):
        file_dialog = QFileDialog()
        video_path, _ = file_dialog.getOpenFileName()
        if video_path:
            self.video = cv2.VideoCapture(video_path)
            if not self.video.isOpened():  # Add this check
                print(f"Could not open video: {video_path}")
                return
            print(f"Loaded video: {video_path}")
            self.video_path = video_path
            self.slider.setMaximum(int(self.video.get(cv2.CAP_PROP_FRAME_COUNT)))
            self.slider.setValue(0)  # To trigger the slider_changed method

            # Clear the annotations when a new video is loaded
            self.annotations.clear()

    def slider_changed(self, value):
        if self.video:
            self.video.set(cv2.CAP_PROP_POS_FRAMES, value)
            ret, frame = self.video.read()
            if not ret:
                print(f"Failed to fetch frame at position: {value}")
                return
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)

            # Draw the frame number on the pixmap
            painter = QPainter(pixmap)
            pen = QPen()
            pen.setColor(Qt.white)
            painter.setPen(pen)
            painter.setFont(QFont('Arial', 100))
            painter.drawText(pixmap.rect(), Qt.AlignTop, f"Frame: {value}")
            painter.end()

            # Scale the pixmap
            screen_resolution = self.screen().availableGeometry()
            screen_width, screen_height = screen_resolution.width(), screen_resolution.height()
            scaled_pixmap = pixmap.scaled(screen_width / 1.5, screen_height / 1.5, Qt.KeepAspectRatio)

            self.label.setPixmap(scaled_pixmap)

    def save_annotations(self):
        video_dir = os.path.dirname(self.video_path)
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        csv_path = os.path.join(video_dir, f'Anno_{video_name}.csv')

        df = pd.DataFrame(self.annotations, columns=['frame', 'event'])
        df.to_csv(csv_path, index=False)

        # Add this line to automatically load a new video after saving annotations
        self.load_video()

    def annotate(self, event):
        if self.video:
            frame_number = int(self.video.get(cv2.CAP_PROP_POS_FRAMES))
            self.annotations.append((frame_number, event))

def main():
    app = QApplication([])

    window = MainWindow()
    window.show()

    app.exec()

if __name__ == "__main__":
    main()


