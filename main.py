import sys
import tomllib

from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QTabWidget,
    QGroupBox,
    QSizePolicy,
    QLabel,
    QGridLayout,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

import theme
from timeline import Timeline
from utils import chain
from elements import Scene
from timeline.labels import Label
from timeline.time import TimeClock, TimeMusic
from timeline.cue import SceneCue


class Application(QApplication):
    updateTimeline = Signal()


class ElementsTab(QWidget):
    COLUMNS = 4
    LAYOUT = (
        ("Labels", [("Label", Label, {})]),
        #("Guides", [("Sheet", TimeClock, {}), ("Media", TimeClock, {})]),
        ("Times", [("Clock", TimeClock, {}), ("Music", TimeMusic, {})]),
        #("Lighting Cues", [("Lighting", TimeClock, {})]),
        ("Scene Cues", []),
    )

    def __init__(self, timeline):
        super().__init__()
        self.timeline = timeline

        self.scenes = []
        with open("config.toml", "rb") as f:
            data = tomllib.load(f)
            for i, scene in data["scenes"].items():
                Scene(id=i, **scene)
                #self.LAYOUT[-1][1].append((scene["name"], SceneCue, {"scene": Scene(id=i, **scene)}))
                self.LAYOUT[-1][1].append((scene["name"], SceneCue, {"scene_id": i}))

        elements_layout = QVBoxLayout()
        for section, items in self.LAYOUT:
            elements_layout.addWidget(QLabel(section))
            section_layout = QGridLayout()
            i = 0
            for label, element_type, kwargs in items:
                button = QPushButton(label)
                button.clicked.connect(self.element_adder(element_type, kwargs))
                section_layout.addWidget(button, i // self.COLUMNS, i % self.COLUMNS)
                i += 1
            # Add blanks to fill columns
            for j in range(self.COLUMNS - i % self.COLUMNS):
                section_layout.addWidget(QWidget(), i // self.COLUMNS, i % self.COLUMNS)
                i += 1
            elements_layout.addLayout(section_layout)
        elements_layout.addStretch()

        self.setLayout(elements_layout)

    def element_adder(self, element_type, kwargs):
        return lambda : self.timeline.add(element_type, **kwargs)


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
        scroll_area.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        scroll_area.setMinimumHeight(240)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(timeline)

        left_tabs = QTabWidget()
        left_tabs.setMinimumHeight(720 / 2)
        left_tabs.addTab(ElementsTab(timeline), "Elements")

        right_tabs = QTabWidget()
        right_tabs.setMinimumHeight(720 / 2)
        right_tabs.addTab(QWidget(), "Guide")

        left_layout = QVBoxLayout()
        left_layout.addWidget(left_tabs)
        right_layout = QVBoxLayout()
        right_layout.addWidget(right_tabs)

        top_layout = QHBoxLayout()
        top_layout.addLayout(left_layout)
        top_layout.addLayout(right_layout)

        bottom_layout.addWidget(scroll_area)

        timeline.load()

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
