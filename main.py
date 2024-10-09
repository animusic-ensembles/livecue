import sys

from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QTabWidget,
)
from PySide6.QtCore import Qt

import theme
from timeline import Timeline
from utils import chain


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveCue")
        self.resize(1080, 720)

        timeline = Timeline()

        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(timeline)

        left_tabs = QTabWidget()
        left_tabs.setMinimumHeight(720 / 2)

        right_tabs = QTabWidget()
        right_tabs.setMinimumHeight(720 / 2)

        left_layout = QVBoxLayout()
        left_layout.addWidget(left_tabs)
        right_layout = QVBoxLayout()
        right_layout.addWidget(right_tabs)

        top_layout = QHBoxLayout()
        top_layout.addLayout(left_layout)
        top_layout.addLayout(right_layout)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(scroll_area)


app = QApplication(sys.argv)
theme.load()
window = MainWindow()
window.show()
app.exec()
