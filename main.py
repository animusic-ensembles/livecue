import sys

from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QTabWidget,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal

import theme
from timeline import Timeline
from utils import chain


class Application(QApplication):
    updateTimeline = Signal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveCue")
        self.resize(1080, 720)

        bottom_layout = QHBoxLayout()
        timeline = Timeline(bottom_layout)

        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(timeline)

        left_tabs = QTabWidget()
        left_tabs.setMinimumHeight(720 / 2)
        left_tabs.addTab(QWidget(), "Labels")
        left_tabs.addTab(QWidget(), "Time")
        left_tabs.addTab(QWidget(), "Guides")
        left_tabs.addTab(QWidget(), "Lighting")
        left_tabs.addTab(QWidget(), "Scenes")
        left_tabs.setCurrentIndex(4)

        right_tabs = QTabWidget()
        right_tabs.setMinimumHeight(720 / 2)
        right_tabs.addTab(QWidget(), "Label")
        right_tabs.addTab(QWidget(), "Time")
        right_tabs.addTab(QWidget(), "Guide")
        right_tabs.addTab(QWidget(), "Lighting")
        right_tabs.addTab(QWidget(), "Stream")
        right_tabs.addTab(QWidget(), "Projector")
        right_tabs.setCurrentIndex(4)

        left_layout = QVBoxLayout()
        left_layout.addWidget(left_tabs)
        right_layout = QVBoxLayout()
        right_layout.addWidget(right_tabs)

        top_layout = QHBoxLayout()
        top_layout.addLayout(left_layout)
        top_layout.addLayout(right_layout)

        bottom_layout.addWidget(scroll_area)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(bottom_layout)


app = Application(sys.argv)
theme.load()
window = MainWindow()
window.show()
app.exec()
