from abc import ABC, abstractmethod

from PySide6.QtGui import (
    QPainterPath,
    QPainter,
    QBrush,
    QPen,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QSpinBox, QLineEdit

import theme
from .common import TimelineElement, State
from project import Scene
from utils import widgetWithLabel, updateTimelineReceiver, textWidth


class Cue(TimelineElement):
    ROUNDING_RADIUS = 3
    MIN_LENGTH = 1
    TEXT_LEFT_OFFSET = 3
    TEXT_TOP_OFFSET = 3

    @abstractmethod
    def getColor(self):
        pass

    @abstractmethod
    def getText(self):
        pass

    def paint(self, painter, rect, state):
        qpp = QPainterPath()
        qpp.addRoundedRect(
            rect,
            self.ROUNDING_RADIUS,
            self.ROUNDING_RADIUS,
        )

        # Fix bad anti-aliasing rendering
        qpp.translate(0.5, 0.5)

        brush = QBrush()
        if state == State.NONE:
            brush.setColor(self.getColor())
        elif state == State.HOVERING:
            brush.setColor(self.getColor().darker(120))
        elif state == State.SELECTED:
            brush.setColor(self.getColor().lighter(120))
        brush.setStyle(Qt.SolidPattern)

        pen = QPen()
        if state == State.SELECTED:
            pen.setColor(theme.SELECTED_OUTLINE)
        else:
            pen.setColor(theme.OUTLINE)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillPath(qpp, brush)
        painter.setPen(pen)
        painter.drawPath(qpp)

        pen = QPen()
        pen.setColor(theme.TEXT)

        rect.adjust(self.TEXT_LEFT_OFFSET, self.TEXT_TOP_OFFSET, 0, 0)
        if textWidth(theme.CUE_FONT, self.getText()) < rect.width():
            painter.setFont(theme.CUE_FONT)
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignLeft, self.getText())


class SceneCue(Cue):
    SAVED_ATTRIBUTES = ["start", "length", "cue", "scene_id"]

    def __init__(self, start, length, cue="", scene=None, scene_id=None):
        if scene_id:
            scene = Scene.from_id(scene_id)

        self._cue = QLineEdit()
        self._cue.textChanged.connect(updateTimelineReceiver)
        self.cue = cue
        self.scene = scene
        self.scene_id = scene.id
        super().__init__(start, length)

    def getColor(self):
        return self.scene.qcolor

    def getText(self):
        return f"{self.cue}\n{self.scene.name}"

    def get_cue(self):
        return self._cue.text()

    def set_cue(self, value):
        self._cue.setText(value)

    cue = property(get_cue, set_cue)

    def createWidget(self):
        groupbox = QGroupBox("Scene Cue")
        groupbox.setMaximumWidth(300)
        groupbox.setMaximumHeight(240)
        vboxlayout = QVBoxLayout()
        vboxlayout.addLayout(widgetWithLabel(self._start, "Start (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._length, "Duration (px):"))
        vboxlayout.addLayout(widgetWithLabel(self._cue, "Cue:"))
        vboxlayout.addStretch()
        groupbox.setLayout(vboxlayout)
        return groupbox


class LightingCue(Cue):
    pass
