import sys
import tomllib
import json
import faulthandler
import os
import shutil
from datetime import datetime

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
from project import Scene, SCENES, ProjectElement
from timeline import Label, TimeClock, TimeMusic, SceneCue


class Application(QApplication):
    updateTimeline = Signal()
    saveProject = Signal()


class PresetsTab(QWidget):
    COLUMNS = 4

    @classmethod
    def load(cls, timeline, presets):
        tab = cls(timeline)
        # TODO: Don't do this. Save properly.
        tab._presets = presets

        elements_layout = QVBoxLayout()
        for section in presets:
            header = section["header"]
            elements_layout.addWidget(QLabel(header))
            section_layout = QGridLayout()
            i = 0
            for item in section["items"]:
                button = QPushButton(item["label"])
                button.clicked.connect(tab.element_adder(getattr(sys.modules["timeline"], item["type"]), **item["kwargs"]))
                section_layout.addWidget(button, i // tab.COLUMNS, i % tab.COLUMNS)
                i += 1
            # Add blanks to fill columns
            for j in range(tab.COLUMNS - i % tab.COLUMNS):
                section_layout.addWidget(QWidget(), i // tab.COLUMNS, i % tab.COLUMNS)
                i += 1
            elements_layout.addLayout(section_layout)
        elements_layout.addStretch()

        tab.setLayout(elements_layout)
        return tab

    def save(self):
        # TODO: Don't do this. Save properly.
        return self._presets

    def __init__(self, timeline):
        super().__init__()
        self.timeline = timeline

    def element_adder(self, element_type, **kwargs):
        return lambda : self.timeline.add(element_type, **kwargs)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveCue")
        self.resize(1080, 720)

        data = None
        os.makedirs("backups", exist_ok=True)
        try:
            shutil.copy("animusic.json", f"backups/animusic.{datetime.now().strftime('%Y%m%dT%H%M%S')}.json")
            with open("animusic.json", "r") as f:
                data = json.loads(f.read())
        except FileNotFoundError:
            pass

        bottom_layout = QHBoxLayout()
        if data:
            for element in data["project"]["elements"]:
                ProjectElement.load(**element)
            self.timeline = Timeline.load(bottom_layout, **data["timeline"])
        else:
            self.timeline = Timeline(bottom_layout)
        QApplication.instance().saveProject.connect(self.save)

        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        scroll_area.setMinimumHeight(240)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.timeline)

        left_tabs = QTabWidget()
        left_tabs.setMinimumHeight(720 / 2)
        if data:
            self.presets_tab = PresetsTab.load(self.timeline, data["presets"])
        else:
            self.presets_tab = PresetsTab(self.timeline)
        left_tabs.addTab(self.presets_tab, "Presets")

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

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(bottom_layout)

    def save(self):
        project_elements = []
        out = {
            "project": {
                "elements": [scene.save() for scene in SCENES.values()],
            },
            "presets": self.presets_tab.save(),
            "timeline": self.timeline.save(),
        }
        with open("animusic.json", "w") as f:
            f.write(json.dumps(out, indent=2))


faulthandler.enable()
app = Application(sys.argv)
theme.load()
window = MainWindow()
window.show()
app.exec()
